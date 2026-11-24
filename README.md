# Check skills and principles generated from your AI chats

Use this kit at a time you choose, about 35 to 50 minutes in total. It generates two sets of suggestions from your own recent messages, writes answers to a few tasks with and without them, and asks you to compare the answers, keep or delete each suggestion, and choose between the two sets. A *skill* is a short, reusable instruction for how an assistant should handle one kind of task; a *principle* is a judgement rule behind several tasks (how you decide, what counts as good).

Before starting, read the course study information and consent form provided separately. You need a terminal, Python 3, and Claude Code signed in to your own account. Generating and answering send text to Claude through your own login and use some of your regular Claude allowance, so start when you have time and usage available. Everything else runs on your computer.

## Get the kit

Download it from https://github.com/NinaCheung123/hase-participant-kit (green Code button, then Download ZIP, then unzip), or run `git clone https://github.com/NinaCheung123/hase-participant-kit.git`. Open a terminal in that folder for every command below. The source is public, so you can read exactly what it does before running it.

## 1. Prepare

Open a terminal in this folder. Use one of these commands, depending on where you keep your chats.

```sh
python3 study.py prepare --claude-logs                       # Claude Code logs on this computer
python3 study.py prepare --cursor-logs                       # Cursor agent transcripts
python3 study.py prepare --codex-logs                        # Codex rollout logs
python3 study.py prepare --export /path/to/conversations.json   # unzipped Claude.ai or ChatGPT export
```

The kit samples about **48 of your messages** at random (at most eight per chat) from the 30 days before your most recent 14 days; those 14 days are kept as the test window for step 3. Change both with `--days N` and `--exclude-recent-days N`. A longer window costs nothing extra: history is read on your computer and only the sample is sent.

**Automatic filter.** Before anything is selected, the kit masks links, file paths, emails and long numbers, drops pasted blocks, and drops messages about sensitive topics (health, family, money, housing and visa, job search, legal; English, Chinese and German word lists). It prints how many messages each rule dropped, never the messages. The filter is a general rule, not a guarantee: it does not recognise names or other details. If you want to read the selected messages first, open `history.review.json` (it is exactly what will be sent). Add `--review` to make that step compulsory (then `generate` needs `--confirm-reviewed`), and `--block words.txt` to drop your own words (one per line).

48 messages is a recommendation, not a rule: it is enough to see what you repeat and keeps generation to roughly 20k to 35k tokens (an estimate; read `/usage` before and after). `--max-messages N` goes up to 150, but more messages cost more and add little. If the sample has fewer than two chats, repeat with `--days 90 --output wider.review.json` and pass `--history wider.review.json` to the next step.

## 2. Generate

```sh
python3 study.py tasks --claude-logs      # same source flag as above; --days N sets the test window (default 14)
python3 study.py generate
```

`generate` calls Claude three times with your own login (a few minutes at most; rerun to resume if interrupted). Two methods write up to five items each, mixed together and unlabelled.

`tasks` writes `tasks.review.json`: three common tasks set by the organisers (leave them as they are) and up to two openings of your own recent chats, picked at random and masked. Open the file and delete any of your own tasks you would not want sent to Claude or cannot judge. Without a history source, or with too little history, only the common tasks are used. HASE cohort: add `--hase` for task T4.

## 3. Answers, then compare

```sh
python3 study.py answers     # about 2 to 5 minutes of waiting, roughly 8k to 14k tokens (estimate)
python3 study.py compare     # write your checklist first, then judge the answers blind
```

`answers` writes each task three ways: without skills, with everything the first method generated, and with everything the second method generated. You have not seen any item yet, so the comparison stays blind.

In `compare`, for each task you first write up to three things a good answer must do for you (Enter to skip). You then see the answers in random order with no labels and pick the best and the worst, or say `tie` (cannot tell) or `skip` (not a fair test). Common tasks show a core rubric. Afterwards you mark which answers meet your checklist; this explains your ranking and never changes it. There are no numeric ratings.

## 4. Look at the items, keep or delete, choose

```sh
python3 study.py confirm     # now you see the items: keep or delete each (e = edit it first); add what was missed
python3 study.py choose      # which of the two sets (X or Y) would you take into your next task?
python3 study.py export      # your kept items as ready-to-use files in my-study/my-skills/
```

Keeping or deleting each item is the required part and takes a key per item. Editing and adding are optional. In `choose` you answer `x`, `y`, `same` or `neither`, with a one-line reason. `export` writes `principles.md` and `skills/*/SKILL.md`, ordinary text files you can edit later.

## 5. Return your files

```sh
python3 study.py bundle      # writes my-study/study_files.zip
```

The zip holds only **`decisions.share.csv`**, **`compare.share.csv`**, **`choice.share.csv`** and **`key.share.json`**. Open each file first and delete any row you do not want to share (run `bundle` again afterwards), then email the zip to yuwen.zhang@uzh.ch. Wait until you have chosen before opening the key, which says which method made which set. The files contain a random participant code, item types, categories, conversation counts, your decisions, your best and worst picks per task, checklist counts, your set choice and your one line reasons; never the text of any item, task, answer or checklist. Keep the history, items, tasks and answers private. If you decide not to take part, you can stop and keep the files on your own computer.

## Optional offline walkthrough

```sh
python3 study.py demo
python3 study.py confirm --folder demo-study
```

The demo uses fictional messages and makes no Claude calls. Its output is marked as demo data.
