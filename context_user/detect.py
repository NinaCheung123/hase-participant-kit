"""Flag friction turns: corrections and repeated instructions.

These are deliberately simple, transparent heuristics. Their accuracy is
measured by hand-labelling a sample (`cu label-sample` / `cu score`), and the
rules are frozen before the evaluation phases so the measure can't be tuned
to favour the tool.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .sources import Turn

# A turn that pushes back on what the agent just did.
CORRECTION_PATTERNS = [
    r"^\s*(no|nope|wrong|stop|wait)\b",
    r"\bthat'?s not (what|right|it)\b",
    r"\bnot what i (asked|meant|wanted|said)\b",
    r"\bi (already )?(said|told you|asked( you)?|mentioned)\b",
    r"\bas i (said|mentioned|told you)\b",
    r"\b(still|again)\b.{0,40}\b(not|wrong|broken|fail(s|ing|ed)?|error)\b",
    r"\b(revert|undo|roll ?back)\b",
    r"\b(please )?(don'?t|do not|never|stop)\b.{0,60}\b(use|add|change|touch|create|run|write)\b",
    r"\binstead of\b",
    r"\byou (forgot|missed|ignored|broke)\b",
    # Pushback on an idea or plan rather than on code
    r"\bi still (think|want|feel|prefer|believe)\b",
    r"\bwhat do you mean\b",
    r"\bnot exactly\b",
    r"\b(too much|too long|too complicated|too verbose|overkill)\b",
    r"\bthat'?s not (necessary|needed|the point)\b",
    # Chinese: wrong / I said / not this / again / don't / I still think / isn't it obvious / too much
    r"不对|错了|我说过|我刚才说|不是这样|还是不行|又错|不要|别再",
    r"我还是觉得|我的意思是|不是这个意思|这不是.{0,12}吗|太多了|太长了|没必要",
]
_CORRECTION = [re.compile(p, re.IGNORECASE) for p in CORRECTION_PATTERNS]

REPEAT_THRESHOLD = 0.5   # Jaccard similarity of token sets
REPEAT_MIN_TOKENS = 5    # ignore "ok", "continue", "yes do it"
REPEAT_WINDOW = 2000     # compare against this many earlier turns


@dataclass
class Flags:
    turn: Turn
    correction: str | None = None          # the matched snippet, "interrupt", or "llm"
    repeat_of: str | None = None           # id of the earlier similar turn, or "llm"
    lesson: str = ""                       # rule drafted by the LLM classifier, if any
    tokens: frozenset = field(default_factory=frozenset, repr=False)


def tokens(text: str) -> frozenset:
    """Lower-cased words of 3+ letters plus individual CJK characters."""
    words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_\-]{2,}", text.lower())
    cjk = re.findall(r"[一-鿿]", text)
    return frozenset(words + cjk)


def jaccard(a: frozenset, b: frozenset) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


PASTE_CHARS = 1500  # longer messages are mostly pasted material
FRAME_CHARS = 300   # a short first/last paragraph around a paste is the developer's framing


def own_words(text: str) -> str:
    """The part of a message the developer wrote themselves.

    Drops quoted lines ("> ..." from replying to the agent), fenced code, and
    the middle of long pastes (articles, documents, logs), whose words would
    otherwise trigger false corrections.
    """
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith(">"))
    if len(text) > PASTE_CHARS:
        paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
        ends = {0, len(paras) - 1} if paras else set()
        text = "\n\n".join(paras[i] for i in sorted(ends) if len(paras[i]) <= FRAME_CHARS)
    return text


def find_correction(turn: Turn) -> str | None:
    if turn.kind == "interrupt":
        return "interrupt"  # the developer stopped the agent mid-action
    if turn.index == 0:  # the opening prompt states the task; it can't correct anything
        return None
    words = own_words(turn.text)
    for rx in _CORRECTION:
        m = rx.search(words)
        if m:
            return m.group(0)
    return None


def analyze(turns: list[Turn], labels: dict | None = None, mode: str = "rules") -> list[Flags]:
    """Flag every turn. `turns` must be in chronological order.

    mode: "rules" (keywords only), "llm" (classifier labels only; interrupts
    still count), or "union" (either). `labels` comes from llm.load_cache().

    A repeat is a turn that closely matches one from a *different* session:
    the developer had to tell an agent something they had already told one.
    """
    from .llm import key  # local import: llm imports sources only
    labels = labels or {}
    out: list[Flags] = []
    for t in turns:
        rule = find_correction(t)
        lab = labels.get(key(t)) if mode != "rules" else None
        llm_corr = "llm" if lab and lab["correction"] else None
        if mode == "llm":
            corr = "interrupt" if rule == "interrupt" else llm_corr
        elif mode == "union":
            corr = rule or llm_corr
        else:
            corr = rule
        f = Flags(t, correction=corr, tokens=tokens(t.text), lesson=(lab or {}).get("lesson", ""))
        if len(f.tokens) >= REPEAT_MIN_TOKENS:
            for prev in reversed(out[-REPEAT_WINDOW:]):
                if prev.turn.session != t.session and len(prev.tokens) >= REPEAT_MIN_TOKENS \
                        and jaccard(f.tokens, prev.tokens) >= REPEAT_THRESHOLD:
                    f.repeat_of = prev.turn.id
                    break
        if not f.repeat_of and lab and lab["repeat"]:
            f.repeat_of = "llm"
        out.append(f)
    return out
