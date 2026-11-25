"""Read user prompts from Claude Code and Cursor into one common shape.

Everything here is read-only: we never modify the tools' own files.
"""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

CLAUDE_DIR = Path.home() / ".claude" / "projects"
CURSOR_DIR = Path.home() / "Library" / "Application Support" / "Cursor" / "User"
CURSOR_TRANSCRIPTS_DIR = Path.home() / ".cursor" / "projects"
CODEX_DIR = Path.home() / ".codex" / "sessions"


@dataclass
class Turn:
    """One message the developer typed to an agent."""

    source: str          # "claude" or "cursor"
    session: str         # conversation id
    project: str         # working directory, if known
    ts: datetime | None  # when it was sent, if known
    index: int           # position within its session (0 = opening prompt)
    text: str
    kind: str = "prompt"  # "prompt", "midturn" (sent while the agent was working), "interrupt"
    prev: str = ""        # end of what the agent said just before (context for classifying)

    @property
    def id(self) -> str:
        return f"{self.source}:{self.session}:{self.index}"


def _parse_ts(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):  # Cursor uses epoch milliseconds
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


# ---------------------------------------------------------------- Claude Code

# User-role entries that the tool generates itself, not the human.
SYSTEM_PREFIXES = ("<command-name>", "<command-message>", "<command-args>", "<local-command-",
                   "<system-reminder>", "<bash-input>", "<bash-stdout>", "<bash-stderr>",
                   "<task-notification>", "<user-memory-input>", "Caveat: The messages below")
REPLY_MARKER = re.compile(r"^<!--\s*reply\s*\d+\s*-->\s*")
INTERRUPT = "[Request interrupted by user"
CLASSIFIER_MARKER = "[context-user-classifier]"  # Context-User's own headless calls; never study data
PREV_CHARS = 600


def _claude_text(content) -> str | None:
    """Return the typed text of a user message, or None for tool results and system entries."""
    if isinstance(content, str):
        text = content
    else:
        parts = [b.get("text", "") for b in content if b.get("type") == "text"]
        if not parts:
            return None  # only tool_result blocks: not something the human typed
        text = "\n".join(parts)
    text = REPLY_MARKER.sub("", text.strip())  # "reply to this part of your answer" marker
    if not text or text.startswith(SYSTEM_PREFIXES) or CLASSIFIER_MARKER in text:
        return None
    return text


def _norm(text: str) -> str:
    return " ".join(REPLY_MARKER.sub("", text.strip()).split())


