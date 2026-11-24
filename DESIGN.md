# Participant flow design

The full, current design (claim, flow, methods, tasks, privacy, what is shared, threats) is in `study/FINAL_STUDY_DESIGN.md` of the project. This file records only why the kit is a terminal tool.

## Decision: terminal commands, not a web UI

Participants are engineers. A resumable terminal flow needs no server, no account and no upload, so chat text never leaves the computer. A web UI would add hosting, identity and data protection work this study does not need. The trade-off is accepted: less pretty, far less risk. Each step is a command plus a local file, so the same steps can also be driven by an assistant.

## Order of steps

`prepare`, `tasks`, (`ask`), `generate`, `answers`, `compare` (blind), `confirm`, `choose`, `export`, `bundle`. `confirm` and `choose` refuse to run until `compare` is done. Every step prints what is happening and what comes next.

## What leaves the computer

Only the four share files (`decisions.share.csv`, `compare.share.csv`, `choice.share.csv`, `key.share.json`), which the participant opens, may edit, and emails. They hold ids, types, decisions, picks, clarity, similarity scores, and the short reasons the participant wrote, never the text of items, tasks or answers.

## Open risks

- Cursor's store is undocumented; the kit reads the on-disk agent transcripts (`~/.cursor/projects`). Codex rollout files are parsed defensively. Both and the Claude.ai or ChatGPT export importers are not re-tested with the current sampling.
- Self-judging is not fully blind: participants may recognise their own style. This is recorded as a threat.
