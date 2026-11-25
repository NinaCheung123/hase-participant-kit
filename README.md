# Check skills and principles generated from your AI chats

About 35 to 50 minutes, at a time you choose. The kit picks a small sample of your past messages, and **you decide which of them may be sent**. Your own AI account then writes two sets of suggestions from them and answers a few tasks with and without them. You compare the answers without knowing which used the suggestions, then look at the suggestions and say which ones fit you.

A *skill* is a short, reusable instruction for how an assistant should handle one kind of task; a *principle* is a judgement rule behind several tasks (how you decide, what counts as good).

**You need:** a terminal, Python 3.9 or newer, and the command-line tool of the AI whose history you use, signed in to your own account: Claude Code (`claude`) or Codex (`codex login status`). Read the consent form first.

## Get the kit

Download it from https://github.com/NinaCheung123/hase-participant-kit (green Code button, Download ZIP, unzip), or `git clone https://github.com/NinaCheung123/hase-participant-kit.git`. The source is public, so you can read exactly what it does. Open a terminal in the folder that contains `study.py`.

## What the code does with your history

You are letting a program read your AI history, so here is exactly what it does. All of it is in three files you can read: `study.py`, `webapp.py` and `context_user/sources.py`.

| Step | What happens | Where |
|---|---|---|
| Read | Reads the log files your AI tool already keeps on your computer: `~/.claude/projects` (Claude Code) or `~/.codex/sessions` (Codex). Read only; it never changes them. | your computer |
| Pick | Keeps only messages **you typed**, from about 5 days. For short corrections such as "shorter", it also keeps the last 300 characters of the assistant's reply before them. No other assistant text, no files, no code output. | your computer |
| Filter | Masks links, file paths, emails and long numbers; drops pasted blocks and messages on sensitive topics. | your computer |
| You decide | Shows you every picked message and own-chat task. Only what you leave ticked can be sent. | your computer |
| Send | Sends the approved messages to **your own** account through your own `claude` or `codex` command-line tool, with its tools, web search and file access switched off, and without saving a chat. This is the only time anything leaves your computer. | your AI account |
| Return | Writes `study_files.zip` with your choices and short reasons only. The program never uploads anything; you upload the zip yourself. | your computer → you upload it |

The program uses no network library at all. It starts only two outside programs: your `claude` or `codex` tool, and your system's "open folder" command. The browser page is served from your own computer (`127.0.0.1`) with a random password, so other websites cannot reach it. Everything it creates stays in this folder; delete the folder to remove all of it.

## Recommended: do everything in your browser

```sh
python3 study.py web --codex-logs      # if you use Codex
python3 study.py web --claude-logs     # if you use Claude Code
```

Your browser opens a page that runs only on your computer (address `127.0.0.1`, nothing is uploaded). Keep the terminal open while you work. The page takes you through six steps:

1. **Check what is sent.** Every selected message and every task from your own chats is listed. Untick anything you do not want sent; optionally add one question of your own.
2. **Generate.** Your AI account writes two sets of suggestions and answers each task three ways (5 to 10 minutes, no input needed).
3. **Compare answers.** For each task, pick the answer you would most and least like to receive, or say you cannot tell. Then say what made the difference and why in one line.
4. **Your skills.** Now you see the suggestions for the first time: keep, edit or delete each one, and answer two short questions.
5. **Choose a set.** Which of the two sets would you keep and build on, and why.
6. **Done.** The page shows which method made which set and where your files are. Upload `my-study/study_files.zip` at https://drive.switch.ch/index.php/s/DpdfHjo9pmGMpdJ (no login).

If you close the page or something stops, run the same command again: your progress is kept.

## The same in the terminal

```sh
python3 study.py prepare --codex-logs     # or --claude-logs; picks the sample, sends nothing
python3 study.py tasks --codex-logs       # the tasks; sends nothing
python3 study.py ask                      # optional: one question of your own
python3 study.py review                   # you see every message and own-chat task and decide what may be sent
python3 study.py generate                 # two sets of suggestions (sends only what you approved)
python3 study.py answers                  # each task answered three ways
python3 study.py compare                  # judge the answers blind
python3 study.py confirm                  # keep, edit or delete each suggestion; two short questions
python3 study.py choose                   # which set to keep
python3 study.py export                   # your kept suggestions as files in my-study/my-skills/
python3 study.py bundle                   # my-study/study_files.zip to upload
```

Run them one at a time and wait for the `Next:` line. `generate` and `answers` refuse to send anything you have not approved in `review`; if you change the sample file afterwards, run `review` again.

## What is selected, and how

The kit reads your history on your computer. It takes the most recent 14 days as the **test window** (tasks from your own chats come only from chats started there) and picks **about 5 days** from the 30 days before it for the sample (busy days, one per week where possible, skipping days where many messages touch sensitive topics). From each day it takes about 10 of your messages in the order you sent them, short or correcting ones first. For those it attaches the last 300 characters of the assistant's previous reply, so a correction such as "shorter" makes sense; no other assistant text is read. Because the two windows do not overlap, no task comes from a chat the suggestions were written from.

**Automatic filter, before you review.** Links, file paths, emails and long numbers are masked; pasted blocks are dropped; messages about health, family, money, housing and visa, job search or legal matters are dropped (English, Chinese and German word lists). Only counts are printed. The filter does not recognise names or other details, which is why you review every message.

Options for `prepare`: `--n-days N`, `--dates 2026-11-03,2026-11-10`, `--days N` (length of the sample window, default 30), `--exclude-recent-days N` (test window, default 14), `--max-messages N` (default 48, at most 150), `--block words.txt` (your own words to drop). In `tasks`, `--days N` is the test window (default 14).

## Cost

Rough estimates; check your usage before and after. Generation: about 20k to 35k tokens for 48 messages. Answers: each task is answered three times, about 0.7k to 1.2k tokens per answer, so 6 tasks take about 13k to 22k tokens and 8 tasks about 17k to 29k.

## What you return

Only `study_files.zip`, which holds `compare.share.csv`, `decisions.share.csv`, `choice.share.csv` and `key.share.json`: a random participant code, which answer you preferred per task with your reason tags and one-line reasons, your keep/edit/delete decisions and short comments, your set choice and answers to the closing questions, item types, categories and counts. **Never** the text of your messages, tasks, answers or suggestions. Open the files first and delete any row you do not want to share (then run `python3 study.py bundle` again). If you decide not to take part, stop at any point and keep everything on your computer.

## Optional offline walkthrough

```sh
python3 study.py demo
python3 study.py confirm --folder demo-study
```

The demo uses fictional messages and makes no model calls.
