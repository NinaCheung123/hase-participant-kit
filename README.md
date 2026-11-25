# Check skills and principles generated from your AI chats

Use this kit at a time you choose, about 35 to 50 minutes in total. It generates two sets of suggestions from your own recent messages, writes answers to a few tasks with and without them, and asks you to compare the answers, keep or delete each suggestion, and choose between the two sets. A *skill* is a short, reusable instruction for how an assistant should handle one kind of task; a *principle* is a judgement rule behind several tasks (how you decide, what counts as good).

You need a terminal, Python 3, and the CLI for the AI you use. With Codex history, use the Codex CLI signed in to your own ChatGPT account (`codex login status`). With Claude Code history, sign in to your own Claude Code account. Generation and answers send the selected text to that service and use your regular allowance. Extraction and judging run on your computer. Before using your own history, read the course consent form that covers your service.

## Get the kit

Unzip the kit provided by the organiser. Open a terminal in the folder directly containing `study.py`, and run the commands one at a time.

**Using Codex?** Follow [Codex quick start](Codex_Quick_Start.txt) for local setup, sample review and generation with your own Codex login.

## 1. Prepare

Open a terminal in this folder. Use one of these commands, depending on where you keep your chats.

```sh
python3 study.py prepare --claude-logs                       # Claude Code logs on this computer
python3 study.py prepare --codex-logs                        # Codex rollout logs
```

The kit reads your history on your computer and picks **about 5 days** from the 30 days before your most recent 14 days (those 14 days are kept as the test window for step 2). It prefers busy days, one per week where possible, and skips days on which many messages touch sensitive topics; it prints the dates it used. From each day it takes about 10 of your messages **in the order you sent them**, short or correcting ones first. For those it also attaches the last 300 characters of what the assistant said just before, so a correction such as "shorter" can be understood; no other assistant text is read. Change the number of days with `--n-days N`, choose days yourself with `--dates 2026-11-03,2026-11-10`, and move the window with `--days N` and `--exclude-recent-days N`. A longer window costs nothing extra: history is read on your computer and only the selected messages are sent.

**Automatic filter.** Before anything is selected, the kit masks links, file paths, emails and long numbers, drops pasted blocks, and drops messages about sensitive topics (health, family, money, housing and visa, job search, legal; English, Chinese and German word lists). It prints how many messages each rule dropped, never the messages. The filter is a general rule, not a guarantee: it does not recognise names or other details. If you want to read the selected messages first, open `history.review.json`. The Codex route always requires review. For the Claude route, add `--review` to require it (then `generate` needs `--confirm-reviewed`), and `--block words.txt` to drop your own words (one per line).

48 messages is a recommendation, not a rule: it is enough to see what you repeat and keeps generation to roughly 20k to 35k tokens (an estimate; read `/usage` before and after). `--max-messages N` goes up to 150, but more messages cost more and add little. If the sample has fewer than two chats, repeat with `--days 90 --output wider.review.json` and pass `--history wider.review.json` to the next step.

## 2. Generate

```sh
python3 study.py tasks --claude-logs      # same source flag as above; --days N sets the test window (default 14)
python3 study.py ask                      # optional: type a question of your own, added as the last task
python3 study.py generate
```

Run the commands **one at a time** and wait for the `Next:` line each prints; do not paste several at once.

`generate` calls your selected AI three times with your own login (a few minutes at most; rerun to resume if interrupted). Two methods write up to five items each, mixed together and unlabelled.

`tasks` writes `tasks.review.json` and lists the tasks: four common tasks set by the organisers (leave them as they are; T4 is the course task, `--no-cohort-task` leaves it out), and up to two openings of your own recent chats, picked at random and masked. Open the file and delete any of your own tasks you would not want sent to your AI account or cannot judge. Without a history source, or with too little history, only the common tasks are used. `ask` is optional: it asks for one question you would really ask an AI and adds it as the last task (task O1; run it again to replace it, press Enter on an empty line to cancel).

## 3. Answers, then compare

```sh
python3 study.py answers     # about 2 to 5 minutes of waiting, roughly 8k to 14k tokens (estimate)
```

`answers` writes each task three ways: without skills, with everything the first method generated, and with everything the second method generated. You have not seen any item yet, so the comparison stays blind.

**Option A — terminal**

```sh
python3 study.py compare     # judge the answers blind
python3 study.py confirm     # keep or delete each item
python3 study.py choose      # which set (X or Y) to keep and build on
```

**Option B — browser (same judgements, easier to read long answers)**

```sh
python3 study.py web         # writes my-study/web_session.json and opens study-web/index.html
```

Load `web_session.json` in the page (or load `eval_answers.local.json`, `cards.local.json`, and `key.share.json`). Complete compare → keep/delete → choose, download the three `.share.csv` files into `my-study/`, then continue with `bundle`. Nothing is uploaded; the page runs only on your computer.

In either path: pick best and worst, or `tie` / `skip`; say how clear it was (clear, slight, or forced); optional one-line reason. No numeric ratings.

## 4. Export kept items (after confirm / choose)

```sh
python3 study.py export      # your kept items as ready-to-use files in my-study/my-skills/
```

If you used the terminal path, `confirm` and `choose` already wrote the share files. Editing items is optional. In `choose` (or the web page) you answer `x`, `y`, `same` or `neither`, with a one-line reason. `export` writes `principles.md` and `skills/*/SKILL.md`.

## 5. Return your files (upload, no email)

```sh
python3 study.py bundle      # writes my-study/study_files.zip
```

The zip holds only **`decisions.share.csv`**, **`compare.share.csv`**, **`choice.share.csv`** and **`key.share.json`**. Each step prints the path and an `open` command for its file. Open each file first and delete any row you do not want to share (run `bundle` again afterwards), then upload the zip at https://drive.switch.ch/index.php/s/DpdfHjo9pmGMpdJ (no login; the page is upload only, so you cannot see other files). Your file is named with your random participant code, not your name. The drop folder records only your connection, not who you are. After `choose` the tool tells you which method made which set; until then do not open the key, which says the same. The files contain a random participant code, item types, categories, conversation counts, your decisions, your best and worst picks per task, your set choice and the short reasons you wrote; never the text of any item, task or answer. Keep the history, items, tasks and answers private. If you decide not to take part, you can stop and keep the files on your own computer.


## Optional: judge in the browser instead of typing

After `answers`, you can do `compare`, `confirm` and `choose` on a web page instead of in the terminal. Nothing is uploaded; the page runs from a file on your computer.

```sh
python3 study.py web            # writes web_session.json and opens the page; load that file on the page
python3 study.py web-import     # after the page has saved web_results.json
python3 study.py export
python3 study.py bundle
```

Do not mix the two ways for the same study folder: use either the terminal commands or the page.

## Optional offline walkthrough

```sh
python3 study.py demo
python3 study.py confirm --folder demo-study
```

The demo uses fictional messages and makes no model calls. Its output is marked as demo data.
