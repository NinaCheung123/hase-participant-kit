# Common Task Pack (organiser-issued)

The organiser sets these tasks. Participants do not choose or edit them.

## Design rule: no shared background needed

Common tasks must work for everyone in the room, whatever their personal
projects are. So each common task carries **everything needed inside the
prompt** — a short text, a scenario, or a claim to inspect. Nobody needs
crypto, database, or any other specialist knowledge to judge the answers.

What the common tasks test instead is what almost every framework contains,
because skills fall into a few kinds:

| Skill kind | What it looks like in an answer |
|---|---|
| Communication | Clear structure, plain language, right length, conclusion first |
| Depth of answer | Reasoning shown, trade-offs named, not just a conclusion |
| Verification habit | Wrong vs unverified kept apart; overclaims flagged |
| Working style | Follows the format and limits given in the prompt |

Domain knowledge is tested only by the personal replay tasks (below), where
each participant judges their own field. Crypto tasks, for example, belong
there — never in the common set.

A second source of common tasks is the course itself: material every
participant has covered (for HASE: the lectures and set papers). One such
task is included as T4. If you reuse this pack for another group, swap T4
for that group's shared material.

The surface prompt is identical for everyone and for all three conditions.
It never mentions any principle — if it did, the framework would have nothing to add.

## How one task fits different people's rules

Scoring has two layers:

1. **Core rubric (same for everyone, below).** Decides whether an answer is correct and complete at all. This is what makes results comparable across participants.
2. **Personal checklist (yours only, written before you see any answer).** Take your confirmed principles and translate each one that is relevant to this task type into one observable item. Example translations:

| Your confirmed principle (example) | Checklist item for a checking task |
|---|---|
| Verify sources before claiming | Answer separates "wrong" from "not verified" |
| Show reasoning, not only conclusions | Answer says why each flagged claim fails |
| Plain language, conclusion first | A non-specialist could follow the answer |

Principles that do not apply to a task type are left out of that task's checklist. Do not force all of them onto every task. If none of your principles apply to a task, expect a tie — that tells you where your framework has no coverage.

The personal checklist never changes the ranking. Rankings are locked in Stage 1; the checklist is used afterwards to explain which items separated the winner.

## The common tasks

### T1 — Communication and depth (all material supplied)

> Below are rough notes from a team meeting. Turn them into a short decision note for people who were not there: what was decided, what is still open, and what happens next. At most 180 words.
>
> "ok so migration — Sara said staging broke twice last week, not sure why. Tom: we could freeze features for two weeks, nobody loved that. Priya has a script that rolls back in like 4 minutes, needs testing though. Budget: cloud bill went up 30%, finance noticed. We said maybe move the log storage first, it's the biggest chunk. No date set. Alex to look at staging logs when back from leave (Thursday). Someone should own the rollback test, not assigned."

Core rubric: the migration/log-storage direction, the undecided freeze, and the unassigned rollback test are all visible; invented facts (dates, owners, decisions not taken) count against; within the word limit.

### T2 — Verification habit (self-contained; nothing to look up)

> Review the claim below. List every statement that is wrong, unsupported, or overgeneralised, and say for each one: is it wrong, or just not proven by what is given?
>
> "We gave our team of 4 developers an AI coding tool for one week. Afterwards, 3 of them said they felt faster, so the tool clearly makes developers about 25% more productive. This shows AI tools will improve productivity in any software team, especially for experienced developers, who benefit the most."

Core rubric: catches that feelings are not measured productivity; that no 25% figure can come from this data; that 4 people for one week cannot support "any team"; that nothing here measures experienced developers specifically; keeps "wrong" apart from "not proven".

### T3 — Depth and communication (scenario supplied)

> A course project team has 3 weeks left. One member wants to add a feature users asked for; another wants to stop adding features and fix the evaluation, which currently uses 5 test cases that everyone passes. They ask you: what should we do, and why? Answer in at most 200 words, and state what information would change your advice.

