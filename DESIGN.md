# Participant Flow Design

## Decision: terminal wizard, not a web UI

Participants are engineers. A resumable terminal flow (the pattern `study.py` already uses) needs no server, no account, and no upload, so chat text never leaves the laptop. A web UI would add hosting, identity, and data-protection work the study does not need. The trade-off is accepted: less pretty, far less risk. The organiser's own AI assistant can also drive the same steps, because every step is a command plus a local file.

## Journey, step by step

| # | Step | What the participant sees | Likely problem | Design answer |
|---|---|---|---|---|
| 0 | Start | One command, estimated time, what will be shared | "How long / what leaves my laptop?" | Opening text states time and the two share files before anything runs |
| 1 | Import | A source menu in words: Claude Code / Cursor / Codex / ChatGPT or Claude.ai export | Wrong folder, empty source, undocumented Cursor store | Each source is one `--flag`; empty result errors with the likely cause, never silently |
| 2 | Sampling | "Prepared N messages from M chats" | History is huge; pasted docs drown real corrections | User turns only, pastes stripped (`own_words`), max 48 messages / 8 per chat / last 7–14 days |
| 3 | Automatic filter | Counts of what was dropped per rule; `history.review.json` is there to read if wanted | Per-message review is too much work and people skip it | General rules (masking, sensitive-topic word lists in three languages, optional `--block` words); `--review` makes reading compulsory (`--confirm-reviewed` before any model call). The filter does not catch names; stated in the consent form |
| 4 | Generation | "Step 1 of 3…" with resume on rerun | Usage limits, interruption, timeout | Checkpoints per stage; rerunning resumes; generation is the only step that spends model allowance, and the guide says so up front |
| 5 | Confirm skills | Cards one at a time: keep / edit / delete / add | Rubber-stamping everything | A card needs support in 2+ chats to count as a principle; kept/edited/deleted/added counts are recorded |
| 6 | Freeze | Copy or zip of the assembled framework + freeze date | Silent edits during evaluation would invalidate it | Freeze is a dated snapshot (or hash); evaluation instructions forbid changing it |
| 7 | Produce answers | For each task: three fresh sessions, one per condition (A none, B generic, C personal) | Same task three times contaminates if done interactively in sequence | Produce first answers in parallel/isolated sessions from the same starting point; paste them into `eval_answers.local.json` |
| 8 | Compare answers | Answers shown as X / Y / Z, shuffled, no condition labels | Knowing which is "mine" biases judgement (halo) | Stage 1 is blinded and locked before anything is revealed; best, worst, below-threshold, one-sentence reason |
| 9 | Compare skills | Condition mapping revealed; three skill sets side by side | Rating scales drift between people and tasks | Direct choice only: "which set goes into your next task?" plus one reason. No numeric card rating in this stage |
| 10 | Return | `compare.share.csv` with `decisions.share.csv` and `choice.share.csv` | Accidentally sharing raw chats | Share files contain ids, conditions, choices, and reasons — never message or answer text. File names say `.share` vs `.local` |

> **Order in the final flow (see `study/FINAL_STUDY_DESIGN.md`):** prepare, tasks, generate, answers (using everything each method generated), compare (blind), confirm (keep or delete each item; edit and add optional), choose, export. Items are first seen after the answers are judged. Rows 5 to 9 above describe the same steps in the older order; the final design note takes precedence.

## How tasks are shown and answered

Tasks are local JSON (`eval_answers.local.json`), one object per task: `task_id`, optional task text, and the three answer texts the participant produced with their own AI under the three conditions. The compare command prints one task at a time, all three answers on screen together, and asks four short questions (below threshold? best? worst? one-sentence difference). That is the whole feedback burden per task.

## What the organiser receives

One CSV per participant: per task, the winning and losing **condition** (A/B/C), below-threshold marks, the one-sentence reasons, and the chosen skill-set condition. Aggregating across participants gives win counts per condition without anyone's chat text.

## Open risks

- Cursor's SQLite store is undocumented; the kit therefore reads the on-disk agent transcripts (`~/.cursor/projects`), which are plain JSONL. If a build changes that layout, import falls back to exported transcripts.
- Codex rollout format is parsed defensively (user `response_item` messages only, environment blocks skipped); other shapes are ignored rather than misread.
- Self-judging is not fully blind: participants may recognise their own framework's style. This is recorded as a threat, not hidden.
