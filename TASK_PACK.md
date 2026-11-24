# Task pack

The organiser sets these tasks. Participants do not choose or edit them (they may delete their own replay tasks and add one question of their own). The rubric lines are design notes for the organiser; the tool never shows them to participants.

## Design rules

1. **Everything needed is in the prompt.** No specialist knowledge or shared background is assumed, so the tasks work for everyone.
2. **Prompts never name a principle.** Otherwise the skills would have nothing to add.
3. **The surface prompt is identical in all three conditions** (none, direct set, structured set). Only a text prefix with the items differs.
4. **The participant judges which answer they would rather receive.** No rubric or checklist is shown, so nothing steers the judgement.
5. **Ties and skips are allowed.** Common tasks give personal skills little to add, so ties are expected and reported as a finding.
6. **Word limits** keep answers short (T1 180, T2 150, T3 200, replay and own question 300). T4 has no limit.

## Tasks

### T1

> Below are rough notes from a team meeting. Turn them into a short decision note for people who were not there: what was decided, what is still open, and what happens next. At most 180 words.
> 
> "ok so migration — Sara said staging broke twice last week, not sure why. Tom: we could freeze features for two weeks, nobody loved that. Priya has a script that rolls back in like 4 minutes, needs testing though. Budget: cloud bill went up 30%, finance noticed. We said maybe move the log storage first, it's the biggest chunk. No date set. Alex to look at staging logs when back from leave (Thursday). Someone should own the rollback test, not assigned."

Design note: The migration/log-storage direction, the undecided freeze and the unassigned rollback test are all visible; invented facts (dates, owners, decisions not taken) count against; within 180 words.

### T2

> Review the claim below. List every statement that is wrong, unsupported, or overgeneralised, and say for each one: is it wrong, or just not proven by what is given? At most 150 words.
> 
> "We gave our team of 4 developers an AI coding tool for one week. Afterwards, 3 of them said they felt faster, so the tool clearly makes developers about 25% more productive. This shows AI tools will improve productivity in any software team, especially for experienced developers, who benefit the most."

Design note: Catches that feelings are not measured productivity; that no 25% figure can come from this data; that 4 people for one week cannot support "any team"; that nothing here measures experienced developers; keeps "wrong" apart from "not proven".

### T3

> A course project team has 3 weeks left. One member wants to add a feature users asked for; another wants to stop adding features and fix the evaluation, which currently uses 5 test cases that everyone passes. They ask you: what should we do, and why? Answer in at most 200 words, and state what information would change your advice.

Design note: Engages with the real tension (an evaluation everyone passes cannot show the feature helps); gives a recommendation with reasoning, not only pros and cons; names information that would change it; within 200 words.

### T4 (HASE cohort; `--no-cohort-task` leaves it out)

> Based only on the excerpt below, answer: (1) What did the study actually measure? (2) What is one thing it does not show? (3) A manager reads this and says "so AI tools are bad for experienced developers." Is that a fair reading? Why?
> 
> Excerpt: "In a randomised study with 16 experienced open-source developers, participants completed tasks from their own projects. With early-2025 AI tools, they took 19% longer on average than without. Before the study, they had expected AI to speed them up by 24%, and after the study they still believed it had sped them up by 20%."

Design note: Measured = task completion time on their own projects; not shown = anything beyond this tool generation, these developers or these tasks; the manager's reading is too strong and the belief-measurement gap is named.

### C1 (control, off by default; `tasks --control`)

> What is 17 times 23? Give the number only.

Design note: 391. All conditions should tie; if not, something other than the skills drives your picks.

## Replay and own tasks

Up to two **replay tasks** are openings of the participant's own recent chats (last 14 days, masked, 80 to 800 characters, no file references, random choice, not chosen for corrections). The participant may delete them before anything is sent; an opening that depends on context outside the prompt can be unfair, and one such task was marked a tie in the first full run. `ask` adds one **own question** (O1).

## Conditions

`answers` writes each task three ways with the participant's own Claude login: **A** no skills, **B** everything the direct method generated, **C** everything the structured method generated. The participant has not seen any item yet, so the comparison stays blind. There is no generic-principles condition, so the study cannot say whether structure alone would be enough (stated as a limitation).
