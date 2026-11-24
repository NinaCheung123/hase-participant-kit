import csv, io, json, sys, tempfile, unittest
from argparse import Namespace
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import study  # noqa: E402


def feed(*answers):
    return mock.patch("builtins.input", side_effect=list(answers))


def run(fn, **kw):
    out = io.StringIO()
    with redirect_stdout(out):
        fn(Namespace(**kw))
    return out.getvalue()


def rows(path):
    with path.open(encoding="utf-8") as file:
        return list(csv.DictReader(file))


class Turn:
    def __init__(self, i):
        self.text = f"message {i} please keep answers short"
        self.ts = datetime(2026, 11, 20, tzinfo=timezone.utc) + timedelta(minutes=i)
        self.kind, self.source, self.session, self.index = "prompt", "claude", f"s{i % 20}", i


class StudyFlow(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.folder = self.dir / "demo"
        run(study.generate, demo=True, folder=self.folder, history=None, model=None, confirm_reviewed=False)

    def test_generate_has_both_types_and_chat_counts(self):
        key = json.loads((self.folder / "key.share.json").read_text())
        self.assertEqual({c["type"] for c in key["cards"]}, {"skill", "principle"})
        self.assertTrue(all(c["chats"] >= 2 for c in key["cards"]))
        self.assertEqual(sorted(key["sets"]), ["X", "Y"])
        self.assertEqual(set(key["sets"].values()), {"direct", "structured"})

    def test_confirm_choose_export(self):
        n = len(json.loads((self.folder / "cards.local.json").read_text()))
        self.assertEqual(n, 3)
        # keep, edit, delete; then add one principle; blank title ends adding
        with feed("k", "e", "Edited when", "Edited do", "d", "Added", "p", "when", "do", ""):
            run(study.confirm, folder=self.folder)
        decisions = rows(self.folder / "decisions.share.csv")
        self.assertEqual([r["decision"] for r in decisions], ["keep", "edit", "delete", "add"])
        self.assertEqual(set(decisions[0]), set(study.FIELDS))
        text = (self.folder / "decisions.share.csv").read_text()
        self.assertNotIn("Edited", text)  # no card text in the shared file
        with feed("x", "closer to me"):
            run(study.choose, folder=self.folder)
        choice = rows(self.folder / "choice.share.csv")[0]
        self.assertIn(choice["chosen_method"], ("direct", "structured"))
        out = run(study.export, folder=self.folder)
        self.assertIn("principles and", out)
        self.assertTrue((self.folder / "my-skills" / "principles.md").exists())
        self.assertTrue(list((self.folder / "my-skills" / "skills").glob("*/SKILL.md")))

    def test_confirm_resumes_without_asking_twice(self):
        with feed("k", "k", EOFError()):
            with self.assertRaises(EOFError):
                run(study.confirm, folder=self.folder)
        with feed("d", "", ):
            run(study.confirm, folder=self.folder)
        self.assertEqual(len(rows(self.folder / "decisions.share.csv")), 3)

    def test_validate_cards_needs_two_chats_and_defaults_type(self):
        history = [{"id": "m1", "chat": "c1", "text": "a"}, {"id": "m2", "chat": "c2", "text": "b"},
                   {"id": "m3", "chat": "c1", "text": "c"}]
        ok = {"title": "t", "when": "w", "instruction": "i", "kind": "x", "type": "nonsense", "evidence": ["m1", "m2"]}
        bad = {**ok, "title": "t2", "instruction": "i2", "evidence": ["m1", "m3"]}
        found = study.validate_cards([ok, bad], history, {"m1", "m2", "m3"})
        self.assertEqual(len(found), 1)
        self.assertEqual((found[0]["type"], found[0]["kind"], found[0]["chats"]), ("skill", "other", 2))

    def test_parse_array_tolerates_fences_and_trailing_text(self):
        self.assertEqual(study.parse_array('[{"a": 1}]'), [{"a": 1}])
        self.assertEqual(study.parse_array('```json\n[{"a": 1}]\n```'), [{"a": 1}])
        self.assertEqual(study.parse_array('Here you go:\n[{"a": 1}]\n\nNote: I kept it short.'), [{"a": 1}])
        for bad in ("no json here", '{"a": 1}', "[1, 2"):
            with self.assertRaises(ValueError):
                study.parse_array(bad)

    def test_prompts_share_scope_and_type_spec(self):
        self.assertIn("not personal topics", study.SCOPE)
        self.assertIn("principle", study.CARD_SPEC)

    def test_prepare_soft_cap_and_estimate(self):
        with mock.patch.object(study, "load_turns", lambda a: [Turn(i) for i in range(120)]):
            out = run(study.prepare, output=self.dir / "h.json", max_messages=100, days=7, exclude_recent_days=0)
            self.assertIn("roughly", out)
            self.assertIn("more than the recommended", out)
            n = len(json.loads((self.dir / "h.json").read_text()))
            self.assertGreater(n, study.RECOMMENDED_TURNS)  # a recommendation, not a hard stop
            out2 = run(study.prepare, output=self.dir / "h2.json", max_messages=study.RECOMMENDED_TURNS,
                       days=7, exclude_recent_days=0)
            self.assertNotIn("more than the recommended", out2)

    def test_forked_session_duplicates_count_once(self):
        a, b = Turn(1), Turn(2)
        b.text, b.ts, b.session = a.text, a.ts + timedelta(seconds=20), "other-session"   # same minute, same text
        others = [Turn(i + 10) for i in range(3)]
        with mock.patch.object(study, "load_turns", lambda args: [a, b] + others):
            run(study.prepare, output=self.dir / "d.json", max_messages=48, days=7, exclude_recent_days=0)
        texts = [r["text"] for r in json.loads((self.dir / "d.json").read_text())]
        self.assertEqual(texts.count(a.text), 1)

    def test_automatic_filter_drops_sensitive_topics_and_reports_counts(self):
        class T(Turn):
            def __init__(self, i, text):
                super().__init__(i)
                self.text, self.session = text, f"s{i}"
        texts = ["Shorter, please, and conclusion first for this note.", "Why did you choose that option here?",
                 "Help me write to my landlord about the lease.", "My doctor said the diagnosis is fine, rewrite this.",
                 "Meine Miete ist zu hoch, formuliere eine Mail.", "帮我改一下面试后的感谢邮件，简短一点。",
                 "Remember the Acme project codename Zebra in every reply."]
        blocklist = self.dir / "block.txt"
        blocklist.write_text("zebra\n")
        with mock.patch.object(study, "load_turns", lambda a: [T(i, t) for i, t in enumerate(texts)]):
            out = run(study.prepare, output=self.dir / "f.json", max_messages=48, days=7, exclude_recent_days=0,
                      block=blocklist, review=False)
        kept = [r["text"] for r in json.loads((self.dir / "f.json").read_text())]
        self.assertEqual(len(kept), 2)
        self.assertTrue(all("landlord" not in t and "Zebra" not in t for t in kept))
        for name in ("housing_visa", "health", "job", "custom"):
            self.assertIn(name, out)
        self.assertNotIn("landlord", out)             # counts only, never message text
        self.assertFalse((self.dir / "f.json.needs-review").exists())

    def test_review_option_requires_confirmation_before_generate(self):
        turns = [Turn(i) for i in range(30)]
        with mock.patch.object(study, "load_turns", lambda a: turns):
            run(study.prepare, output=self.dir / "r.json", max_messages=48, days=7, exclude_recent_days=0, review=True)
        self.assertTrue((self.dir / "r.json.needs-review").exists())
        with self.assertRaises(ValueError):
            run(study.generate, demo=False, folder=self.dir / "x", history=self.dir / "r.json", model="m",
                confirm_reviewed=False)

    def test_history_ceiling(self):
        rows_ = [{"id": f"m{i+1}", "chat": f"c{i % 30 + 1}", "text": "x"} for i in range(study.MAX_TURNS + 1)]
        p = self.dir / "big.json"
        p.write_text(json.dumps(rows_))
        with self.assertRaises(ValueError):
            study.load_history(p)


class AnswerStage(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.folder = self.dir / "demo"
        run(study.generate, demo=True, folder=self.folder, history=None, model=None, confirm_reviewed=False)
        self.tasks = self.dir / "tasks.review.json"
        self.tasks.write_text(json.dumps(study.COMMON_TASKS))

    def confirm_all(self, *decisions):
        with feed(*decisions, ""):
            run(study.confirm, folder=self.folder)

    def make_tasks(self, turns, **kw):
        args = dict(output=self.dir / "t.json", days=14, hase=False, control=False, no_replay=False,
                    export=None, cursor_logs=None, codex_logs=None, claude_logs=1)
        args.update(kw)
        with mock.patch.object(study, "load_turns", lambda a: turns):
            out = run(study.tasks, **args)
        return json.loads(args["output"].read_text()), out

    def test_tasks_common_plus_masked_filtered_replay(self):
        class T(Turn):
            def __init__(self, i, text):
                super().__init__(i)
                self.text, self.index, self.session = text, 0, f"s{i}"
        good = "Explain the trade-offs between two vendors for a manager, then reply to a@b.com or call 0041 44 635 67 32 later"
        needs_file = "please run the script in my repo and fix the file " + "x" * 60
        link = "Explain the trade-offs between two vendors for a manager, using the page at https://x.io/a for the facts"
        sensitive = "Help me write a polite message to my landlord about the lease and the rent increase next month"
        rows_, _ = self.make_tasks([T(1, good), T(2, needs_file), T(3, link), T(4, "short"), T(5, sensitive)])
        self.assertEqual([r["task_id"] for r in rows_], ["T1", "T2", "T3", "R1"])
        self.assertTrue(all(r["rubric"] for r in rows_[:3]))
        replay = rows_[3]
        self.assertEqual(replay["kind"], "replay")
        self.assertIn("[EMAIL]", replay["opening_prompt"])
        self.assertNotIn("635", replay["opening_prompt"])

    def test_tasks_options_and_fallbacks(self):
        rows_, out = self.make_tasks([], hase=True, control=True, output=self.dir / "a.json")
        self.assertEqual([r["task_id"] for r in rows_], ["T1", "T2", "T3", "T4", "C1"])
        self.assertIn("only the common tasks", out)
        rows_, out = self.make_tasks([], no_replay=True, output=self.dir / "b.json")
        self.assertEqual(len(rows_), 3)
        rows_, out = self.make_tasks([], claude_logs=None, output=self.dir / "c.json")
        self.assertEqual(len(rows_), 3)
        self.assertIn("replay tasks are skipped", out)

    def test_replay_is_capped(self):
        class T(Turn):
            def __init__(self, i):
                super().__init__(i)
                self.text = f"Explain option {i} to a new teammate in plain words, with one example for each of the options we discussed"
                self.index, self.session = 0, f"s{i}"
                self.ts = datetime(2026, 11, 1, tzinfo=timezone.utc) + timedelta(days=i % 14, minutes=i)
        rows_, _ = self.make_tasks([T(i) for i in range(30)])
        replay = [r for r in rows_ if r["kind"] == "replay"]
        self.assertEqual(len(replay), study.MAX_REPLAY)

    def test_full_flow_answers_compare_confirm_choose(self):
        out = run(study.answers, folder=self.folder, tasks=self.tasks, n=6, model=None, demo=True)  # no confirm needed
        self.assertIn("3 tasks x 3 conditions", out)
        with self.assertRaises(ValueError):       # items stay unseen until the answers are judged
            run(study.confirm, folder=self.folder)
        data = json.loads((self.folder / "eval_answers.local.json").read_text())
        self.assertEqual(set(data[0]["answers"]), {"A", "B", "C"})
        self.assertTrue(data[0]["rubric"])
        inputs = ["short", "conclusion first", "",   # T1 checklist (written before any answer is shown)
                  "", "",                              # T2, T3: no checklist
                  "x", "y", "none", "clear",           # T1: best X, worst Y, nothing fails, reason
                  "tie", "none", "",                   # T2: cannot tell
                  "skip",                              # T3: not a fair test
                  "xz", "none"]                        # T1 checklist afterwards: which answers meet each item
        with feed(*inputs):
            run(study.compare, folder=self.folder)
        r = rows(self.folder / "compare.share.csv")
        self.assertEqual([x["result"] for x in r], ["", "tie", "skip"])
        self.assertEqual(r[0]["kind"], "common")
        self.assertIn(r[0]["best_condition"], ("none", "direct", "structured"))
        self.assertNotEqual(r[0]["best_condition"], r[0]["worst_condition"])
        self.assertEqual(r[0]["checklist_items"], "2")
        self.assertIn(r[0]["best_meets"], ("0", "1"))
        key = json.loads((self.folder / "key.share.json").read_text())
        self.assertEqual(r[0]["participant"], key["participant"])
        text = (self.folder / "compare.share.csv").read_text()
        self.assertNotIn("demo answer", text)
        self.assertNotIn("conclusion first", text)     # checklist wording stays local; only counts are shared
        with feed("y", "closer"):                       # choose needs confirm first
            with self.assertRaises(ValueError):
                run(study.choose, folder=self.folder)
        self.confirm_all("k", "d", "k")
        with feed("y", "closer"):
            run(study.choose, folder=self.folder)
        self.assertTrue((self.folder / "choice.share.csv").exists())
        self.assertEqual(rows(self.folder / "decisions.share.csv")[0]["participant"], key["participant"])

    def test_bundle_contains_only_share_files(self):
        with feed("", "", "", "x", "y", "none", "ok", "skip", "skip"):  # skip checklists; task 1 ranked, 2 and 3 skipped
            run(study.answers, folder=self.folder, tasks=self.tasks, n=6, model=None, demo=True)
            run(study.compare, folder=self.folder)
        with self.assertRaises(ValueError):       # decisions and choice are still missing
            run(study.bundle, folder=self.folder)
        self.confirm_all("k", "d", "k")
        with feed("x", "fine"):
            run(study.choose, folder=self.folder)
        run(study.bundle, folder=self.folder)
        import zipfile
        names = sorted(zipfile.ZipFile(self.folder / "study_files.zip").namelist())
        self.assertEqual(names, sorted(study.SHARE_FILES))
        self.assertFalse(any(".local" in n for n in names))

    def test_checklist_never_changes_the_ranking(self):
        run(study.answers, folder=self.folder, tasks=self.tasks, n=1, model=None, demo=True)
        with feed("one", "", "x", "y", "z", "ok", "none"):      # checklist, X best, Y worst, Z fails, reason, "none meet"
            run(study.compare, folder=self.folder)
        r = rows(self.folder / "compare.share.csv")[0]
        self.assertEqual(r["best_meets"], "0")                  # the winner met no checklist item; ranking unchanged
        self.assertNotEqual(r["best_condition"], "")
        self.assertEqual(len(r["below_threshold"].split(";")), 1)

    def test_method_with_no_items_drops_that_condition(self):
        kp = self.folder / "key.share.json"
        key = json.loads(kp.read_text())
        for c in key["cards"]:
            c["method"] = "structured"
        kp.write_text(json.dumps(key))
        out = run(study.answers, folder=self.folder, tasks=self.tasks, n=1, model=None, demo=True)
        self.assertIn("direct method returned no items", out)
        data = json.loads((self.folder / "eval_answers.local.json").read_text())
        self.assertEqual(set(data[0]["answers"]), {"A", "C"})
        with feed("", "x", "none", "ok"):                       # no checklist; two conditions: best only, worst implied
            run(study.compare, folder=self.folder)
        r = rows(self.folder / "compare.share.csv")[0]
        self.assertEqual({r["best_condition"], r["worst_condition"]}, {"none", "structured"})

    def test_no_items_anywhere_refuses(self):
        (self.folder / "cards.local.json").write_text("[]")
        with self.assertRaises(ValueError):
            run(study.answers, folder=self.folder, tasks=self.tasks, n=1, model=None, demo=True)

    def test_replay_prompt_gets_word_cap_common_does_not(self):
        calls = []
        tasks = [{"task_id": "T1", "kind": "common", "opening_prompt": "common prompt"},
                 {"task_id": "R1", "kind": "replay", "opening_prompt": "replay prompt"}]
        path = self.dir / "two.json"
        path.write_text(json.dumps(tasks))
        with mock.patch.object(study, "run_claude", lambda prompt, model, system=None: calls.append(prompt) or "a"):
            run(study.answers, folder=self.folder, tasks=path, n=6, model="m", demo=False)
        self.assertEqual(len(calls), 6)
        self.assertEqual(sum(study.REPLAY_WORDS in c for c in calls), 3)
        self.assertTrue(all("common prompt" in c for c in calls if "replay prompt" not in c))

    def test_choose_without_answers_still_works(self):
        self.confirm_all("k", "k", "k")
        with feed("same", "no difference"):
            run(study.choose, folder=self.folder)
        self.assertEqual(rows(self.folder / "choice.share.csv")[0]["chosen_method"], "same")


if __name__ == "__main__":
    unittest.main()