def read_claude(root: Path = CLAUDE_DIR) -> Iterator[Turn]:
    """Typed prompts, interruptions, and messages sent while the agent was working.

    Mid-turn messages are not stored as user entries: they only appear as
    queue "enqueue" operations, so we recover those whose text never shows
    up as a regular prompt.
    """
    for path in sorted(root.glob("*/*.jsonl")):
        found: list[tuple] = []   # (ts, session, cwd, text, kind, prev)
        queued: list[tuple] = []
        cwd = ""
        last_agent: dict[str, str] = {}
        with path.open(encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                cwd = entry.get("cwd", cwd)
                if entry.get("type") == "queue-operation" and entry.get("operation") == "enqueue":
                    text = entry.get("content")
                    if isinstance(text, str) and text.strip() and CLASSIFIER_MARKER not in text:
                        session = entry.get("sessionId", path.stem)
                        queued.append((_parse_ts(entry.get("timestamp")), session, text,
                                       last_agent.get(session, "")))
                    continue
                if entry.get("type") == "assistant" and not entry.get("isSidechain"):
                    content = entry.get("message", {}).get("content")
                    said = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"] \
                        if isinstance(content, list) else []
                    if said:
                        last_agent[entry.get("sessionId", path.stem)] = "\n".join(said)[-PREV_CHARS:]
                    continue
                if entry.get("type") != "user" or entry.get("isSidechain") or entry.get("isMeta"):
                    continue
                text = _claude_text(entry.get("message", {}).get("content", ""))
                if text is None:
                    continue
                session = entry.get("sessionId", path.stem)
                kind = "interrupt" if text.startswith(INTERRUPT) else "prompt"
                found.append((_parse_ts(entry.get("timestamp")), session,
                              entry.get("cwd", cwd), text, kind, last_agent.get(session, "")))
        seen = {_norm(t[3]) for t in found}
        for ts, session, text, prev in queued:
            clean = REPLY_MARKER.sub("", text.strip())
            if _norm(clean) not in seen and not clean.startswith(SYSTEM_PREFIXES):
                found.append((ts, session, cwd, clean, "midturn", prev))
                seen.add(_norm(clean))
        epoch = datetime.min.replace(tzinfo=timezone.utc)
        found.sort(key=lambda t: t[0] or epoch)
        index: dict[str, int] = {}
        for ts, session, cwd_, text, kind, prev in found:
            i = index.get(session, 0)
            yield Turn("claude", session, cwd_, ts, i, text, kind, prev)
            index[session] = i + 1


@dataclass
class ToolUse:
    """One tool call made by the agent (Claude Code only)."""

    session: str
    ts: datetime | None
    name: str     # e.g. "Edit", "Write", "Read", "Skill"
    input: dict


EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def read_claude_tools(root: Path = CLAUDE_DIR) -> Iterator[ToolUse]:
    for path in sorted(root.glob("*/*.jsonl")):
        with path.open(encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("type") != "assistant" or entry.get("isSidechain"):
                    continue
                content = entry.get("message", {}).get("content")
                if not isinstance(content, list):
                    continue
                for block in content:
                    if block.get("type") == "tool_use":
                        yield ToolUse(entry.get("sessionId", path.stem), _parse_ts(entry.get("timestamp")),
                                      block.get("name", ""), block.get("input") or {})


# --------------------------------------------------------------------- Cursor

def _open_copy(db: Path) -> sqlite3.Connection:
    """Cursor keeps its database open, so we read a temporary copy."""
    tmp = Path(tempfile.mkdtemp()) / db.name
    shutil.copy2(db, tmp)
    return sqlite3.connect(tmp)


def read_cursor(root: Path = CURSOR_DIR) -> Iterator[Turn]:
    """Read Cursor chat/composer prompts from its global SQLite store.

    Cursor's storage format is undocumented and changes between versions.
    We support the two layouts seen in 2025-26 builds:
      * composerData:<id>  -> {"conversation": [{"type": 1, "text": ...}, ...]}
      * bubbleId:<composer>:<bubble> -> {"type": 1, "text": ...}
    Run `cu doctor` to check what is found on your machine.
    """
    db = root / "globalStorage" / "state.vscdb"
    if not db.exists():
        return
    con = _open_copy(db)
    try:
        rows = con.execute(
            "SELECT key, value FROM cursorDiskKV "
            "WHERE key LIKE 'composerData:%' OR key LIKE 'bubbleId:%'"
        ).fetchall()
    except sqlite3.OperationalError:
        return
    finally:
        con.close()

    composers: dict[str, dict] = {}
    bubbles: dict[str, list[dict]] = {}
    for key, value in rows:
        try:
            data = json.loads(value) if value else None
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(data, dict):
            continue
        parts = key.split(":")
        if parts[0] == "composerData":
            composers[parts[1]] = data
        elif len(parts) >= 3:
            bubbles.setdefault(parts[1], []).append(data)

    for cid in sorted(set(composers) | set(bubbles)):
        meta = composers.get(cid, {})
        messages = meta.get("conversation") or bubbles.get(cid, [])
        base_ts = _parse_ts(meta.get("createdAt"))
        index = 0
        for msg in messages:
            if msg.get("type") != 1:  # 1 = user, 2 = assistant
                continue
            text = (msg.get("text") or "").strip()
            if not text:
                continue
            ts = _parse_ts(msg.get("createdAt") or (msg.get("timingInfo") or {}).get("clientStartTime")) or base_ts
            yield Turn("cursor", cid, meta.get("workspace", ""), ts, index, text)
            index += 1


# ------------------------------------------------------------- claude.ai export

def _chat_text(msg: dict) -> str:
    """Text of one message in a claude.ai export (plain `text`, or `content` blocks)."""
    if isinstance(msg.get("content"), list):
        parts = [b.get("text", "") for b in msg["content"] if isinstance(b, dict) and b.get("type") == "text"]
        if any(parts):
            return "\n".join(parts).strip()
    return str(msg.get("text") or "").strip()


def _chatgpt_thread(conv: dict) -> list[dict]:
    """The visible thread of a ChatGPT conversation, oldest first.

    ChatGPT stores a tree (regenerated and edited messages are branches);
    the thread the user ended on runs from `current_node` up to the root.
    """
    mapping = conv.get("mapping") or {}
    node, out, seen = conv.get("current_node"), [], set()
    while node and node in mapping and node not in seen:
        seen.add(node)
        msg = (mapping[node] or {}).get("message")
        if msg:
            out.append(msg)
        node = mapping[node].get("parent")
    out.reverse()
    messages = []
    for m in out:
        role = (m.get("author") or {}).get("role")
        content = m.get("content") or {}
        parts = [x for x in content.get("parts") or [] if isinstance(x, str)]
        text = "\n".join(parts).strip()
        if role in ("user", "assistant") and text and content.get("content_type", "text") == "text":
            ts = m.get("create_time")
            messages.append({"sender": "human" if role == "user" else "assistant", "text": text,
                             "created_at": ts * 1000 if isinstance(ts, (int, float)) else ts})
    return messages


def read_chat_export(path: Path) -> tuple[list[Turn], list[tuple]]:
    """Turns and assistant replies from a chat export (conversations.json).

    Works with both claude.ai (Settings → Privacy → Export data) and ChatGPT
    (Settings → Data controls → Export data) exports: unzip and pass the
    conversations.json. Returns (turns, replies) where replies are
    (session, ts, text) for draft detection.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    turns: list[Turn] = []
    replies: list[tuple] = []
    for conv in data if isinstance(data, list) else data.get("conversations", []):
        if "mapping" in conv:  # ChatGPT
            conv = {"uuid": conv.get("conversation_id") or conv.get("id") or conv.get("title", ""),
                    "chat_messages": _chatgpt_thread(conv), "source": "chatgpt"}
        session = str(conv.get("uuid") or conv.get("id") or conv.get("name", ""))
        prev, index = "", 0
        for msg in conv.get("chat_messages") or conv.get("messages") or []:
            text = _chat_text(msg)
            ts = _parse_ts(msg.get("created_at"))
            if not text:
                continue
            if msg.get("sender") in ("assistant", "model"):
                prev = text[-PREV_CHARS:]
                replies.append((session, ts, text))
            elif msg.get("sender") in ("human", "user"):
                turns.append(Turn(conv.get("source", "claude.ai"), session, "", ts, index,
                                  REPLY_MARKER.sub("", text), "prompt", prev))
                index += 1
    return turns, replies


CURSOR_TS = re.compile(r"<timestamp>(.*?)</timestamp>", re.S)
CODEX_SKIP_PREFIXES = ("<environment_context>", "<app-context>", "<permissions instructions>",
                       "<external_codex_apps", "The following is the Codex agent history",
                       # AGENTS.md / user instructions are logged as a user message; without this the person's real
                       # first message gets index 1 and is never offered as a replay task.
                       "<user_instructions>", "# AGENTS.md instructions")


def _cursor_transcript_ts(text: str):
    match = CURSOR_TS.search(text or "")
    if not match:
        return None
    raw = re.sub(r"\s*\((UTC|GMT)[^)]*\)\s*$", "", match.group(1).strip())
    for fmt in ("%A, %b %d, %Y, %I:%M %p", "%A, %B %d, %Y, %I:%M %p"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def read_cursor_transcripts(root: Path = CURSOR_TRANSCRIPTS_DIR) -> Iterator[Turn]:
    """User turns from Cursor agent-transcript JSONL files (~/.cursor/projects).

    This is the on-disk transcript layout, distinct from read_cursor()'s
    undocumented SQLite store. Subagent transcripts are skipped.
    """
    for path in sorted(root.glob("*/agent-transcripts/*/*.jsonl")):
        if "subagents" in path.parts:
            continue
        session = path.stem
        index, prev = 0, ""
        with path.open(encoding="utf-8", errors="ignore") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                content = (entry.get("message") or {}).get("content") or []
                texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
                if entry.get("role") == "assistant":
                    if texts:
                        prev = "\n".join(texts)[-600:]
                    continue
                if entry.get("role") != "user" or not texts:
                    continue
                raw = "\n".join(texts)
                match = re.search(r"<user_query>(.*?)</user_query>", raw, flags=re.S)
                text = (match.group(1) if match else raw).strip()
                if not text or text.startswith(SYSTEM_PREFIXES):
                    continue
                yield Turn("cursor", session, "", _cursor_transcript_ts(raw), index, text, "prompt", prev)
                index += 1


def read_codex(root: Path = CODEX_DIR) -> Iterator[Turn]:
    """User turns from Codex rollout JSONL files (~/.codex/sessions/**/rollout-*.jsonl)."""
    for path in sorted(root.rglob("rollout-*.jsonl")):
        session, cwd, index, prev = path.stem, "", 0, ""
        with path.open(encoding="utf-8", errors="ignore") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                payload = entry.get("payload") or {}
                if entry.get("type") == "session_meta":
                    session = payload.get("session_id") or payload.get("id") or session
                    cwd = payload.get("cwd", cwd)
                    continue
                if entry.get("type") != "response_item" or payload.get("type") != "message":
                    continue
                parts = [b.get("text", "") for b in payload.get("content") or []
                         if isinstance(b, dict) and b.get("type") in ("input_text", "output_text", "text")]
                text = "\n".join(p for p in parts if p).strip()
                if payload.get("role") == "assistant":
                    if text:
                        prev = text[-600:]
                    continue
                if payload.get("role") != "user" or not text:
                    continue
                if text.startswith(CODEX_SKIP_PREFIXES) or "<environment_context>" in text[:200]:
                    continue
                yield Turn("codex", session, cwd, _parse_ts(entry.get("timestamp")), index, text, "prompt", prev)
                index += 1


def read_all(project: str | None = None, sources=("claude", "cursor"), chat_export=None) -> list[Turn]:
    """All turns, oldest first. `chat_export` is one path or a list of paths."""
    turns: list[Turn] = []
    for path in ([chat_export] if isinstance(chat_export, (str, Path)) else chat_export or []):
        turns += read_chat_export(path)[0]
    if "claude" in sources:
        turns += read_claude()
    if "cursor" in sources:
        turns += read_cursor()
    if "cursor-transcripts" in sources:
        turns += read_cursor_transcripts()
    if "codex" in sources:
        turns += read_codex()
    if project:
        turns = [t for t in turns if project in t.project or t.source in ("cursor", "claude.ai", "chatgpt") and not t.project]
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    turns.sort(key=lambda t: (t.ts or epoch, t.session, t.index))
    return turns
