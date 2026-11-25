"""Local web app for the whole study: one command, everything in the browser.

Runs only on 127.0.0.1 with a random token, uses the Python standard library only, and calls the same functions
as the terminal commands, so both write identical files. The browser never receives which answer or item came
from which method until the participant has made their choice.
"""
import argparse
import io
import json
import random
import secrets
import sys
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import study

PAGE = Path(__file__).resolve().parent / "study-web" / "index.html"
UPLOAD_URL = "https://drive.switch.ch/index.php/s/DpdfHjo9pmGMpdJ"


class ThreadOutput(io.TextIOBase):
    """sys.stdout replacement: text printed in a thread that registered a buffer goes there, the rest to the terminal."""

    def __init__(self, original):
        self.original, self.local = original, threading.local()

    def write(self, text):
        buffer = getattr(self.local, "buffer", None)
        if buffer is None:
            return self.original.write(text)
        buffer.append(text)
        return len(text)

    def flush(self):
        try:
            self.original.flush()
        except ValueError:     # the terminal stream was closed (only happens at interpreter exit or in tests)
            pass


OUT = ThreadOutput(sys.stdout)


def captured(fn, *args, buffer=None, **kwargs):
    """Run fn with its printed output collected (and returned)."""
    installed = sys.stdout is not OUT      # run() installs OUT for the server; elsewhere (tests) only for this call
    if installed:
        OUT.original, sys.stdout = sys.stdout, OUT
    lines = [] if buffer is None else buffer
    OUT.local.buffer = lines
    try:
        fn(*args, **kwargs)
    finally:
        OUT.local.buffer = None
        if installed:
            sys.stdout = OUT.original
    return "".join(lines)