Core rubric: engages with the actual tension (a passing-everything evaluation cannot show the feature helps); gives a recommendation with reasoning, not only pros and cons; names information that would change it; within the word limit.

### T4 — Course-shared knowledge (HASE cohort only)

> Based only on the excerpt below, answer: (1) What did the study actually measure? (2) What is one thing it does **not** show? (3) A manager reads this and says "so AI tools are bad for experienced developers." Is that a fair reading? Why?
>
> Excerpt: "In a randomised study with 16 experienced open-source developers, participants completed tasks from their own projects. With early-2025 AI tools, they took 19% longer on average than without. Before the study, they had expected AI to speed them up by 24%, and after the study they still believed it had sped them up by 20%."

Core rubric: measured = task completion time on their own projects; not shown = anything beyond this tool generation / these developers / these tasks (for example long-term effects, or other populations); the manager's reading is too strong, and the belief–measurement gap is named.

## Control task (optional, organiser decides)

Add one task with a single correct answer and no room for judgement, for example a short factual computation. All three conditions should tie. If they do not, something other than the framework is driving your rankings.

## Alternative: tasks replayed from your own recent chats (temporal holdout)

Instead of — or alongside — the common tasks above, test tasks can be replayed from your own history:

1. **Generation window:** by default the 30 days before the most recent 14, e.g.
   `python3 study.py prepare --cursor-logs` (change with `--days` and `--exclude-recent-days`; adjust the source flag to your tool). Build and freeze the framework from this window only.
2. **Test window:** the most recent 14 days by default. List candidate tasks with
   `python3 study.py tasks --cursor-logs --days 14` (choose your own window with `--days`). This exports only the **opening prompt**
   of each recent chat. The original answers, and everything you said afterwards, are never exported.
3. **Screen the candidates yourself.** Keep only tasks that are self-contained (the opening prompt
   makes sense on its own), in a domain you can judge, and not a continuation of an earlier chat.
   Delete the rest. Do not prefer chats where you remember correcting the assistant — include
   ordinary chats too, or the test is rigged in the framework's favour.
4. **Replay:** run each kept opening prompt fresh under A / B / C and compare as usual.

Eligibility and fallbacks, so this works for every participant:

| Situation | Rule |
|---|---|
| At least ~4 months of history, 2+ chats in each window | Use 3 months generation / 1 month test as above |
| Less history | Split by proportion instead of calendar: oldest 75% of chats generate, newest 25% test |
| Too little history for either | Use the common tasks above; report that the replay variant was not available |

Known limits, to state in the report: you may remember the original chats, so blinding is weaker than with common tasks; and principles can drift — if a recent chat reverses an older rule, the structured generation step already drops the outdated one, because generation sees only the earlier window and the reversal is part of what the test measures.

## Running the tasks

`python3 study.py tasks` writes the three common tasks (T1 to T3; `--hase` adds T4, `--control` adds the control task) and up to two replay candidates from your own recent chats. `python3 study.py answers` then answers every task three ways with your own Claude login: **A** no skills, **B** everything the direct method generated, **C** everything the structured method generated (you have not seen any item yet, so the comparison stays blind). The surface prompt is identical; only the skills text before it differs. `python3 study.py compare` runs the blind judgement (checklist first, then best / worst / tie / skip), and `choose` the choice between the two sets. Conditions B and C are the two generation methods; there is no generic-principles condition, so the study cannot say whether structure alone would be enough (stated as a limitation).

## Cost rules (keep this cheap for every participant)

- **Default set: the 3 common tasks plus at most 2 replay tasks.** More tasks add little; ranking data saturates fast.
- **Answer length is capped** in the common task prompts (180 to 200 words) and by `At most 300 words.` for replay tasks.
- **Same model for all conditions** (default `sonnet`, option `--model`).
- Generation is capped at about 48 messages and three model calls; do not widen it to be thorough. A longer *window* costs nothing, only the sample sent does.