class App:
    def __init__(self, workdir, folder, engine=None, source=None):
        self.dir, self.folder, self.engine, self.source = Path(workdir), Path(workdir) / folder, engine, source
        self.history, self.tasks = self.dir / "history.review.json", self.dir / "tasks.review.json"
        self.lock, self.job = threading.Lock(), {"running": False, "log": [], "error": "", "step": ""}
        self.notes = []          # what prepare/tasks printed, shown on the review page

    # ---------------------------------------------------------------- local steps, no model calls
    def source_args(self):
        if self.engine == "codex":
            return {"codex_logs": self.source or study.CODEX_DIR, "claude_logs": None}
        return {"claude_logs": self.source or study.CLAUDE_DIR, "codex_logs": None}

    def ensure_inputs(self):
        if not self.history.exists():
            if not self.engine:
                raise ValueError("Start with your history source, for example: python3 study.py web --codex-logs")
            self.notes.append(captured(study.prepare, argparse.Namespace(
                **self.source_args(), output=self.history, days=30, max_messages=study.RECOMMENDED_TURNS,
                exclude_recent_days=14, n_days=study.N_DAYS, dates=None, review=False, block=None)))
        if not self.tasks.exists():
            self.notes.append(captured(study.tasks, argparse.Namespace(
                **(self.source_args() if self.engine else {"claude_logs": None, "codex_logs": None}),
                output=self.tasks, days=14, block=None, no_cohort_task=False, control=False, no_replay=False)))

    def answers_done(self):
        path = self.folder / "eval_answers.local.json"
        if not path.exists() or not self.tasks.exists():
            return False
        done = {t["task_id"] for t in study.read_json(path)}
        return all(t["task_id"] in done for t in study.read_json(self.tasks)[:8])

    def phase(self):
        f = self.folder
        if self.job["running"]:
            return "working"
        if not (study.history_approved(self.history) and self.tasks.exists()
                and not study.unapproved_tasks(self.tasks, study.read_json(self.tasks))):
            return "review"
        if not (f / "cards.local.json").exists() or not self.answers_done():
            return "start"
        if not (f / "compare.share.csv").exists():
            return "compare"
        if not (f / "decisions.share.csv").exists():
            return "confirm"
        if not (f / "choice.share.csv").exists():
            return "choose"
        return "done"

    # ---------------------------------------------------------------- what the page may see in each phase
    def state(self):
        phase = self.phase()
        out = {"phase": phase, "engine": study.ENGINE_NAMES.get(self.current_engine(), ""),
               "job": {k: (("".join(v)[-4000:]) if k == "log" else v) for k, v in self.job.items()}}
        if phase == "review":
            out.update(self.review_data())
        elif phase == "compare":
            out.update(self.compare_data())
        elif phase == "confirm":
            out["cards"] = [{k: c[k] for k in ("card_id", "title", "when", "instruction", "type")}
                            for c in study.read_cards(self.folder)]
        elif phase == "choose":
            out.update(self.choose_data())
        elif phase == "done":
            out.update(self.done_data())
        return out

    def current_engine(self):
        if self.history.exists():
            try:
                return study.load_history(self.history)[0]
            except ValueError:
                pass
        return self.engine or "claude"

    def review_data(self):
        engine, rows = study.load_history(self.history)
        days = {}
        for row in rows:
            days.setdefault(row.get("day", "d1"), []).append({k: row.get(k, "") for k in ("id", "text", "ai")})
        tasks_ = study.read_json(self.tasks)
        return {"days": [days[d] for d in sorted(days, key=lambda d: int(d[1:]))],
                "chats": len({r["chat"] for r in rows}),
                "common": [{"task_id": t["task_id"], "text": t["opening_prompt"]} for t in tasks_
                           if t.get("kind") in ("common", "control")],
                "replay": [{"task_id": t["task_id"], "date": t.get("date", ""), "text": t["opening_prompt"]}
                           for t in tasks_ if t.get("kind") == "replay"],
                "own": next((t["opening_prompt"] for t in tasks_ if t.get("task_id") == "O1"), ""),
                "notes": "".join(self.notes)}

    def compare_order(self):
        """Same order file the terminal compare uses; created here so the browser only ever sees slots X, Y, Z."""
        path = self.folder / "compare.local.json"
        state = study.read_json(path) if path.exists() else {"order": {}, "stage1": {}}
        rng = random.SystemRandom()
        for task in study.load_eval_tasks(self.folder / "eval_answers.local.json"):
            if task["task_id"] not in state["order"]:
                order = [c for c in study.CONDITIONS if c in task["answers"]]
                rng.shuffle(order)
                state["order"][task["task_id"]] = order
        study.save_json(path, state)
        return state

    def compare_data(self):
        state = self.compare_order()
        tasks_ = []
        for task in study.load_eval_tasks(self.folder / "eval_answers.local.json"):
            order = state["order"][task["task_id"]]
            slots = dict(zip(order, "XYZ"))
            done = state["stage1"].get(task["task_id"])
            tasks_.append({"task_id": task["task_id"], "kind": task.get("kind", ""), "task": task.get("task", ""),
                           "answers": [{"slot": slots[c], "text": task["answers"][c]} for c in order],
                           "done": None if not done else {**done, "best": slots.get(done["best"], ""),
                                                          "worst": slots.get(done["worst"], "")}})
        return {"tasks": tasks_, "tags": [{"id": n, "label": text} for n, text in study.REASON_TAGS.values()]}

    def choose_data(self):
        key = study.read_json(self.folder / "key.share.json")
        cards = {c["card_id"]: c for c in study.read_cards(self.folder)}
        decisions = study.read_json(self.folder / "decisions.local.json")["decisions"]
        return {"sets": {letter: [{"title": cards[c["card_id"]]["title"], "type": cards[c["card_id"]]["type"],
                                   "instruction": cards[c["card_id"]]["instruction"],
                                   "decision": decisions.get(c["card_id"], {}).get("decision", "")}
                                  for c in key["cards"] if c["method"] == key["sets"][letter]] for letter in "XY"}}

    def done_data(self):
        key = study.read_json(self.folder / "key.share.json")
        pick = study.read_json(self.folder / "decisions.local.json")["choice"]["pick"]
        zip_path = self.folder / "study_files.zip"
        return {"sets": key["sets"], "pick": pick, "zip": str(zip_path.resolve()), "upload": UPLOAD_URL,
                "files": [str((self.folder / name).resolve()) for name in study.SHARE_FILES
                          if (self.folder / name).exists()],
                "skills": str((self.folder / "my-skills").resolve())}

    # ---------------------------------------------------------------- actions
    def do_review(self, body):
        if self.phase() != "review":
            raise ValueError("The review is already done.")
        study.apply_history_review(self.history, [str(x) for x in body.get("remove_messages", [])])
        rows = study.read_json(self.tasks)
        own = " ".join(str(body.get("own_question", "")).split())
        rows = [r for r in rows if r.get("task_id") != "O1"]
        if own:
            rows.append({"task_id": "O1", "kind": "own", "opening_prompt": study.mask(own)[:800]})
        study.save_json(self.tasks, rows)
        study.apply_task_review(self.tasks, [str(x) for x in body.get("remove_tasks", [])])

    def do_start(self, _body):
        if self.phase() != "start":
            raise ValueError("Nothing to start in this step.")
        self.job.update(running=True, log=[], error="", step="generate")
        threading.Thread(target=self.run_models, daemon=True).start()

    def run_models(self):
        try:
            captured(study.generate, argparse.Namespace(history=self.history, folder=self.folder, model=None,
                                                        confirm_reviewed=False, demo=False), buffer=self.job["log"])
            self.job["step"] = "answers"
            captured(study.answers, argparse.Namespace(folder=self.folder, tasks=self.tasks, n=8, model=None,
                                                       demo=False), buffer=self.job["log"])
        except Exception as error:   # shown on the page; the participant can press Start again to resume
            self.job["error"] = str(error) or error.__class__.__name__
            if not isinstance(error, (ValueError, OSError)):
                traceback.print_exc(file=OUT.original)
        finally:
            self.job["running"] = False

    def do_compare(self, body):
        if self.phase() != "compare":
            raise ValueError("Comparing is not open in this step.")
        state = self.compare_order()
        tid = body.get("task_id")
        if tid not in state["order"]:
            raise ValueError("Unknown task.")
        order = state["order"][tid]
        slot = dict(zip("XYZ", order))
        result = body.get("result", "")
        entry = {"best": "", "worst": "", "result": result, "reason": str(body.get("reason", "")).strip(),
                 "clarity": "", "question_note": str(body.get("question_note", "")).strip(), "tags": ""}
        if result not in ("tie", "skip"):
            best, worst = body.get("best"), body.get("worst")
            if len(order) == 2 and best in slot and not worst:
                worst = next(s for s in slot if s != best and s in "XYZ"[:2])
            tags = [t for t in body.get("tags", []) if t in {n for n, _ in study.REASON_TAGS.values()}]
            if best not in slot or worst not in slot or best == worst:
                raise ValueError("Pick one best and one different worst answer, or press Tie or Skip.")
            if body.get("clarity") not in ("clear", "slight", "forced"):
                raise ValueError("Say how clear the difference was.")
            if not tags or not entry["reason"]:
                raise ValueError("Choose what made the difference and write one line on why.")
            entry.update(best=slot[best], worst=slot[worst], clarity=body["clarity"],
                         tags=" ".join(n for n, _ in study.REASON_TAGS.values() if n in tags))
        state["stage1"][tid] = entry
        study.save_json(self.folder / "compare.local.json", state)
        if all(t in state["stage1"] for t in state["order"]):
            captured(study.compare, argparse.Namespace(folder=self.folder, checklist=False))

    def do_confirm(self, body):
        if self.phase() != "confirm":
            raise ValueError("This step is not open yet.")
        cards = study.read_cards(self.folder)
        given = body.get("decisions", {})
        decisions = {}
        for card in cards:
            entry = given.get(card["card_id"]) or {}
            if entry.get("decision") not in ("keep", "edit", "delete"):
                raise ValueError("Choose keep, edit or delete for every item.")
            decisions[card["card_id"]] = {"decision": entry["decision"],
                                          "comment": str(entry.get("comment", "")).strip()}
            if entry["decision"] == "edit":
                decisions[card["card_id"]].update(
                    when=str(entry.get("when") or card["when"]).strip(),
                    instruction=str(entry.get("instruction") or card["instruction"]).strip())
        reflection = {k: str(body.get("reflection", {}).get(k, "")).strip() for k in ("surprise", "missing")}
        if not all(reflection.values()):
            raise ValueError("Answer both closing questions (write none if nothing comes to mind).")
        added = [{"title": str(a.get("title", "")).strip(), "type": "principle" if a.get("type") == "principle"
                  else "skill", "when": str(a.get("when", "")).strip(), "instruction": str(a.get("instruction", "")).strip()}
                 for a in body.get("added", []) if str(a.get("title", "")).strip()]
        participant = study.read_json(self.folder / "key.share.json")["participant"]
        study.save_json(self.folder / "decisions.local.json", {
            "participant": participant, "decisions": decisions, "added": added, "added_done": True,
            "reflection": reflection})
        captured(study.confirm, argparse.Namespace(folder=self.folder))

    def do_choose(self, body):
        if self.phase() != "choose":
            raise ValueError("This step is not open yet.")
        pick, reason = body.get("pick"), str(body.get("reason", "")).strip()
        if pick not in ("x", "y", "same", "neither") or not reason:
            raise ValueError("Choose X, Y, same or neither, and write one line on why.")
        path = self.folder / "decisions.local.json"
        state = study.read_json(path)
        state["choice"] = {"pick": pick, "reason": reason, "comments": str(body.get("comments", "")).strip()}
        study.save_json(path, state)
        ns = argparse.Namespace(folder=self.folder)
        captured(study.choose, ns)
        captured(study.export, ns)
        captured(study.bundle, ns)

    def do_open(self, body):
        target = self.folder if body.get("what") != "skills" else self.folder / "my-skills"
        study.open_path(target)


def make_handler(app, token):
    page = PAGE.read_text(encoding="utf-8").replace("__TOKEN__", token)
    actions = {"review": app.do_review, "start": app.do_start, "compare": app.do_compare,
               "confirm": app.do_confirm, "choose": app.do_choose, "open": app.do_open}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):   # keep the terminal quiet
            pass

        def send(self, code, body, kind="application/json"):
            data = body.encode("utf-8") if isinstance(body, str) else json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", kind + "; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def allowed(self):
            return secrets.compare_digest(self.headers.get("X-Study-Token", ""), token)

        def do_GET(self):
            if self.path.split("?")[0] == "/":
                return self.send(200, page, "text/html")
            if self.path == "/api/state" and self.allowed():
                try:
                    with app.lock:
                        return self.send(200, app.state())
                except (OSError, ValueError, KeyError) as error:
                    return self.send(200, {"phase": "error", "error": str(error)})
            self.send(404, {"error": "not found"})

        def do_POST(self):
            name = self.path.removeprefix("/api/")
            if name not in actions or not self.allowed():
                return self.send(404, {"error": "not found"})
            try:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}") if length else {}
                with app.lock:
                    actions[name](body)
                    return self.send(200, app.state())
            except (OSError, ValueError, KeyError, TypeError) as error:
                return self.send(400, {"error": str(error)})

    return Handler


def serve(workdir, folder, engine=None, source=None, open_browser=True, port=0):
    app = App(workdir, folder, engine, source)
    app.ensure_inputs()
    token = secrets.token_urlsafe(16)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app, token))
    return app, server


def run(args):
    sys.stdout = OUT
    engine = "codex" if getattr(args, "codex_logs", None) else ("claude" if getattr(args, "claude_logs", None) else None)
    source = args.codex_logs if engine == "codex" else args.claude_logs if engine == "claude" else None
    _, server = serve(Path.cwd(), args.folder, engine, source)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"The study page {'is ready' if args.no_open else 'is opening in your browser'}: {url}\n"
          "(If no page opens, copy that address into your browser.)\n"
          "Everything runs on this computer. Keep this window open while you work on the page; when the page says "
          "you are done, press Ctrl+C here to close it. If you close the page, run the same command again: your "
          "progress is kept.")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nClosed. Run the same command again to continue where you stopped.")
    finally:
        server.server_close()
