import csv, io, json, sys, tempfile, unittest
from argparse import Namespace
from collections import Counter
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
        with feed("k", "sounds like me", "e", "Edited when", "Edited do", "close", "d", "", "the second", "none",
                  "Added", "p", "when", "do", ""):
            run(study.confirm, folder=self.folder)
        decisions = rows(self.folder / "decisions.share.csv")
        self.assertEqual([r["decision"] for r in decisions], ["keep", "edit", "delete", "add"])
        self.assertEqual(set(decisions[0]), set(study.FIELDS))
        text = (self.folder / "decisions.share.csv").read_text()
        self.assertNotIn("Edited", text)  # no card text in the shared file
        self.assertEqual([r["comment"] for r in decisions], ["sounds like me", "close", "", ""])
        with feed("x", "closer to me", ""):
            run(study.choose, folder=self.folder)
        choice = rows(self.folder / "choice.share.csv")[0]
        self.assertIn(choice["chosen_method"], ("direct", "structured"))
        self.assertEqual((choice["surprise"], choice["missing"]), ("the second", "none"))
        out = run(study.export, folder=self.folder)
        self.assertIn("principles and", out)
        self.assertTrue((self.folder / "my-skills" / "principles.md").exists())
        self.assertTrue(list((self.folder / "my-skills" / "skills").glob("*/SKILL.md")))

    def test_confirm_resumes_without_asking_twice(self):
        with feed("k", "", "k", "", EOFError()):
            with self.assertRaises(EOFError):
                run(study.confirm, folder=self.folder)
        with feed("d", "", "s", "m", ""):
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

    def test_review_shows_each_day_removes_numbers_and_gates_generate(self):
        turns = [Turn(i) for i in range(30)]
        with mock.patch.object(study, "load_turns", lambda a: turns):
            run(study.prepare, output=self.dir / "r.json", max_messages=48, days=7, exclude_recent_days=0)
        with self.assertRaisesRegex(ValueError, "study.py review"):
            run(study.generate, demo=False, folder=self.dir / "x", history=self.dir / "r.json", model="m",
                confirm_reviewed=True)
        before = json.loads((self.dir / "r.json").read_text())
        with feed("99", "2 5"):                                 # invalid number is re-asked; then remove 2 and 5
            out = run(study.review, history=self.dir / "r.json", tasks=self.dir / "none.json")
        after = json.loads((self.dir / "r.json").read_text())
        self.assertEqual(len(after), len(before) - 2)
        self.assertNotIn(before[1]["text"], [r["text"] for r in after if r["id"] == before[1]["id"]])
        self.assertIn("Approved 28 of 30", out)
        self.assertTrue(study.history_approved(self.dir / "r.json"))
        (self.dir / "r.json").write_text(json.dumps(after[:-1]))    # editing after review needs a new review
        self.assertFalse(study.history_approved(self.dir / "r.json"))

    def test_review_refuses_to_leave_fewer_than_two_chats(self):
        path = self.dir / "two.json"
        path.write_text(json.dumps([{"id": "m1", "chat": "c1", "text": "a"}, {"id": "m2", "chat": "c2", "text": "b"}]))
        with self.assertRaisesRegex(ValueError, "two chats"):
            study.apply_history_review(path, ["m1"])
        self.assertFalse(study.history_approved(path))

    def test_review_asks_about_each_own_chat_task(self):
        path = self.dir / "t.json"
        path.write_text(json.dumps(study.COMMON_TASKS + [
            {"task_id": "R1", "kind": "replay", "opening_prompt": "first own opening"},
            {"task_id": "R2", "kind": "replay", "opening_prompt": "second own opening"}]))
        with feed("n", "y"):
            out = run(study.review, history=self.dir / "none.json", tasks=path)
        ids = [r["task_id"] for r in json.loads(path.read_text())]
        self.assertEqual(ids, ["T1", "T2", "T3", "R2"])
        self.assertIn("removed R1", out)
        self.assertEqual(study.unapproved_tasks(path, json.loads(path.read_text())), [])

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
        inputs = [x for d in decisions for x in (d, "")] + ["surprise", "missing", ""]
        with feed(*inputs):
            run(study.confirm, folder=self.folder)

    def make_tasks(self, turns, **kw):
        args = dict(output=self.dir / "t.json", days=14, no_cohort_task=False, control=False, no_replay=False,
                    no_own=True, export=None, cursor_logs=None, codex_logs=None, claude_logs=1)
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
        self.assertEqual([r["task_id"] for r in rows_], ["T1", "T2", "T3", "T4", "R1"])
        self.assertTrue(all(r["rubric"] for r in rows_[:4]))
        replay = rows_[4]
        self.assertEqual(replay["kind"], "replay")
        self.assertIn("[EMAIL]", replay["opening_prompt"])
        self.assertNotIn("635", replay["opening_prompt"])

    def test_tasks_options_and_fallbacks(self):
        rows_, out = self.make_tasks([], control=True, output=self.dir / "a.json")
        self.assertEqual([r["task_id"] for r in rows_], ["T1", "T2", "T3", "T4", "C1"])
        self.assertIn("only the common tasks", out)
        rows_, out = self.make_tasks([], no_replay=True, output=self.dir / "b.json")
        self.assertEqual(len(rows_), 4)
        rows_, out = self.make_tasks([], no_replay=True, no_cohort_task=True, output=self.dir / "b2.json")
        self.assertEqual([r["task_id"] for r in rows_], ["T1", "T2", "T3"])
        rows_, out = self.make_tasks([], claude_logs=None, output=self.dir / "c.json")
        self.assertEqual(len(rows_), 4)
        self.assertIn("replay tasks are skipped", out)

    def test_tasks_never_waits_for_input_and_lists_the_tasks(self):
        with mock.patch("builtins.input", side_effect=AssertionError("tasks must not read input")):
            rows_, out = self.make_tasks([], no_replay=True, output=self.dir / "n.json")
        self.assertEqual(len(rows_), 4)
        self.assertIn("T1  Below are rough notes", out)
        self.assertIn("python3 study.py ask", out)
        self.assertIn("Next: python3 study.py review", out)

    def test_ask_adds_one_masked_own_task_last_and_can_be_cancelled(self):
        rows_, _ = self.make_tasks([], no_replay=True, output=self.dir / "a1.json")
        path = self.dir / "a1.json"
        with feed("Plan my week, see https://x.io/a today"):
            out = run(study.ask, tasks=path)
        rows_ = json.loads(path.read_text())
        self.assertEqual([r["task_id"] for r in rows_], ["T1", "T2", "T3", "T4", "O1"])
        self.assertEqual(rows_[-1]["kind"], "own")
        self.assertIn("[URL]", rows_[-1]["opening_prompt"])
        with feed("A different question"):                      # asking again replaces O1 instead of adding a second
            run(study.ask, tasks=path)
        rows_ = json.loads(path.read_text())
        self.assertEqual([r["task_id"] for r in rows_].count("O1"), 1)
        self.assertEqual(rows_[-1]["opening_prompt"], "A different question")
        with feed(""):                                           # Enter = cancel, nothing changes
            out = run(study.ask, tasks=path)
        self.assertIn("unchanged", out)
        self.assertEqual(len(json.loads(path.read_text())), 5)
        with self.assertRaises(ValueError):
            run(study.ask, tasks=self.dir / "missing.json")

    def test_prepare_prints_full_path_and_clear_sample_line(self):
        turns = [Turn(i) for i in range(30)]
        with mock.patch.object(study, "load_turns", lambda a: turns):
            out = run(study.prepare, output=self.dir / "p.json", max_messages=48, days=7, exclude_recent_days=0)
        self.assertIn("Nothing has been sent yet", out)
        self.assertIn("review step", out)
        self.assertNotIn("Recommended sample", out)
        self.assertIn("Next: python3 study.py tasks", out)

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
        inputs = ["x", "y", "clear", "", "1 3", "", "why",   # T1: best X, worst Y, clarity, tags (re-asked), reason (re-asked)
                  "tie", "cannot tell",                       # T2: cannot tell, why
                  "skip", "needs a file"]                     # T3: not a fair test, what is wrong with the question
        with feed(*inputs):                            # no checklist prompts by default
            run(study.compare, folder=self.folder)
        r = rows(self.folder / "compare.share.csv")
        self.assertEqual([x["result"] for x in r], ["", "tie", "skip"])
        self.assertEqual(r[0]["kind"], "common")
        self.assertIn(r[0]["best_condition"], ("none", "direct", "structured"))
        self.assertNotEqual(r[0]["best_condition"], r[0]["worst_condition"])
        self.assertNotIn("checklist_items", r[0])
        self.assertNotIn("below_threshold", r[0])
        self.assertEqual((r[0]["clarity"], r[0]["reason"], r[0]["question_note"]), ("clear", "why", ""))
        self.assertEqual((r[0]["reason_tags"], r[1]["reason_tags"]), ("accurate clearer", ""))
        self.assertEqual((r[1]["reason"], r[1]["clarity"]), ("cannot tell", ""))
        self.assertEqual(r[2]["question_note"], "needs a file")
        self.assertEqual(r[0]["sim_none_direct"], "1.0")                 # demo answers are identical
        key = json.loads((self.folder / "key.share.json").read_text())
        self.assertEqual(r[0]["participant"], key["participant"])
        text = (self.folder / "compare.share.csv").read_text()
        self.assertNotIn("demo answer", text)
        with feed("y", "closer"):                       # choose needs confirm first
            with self.assertRaises(ValueError):
                run(study.choose, folder=self.folder)
        self.confirm_all("k", "d", "k")
        with feed("y", "closer", "step 3 was unclear"):
            run(study.choose, folder=self.folder)
        self.assertTrue((self.folder / "choice.share.csv").exists())
        self.assertEqual(rows(self.folder / "choice.share.csv")[0]["comments"], "step 3 was unclear")
        self.assertEqual(rows(self.folder / "decisions.share.csv")[0]["participant"], key["participant"])

    def test_bundle_contains_only_share_files(self):
        with feed("x", "y", "clear", "1", "ok", "skip", "", "skip", ""):   # task 1 ranked, 2 and 3 skipped
            run(study.answers, folder=self.folder, tasks=self.tasks, n=6, model=None, demo=True)
            run(study.compare, folder=self.folder)
        with self.assertRaises(ValueError):       # decisions and choice are still missing
            run(study.bundle, folder=self.folder)
        self.confirm_all("k", "d", "k")
        with feed("x", "fine", ""):
            run(study.choose, folder=self.folder)
        run(study.bundle, folder=self.folder)
        import zipfile
        names = sorted(zipfile.ZipFile(self.folder / "study_files.zip").namelist())
        self.assertEqual(names, sorted(study.SHARE_FILES))
        self.assertFalse(any(".local" in n for n in names))

    def test_optional_checklist_never_changes_the_ranking(self):
        run(study.answers, folder=self.folder, tasks=self.tasks, n=1, model=None, demo=True)
        with feed("one", "", "x", "y", "slight", "1", "ok", "none"):   # checklist; X best, Y worst, clarity, reason, note; "none meet"
            run(study.compare, folder=self.folder, checklist=True)
        r = rows(self.folder / "compare.share.csv")[0]
        self.assertEqual(r["best_meets"], "0")                  # the winner met no checklist item; ranking unchanged
        self.assertNotEqual(r["best_condition"], "")
        self.assertEqual(r["clarity"], "slight")

    def test_each_step_explains_what_is_happening(self):
        out = run(study.answers, folder=self.folder, tasks=self.tasks, n=6, model=None, demo=True)
        self.assertIn("You do not answer anything in this step and no question is shown yet", out)
        with feed("x", "y", "clear", "2", "r", "tie", "", "skip", ""):
            out = run(study.compare, folder=self.folder)
        # the compare intro is printed before the first task is shown
        self.assertIn("one at a time", out)
        self.assertIn("Nothing is graded", out)
        with feed("k", "", "k", "", "k", "", "s", "m", ""):
            out = run(study.confirm, folder=self.folder)
        self.assertIn("for the first time", out)
        with feed("x", "ok", ""):
            out = run(study.choose, folder=self.folder)
        self.assertIn("without saying which is which", out)
        self.assertIn("Set X =", out)
        self.assertIn("A = no skills", out)

    def test_similarity_is_word_overlap(self):
        self.assertEqual(study.similarity("a b c", "a b c"), 1.0)
        self.assertEqual(study.similarity("a b c", "a b d"), 0.5)
        self.assertEqual(study.similarity("", ""), 1.0)

    def test_harness_text_is_not_used(self):
        for text in ("Side conversation boundary. Parent chat: x", "<turn_aborted> The user interrupted", "# Files mentioned by the user: a.png"):
            self.assertTrue(study.HARNESS_TEXT.search(text))
        self.assertFalse(study.HARNESS_TEXT.search("can you find me the files"))

    def test_every_common_task_has_a_word_limit(self):
        texts = {x["task_id"]: x["opening_prompt"] for x in study.COMMON_TASKS + [study.COHORT_TASK]}
        self.assertIn("At most 180 words", texts["T1"])
        self.assertIn("at most 200 words", texts["T3"])
        self.assertIn("at most 150 words", texts["T4"])
        self.assertIn("At most 150 words", texts["T2"])

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
        with feed("x", "forced", "1", "ok"):                     # two conditions: best only, worst implied
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
                 {"task_id": "R1", "kind": "replay", "opening_prompt": "replay prompt"},
                 {"task_id": "O1", "kind": "own", "opening_prompt": "own prompt"}]
        path = self.dir / "two.json"
        path.write_text(json.dumps(tasks))
        with self.assertRaisesRegex(ValueError, "R1"):          # own-chat tasks need approval before anything is sent
            run(study.answers, folder=self.folder, tasks=path, n=6, model="m", demo=False)
        study.apply_task_review(path, [])
        with mock.patch.object(study, "run_claude", lambda prompt, model, system=None: calls.append(prompt) or "a"):
            run(study.answers, folder=self.folder, tasks=path, n=6, model="m", demo=False)
        self.assertEqual(len(calls), 9)
        self.assertEqual(sum(study.REPLAY_WORDS in c for c in calls), 6)          # replay and own are capped
        self.assertTrue(all(study.REPLAY_WORDS not in c for c in calls if "common prompt" in c))

    def test_choose_without_answers_still_works(self):
        self.confirm_all("k", "k", "k")
        with feed("same", "no difference", ""):
            run(study.choose, folder=self.folder)
        self.assertEqual(rows(self.folder / "choice.share.csv")[0]["chosen_method"], "same")


class CodexStudyFlow(unittest.TestCase):
    def test_codex_history_routes_generation_and_answers_to_same_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sample = root / "history.json"
            tasks = root / "tasks.json"
            folder = root / "run"
            with mock.patch.object(study, "load_turns", return_value=[Turn(1), Turn(2)]):
                run(study.prepare, codex_logs=root, output=sample, max_messages=48,
                    days=7, exclude_recent_days=0)
            self.assertEqual(study.read_json(sample)["engine"], "codex")
            with self.assertRaisesRegex(ValueError, "study.py review"):
                run(study.generate, history=sample, folder=folder, demo=False, model=None,
                    confirm_reviewed=True)                  # the old flag no longer skips the review
            study.apply_history_review(sample, [])
            responses = [json.dumps(study.demo_response(stage))
                         for stage in ("direct", "observations", "structured")]
            with mock.patch.object(study, "run_codex", side_effect=responses + ["Answer"] * 3) as codex, \
                    mock.patch.object(study, "run_claude") as claude:
                run(study.generate, history=sample, folder=folder, demo=False, model="custom-codex",
                    confirm_reviewed=True)
                study.save_json(tasks, study.COMMON_TASKS[:1])
                with self.assertRaisesRegex(ValueError, "custom-codex"):
                    run(study.answers, folder=folder, tasks=tasks, n=1, model="another-model", demo=False)
                run(study.answers, folder=folder, tasks=tasks, n=1, model=None, demo=False)
                self.assertEqual(codex.call_count, 6)
                self.assertEqual({call.args[1] for call in codex.call_args_list}, {"custom-codex"})
                claude.assert_not_called()
            self.assertEqual(study.read_json(folder / "key.share.json")["engine"], "codex")
            answers = study.read_json(folder / "eval_answers.local.json")
            self.assertEqual(set(answers[0]["answers"]), {"A", "B", "C"})


class DayTurn:
    def __init__(self, day, minute, text, session, prev=""):
        self.text, self.prev, self.session = text, prev, session
        self.ts = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc) + timedelta(days=day, minutes=minute)
        self.kind, self.source, self.index = "prompt", "claude", minute


def busy_day(day, n, session="s", sensitive=0):
    out = []
    for m in range(n):
        text = ("My landlord and the lease again please" if m < sensitive
                else f"Plain neutral request number {m} on day {day} about the quarterly planning document")
        out.append(DayTurn(day, m, text, f"{session}{day}-{m % 3}"))
    return out


class DaySelection(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def prepare(self, turns, **kw):
        args = dict(output=self.dir / f"h{len(list(self.dir.iterdir()))}.json", max_messages=48, days=60,
                    exclude_recent_days=0, n_days=5, dates=None, block=None, review=False)
        args.update(kw)
        with mock.patch.object(study, "load_turns", lambda a: turns):
            out = run(study.prepare, **args)
        return json.loads(args["output"].read_text()), out

    def test_one_busy_day_per_week_in_order_with_day_labels(self):
        turns = []
        for week in range(6):                      # six weeks; two busy days in each, one busier
            turns += busy_day(week * 7 + 1, 14) + busy_day(week * 7 + 3, 10)
        rows_, out = self.prepare(turns)
        self.assertEqual(sorted({r["day"] for r in rows_}), ["d1", "d2", "d3", "d4", "d5"])
        self.assertLessEqual(len(rows_), 50)
        self.assertEqual([r["id"] for r in rows_], [f"m{i + 1}" for i in range(len(rows_))])
        days_used = [d for d in out.split("(")[1].split(")")[0].split(", ")]
        weeks = {datetime.strptime(d, "%Y-%m-%d").isocalendar()[1] for d in days_used}
        self.assertEqual(len(weeks), 5)             # five different weeks
        self.assertEqual([r["day"] for r in rows_], sorted(r["day"] for r in rows_))   # chronological

    def test_one_long_chat_across_days_still_passes_generation_limits(self):
        turns = []
        for week in range(5):
            day = week * 7 + 1
            turns += [DayTurn(day, m, f"Plain neutral request number {m} on day {day} about the quarterly plan",
                              "long-chat") for m in range(12)]
            turns += [DayTurn(day, 30 + m, f"Another neutral request number {m} on day {day} about the budget plan",
                              f"other{week}") for m in range(3)]
        rows_, _ = self.prepare(turns)
        self.assertLessEqual(len(rows_), 48)
        self.assertLessEqual(max(Counter(r["chat"] for r in rows_).values()), study.MAX_PER_CHAT)
        path = self.dir / "check.json"
        path.write_text(json.dumps(rows_))
        study.load_history(path)

    def test_personal_day_is_skipped(self):
        turns = busy_day(1, 12) + busy_day(10, 12, sensitive=8) + busy_day(20, 12)
        rows_, out = self.prepare(turns, n_days=3)
        self.assertNotIn("2026-11-11", out)
        self.assertEqual(len({r["day"] for r in rows_}), 2)     # the personal day is not used, the other two are

    def test_dates_override(self):
        turns = busy_day(1, 12) + busy_day(10, 12) + busy_day(20, 12)
        rows_, out = self.prepare(turns, dates="2026-11-11")
        self.assertEqual({r["day"] for r in rows_}, {"d1"})
        self.assertIn("2026-11-11", out)
        with self.assertRaises(ValueError):
            self.prepare(turns, dates="2030-01-01")

    def test_sparse_history_still_works(self):
        rows_, out = self.prepare([DayTurn(3, 0, "A short note about the report", "sa"),
                                   DayTurn(3, 1, "Another note about the report plan", "sb")])
        self.assertEqual(len(rows_), 2)
        self.assertIn("smaller days were used", out)

    def test_cap_per_day_keeps_total_near_max(self):
        turns = []
        for week in range(6):
            turns += busy_day(week * 7 + 1, 40)
        rows_, _ = self.prepare(turns, max_messages=20, n_days=5)
        self.assertLessEqual(len(rows_), 20)
        self.assertEqual({r["day"] for r in rows_}, {"d1", "d2", "d3", "d4", "d5"})

    def test_ai_tail_only_for_short_or_steering_and_masked_and_filtered(self):
        long_neutral = "Please prepare the quarterly planning document with the usual sections and a tidy summary"
        turns = []
        for m in range(8):
            turns.append(DayTurn(1, m, long_neutral + f" version {m}", f"s{m % 2}", prev="assistant long reply " + "x" * 500))
        turns += [DayTurn(1, 20, "Shorter please", "s0", prev="Here is a long reply see https://x.io/a and mail a@b.com"),
                  DayTurn(1, 21, "No, I said use plain words instead of jargon here", "s1", prev="Your landlord lease notes"),
                  DayTurn(1, 22, "Again, put the answer first", "s0", prev="y" * 600)]
        rows_, out = self.prepare(turns, n_days=1)
        with_ai = [r for r in rows_ if "ai" in r]
        self.assertEqual(len(with_ai), 2)                       # Shorter + Again; the landlord tail is dropped
        self.assertTrue(all(len(r["ai"]) <= study.MAX_AI_CHARS for r in with_ai))
        self.assertFalse(any("ai" in r for r in rows_ if r["text"].startswith("Please prepare")))
        shorter = next(r for r in rows_ if r["text"] == "Shorter please")
        self.assertIn("[URL]", shorter["ai"])
        self.assertNotIn("a@b.com", shorter["ai"])
        self.assertIn("2 short or correcting messages carry", out)

    def test_history_file_accepts_day_and_ai_but_not_other_keys_or_long_ai(self):
        good = [{"id": "m1", "chat": "c1", "day": "d1", "text": "a", "ai": "tail"},
                {"id": "m2", "chat": "c2", "day": "d1", "text": "b"}]
        path = self.dir / "g.json"
        path.write_text(json.dumps(good))
        self.assertEqual(len(study.load_history(path)), 2)
        for bad in ([{**good[0], "extra": 1}, good[1]], [{**good[0], "ai": "z" * 301}, good[1]],
                    [{**good[0], "day": "today"}, good[1]]):
            path.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):
                study.load_history(path)

    def test_prompts_explain_ai_and_day_fields(self):
        self.assertIn("ai:", study.FIELDS_NOTE)
        self.assertIn("day label", study.FIELDS_NOTE)


if __name__ == "__main__":
    unittest.main()


class CodexLogs(unittest.TestCase):
    def test_agents_md_does_not_hide_the_real_opening_message(self):
        from context_user.sources import read_codex
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026" / "11" / "20" / "rollout-x.jsonl"
            path.parent.mkdir(parents=True)
            def line(role, text):
                return json.dumps({"timestamp": "2026-11-20T10:00:00Z", "type": "response_item", "payload": {
                    "type": "message", "role": role, "content": [{"type": "input_text", "text": text}]}})
            path.write_text("\n".join([
                json.dumps({"timestamp": "2026-11-20T10:00:00Z", "type": "session_meta", "payload": {"id": "s1"}}),
                line("user", "# AGENTS.md instructions for /p\n\n<INSTRUCTIONS>\nUse uv.\n</INSTRUCTIONS>"),
                line("user", "<user_instructions>older layout</user_instructions>"),
                line("user", "<environment_context>\n<cwd>/p</cwd>\n</environment_context>"),
                line("user", "Real opening message"), line("user", "shorter")]) + "\n")
            turns = list(read_codex(Path(tmp)))
        self.assertEqual([(t.index, t.text) for t in turns], [(0, "Real opening message"), (1, "shorter")])


class WebApp(unittest.TestCase):
    """The browser flow calls the same functions as the terminal and never shows the method before the choice."""

    def setUp(self):
        import webapp
        self.webapp = webapp
        self.dir = Path(tempfile.mkdtemp())
        turns = [DayTurn(day, m, f"please keep it short, request {m} on day {day}", f"s{day % 6}")
                 for day in range(45) for m in range(8)]
        for day in (40, 42):                                   # two recent chats to offer as own-chat tasks
            turns.append(DayTurn(day, 30, f"Explain option {day} to a new teammate in plain words, with one example "
                                          "for each of the options we discussed", f"open{day}"))
            turns[-1].index = 0
        self.patch = mock.patch.object(study, "load_turns", lambda a: turns)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.app = webapp.App(self.dir, "my-study", engine="claude", source=self.dir)
        self.app.ensure_inputs()

    def fake_model(self, engine, prompt, model, system=None):
        import re
        rows_ = json.loads(prompt.split("History:\n", 1)[1].split("\nObservations:", 1)[0]) if "History:" in prompt else []
        ids = [r["id"] for r in rows_]
        if "Identify only explicit steering" in prompt:
            return json.dumps([{"id": i, "rule": "short", "scope": "reusable"} for i in ids])
        if rows_:
            return json.dumps([{"title": f"Item {k}", "type": "principle" if k else "skill", "kind": "preference",
                                "when": f"w{k}", "instruction": f"i{k}", "evidence": ids} for k in range(2)])
        return "answer with guidance" if "Guidance you have loaded" in prompt else "plain answer"

    def test_whole_flow_writes_the_same_share_files(self):
        app = self.app
        self.assertEqual(app.phase(), "review")
        state = app.state()
        self.assertTrue(state["days"] and state["common"])
        with self.assertRaises(ValueError):
            app.do_start({})                                    # nothing can be sent before the review
        first = state["days"][0][0]["id"]
        app.do_review({"remove_messages": [first], "remove_tasks": [], "own_question": "Plan my talk, see https://x.io"})
        self.assertNotIn(first, [r["id"] for r in study.read_json(app.history)])
        tasks_ = study.read_json(app.tasks)
        self.assertEqual(tasks_[-1]["task_id"], "O1")
        self.assertIn("[URL]", tasks_[-1]["opening_prompt"])
        self.assertEqual(app.phase(), "start")
        with mock.patch.object(study, "run_model", self.fake_model):
            app.do_start({})
            while app.job["running"]:
                pass
        self.assertEqual(app.job["error"], "")
        self.assertEqual(app.phase(), "compare")
        state = app.state()
        text = json.dumps(state["tasks"]) + json.dumps(state["job"])
        for secret in ('"A"', '"B"', '"C"', "direct", "structured", "rubric"):
            self.assertNotIn(secret, text)                      # only slots X, Y, Z reach the browser
        with self.assertRaisesRegex(ValueError, "why"):
            app.do_compare({"task_id": "T1", "best": "X", "worst": "Y", "clarity": "clear", "tags": [], "reason": ""})
        for task in state["tasks"]:
            if task["task_id"] == "T2":
                app.do_compare({"task_id": "T2", "result": "tie", "reason": "same"})
            else:
                app.do_compare({"task_id": task["task_id"], "best": "X", "worst": "Y", "clarity": "slight",
                                "tags": ["accurate", "nonsense"], "reason": "more exact"})
        r = rows(app.folder / "compare.share.csv")
        self.assertEqual(r[0]["reason_tags"], "accurate")
        self.assertEqual([x["result"] for x in r if x["task_id"] == "T2"], ["tie"])
        self.assertEqual(app.phase(), "confirm")
        cards = app.state()["cards"]
        self.assertNotIn("method", json.dumps(cards))
        decisions = {c["card_id"]: {"decision": "keep", "comment": "me"} for c in cards}
        with self.assertRaisesRegex(ValueError, "closing questions"):
            app.do_confirm({"decisions": decisions, "reflection": {"surprise": "x", "missing": ""}})
        app.do_confirm({"decisions": decisions, "reflection": {"surprise": "x", "missing": "none"},
                        "added": [{"title": "Mine", "type": "principle", "when": "w", "instruction": "i"}]})
        self.assertEqual([d["comment"] for d in rows(app.folder / "decisions.share.csv")][:1], ["me"])
        sets = app.state()["sets"]
        self.assertEqual(set(sets), {"X", "Y"})
        self.assertNotIn("direct", json.dumps(sets))
        app.do_choose({"pick": "x", "reason": "closer", "comments": ""})
        self.assertEqual(app.phase(), "done")
        choice = rows(app.folder / "choice.share.csv")[0]
        self.assertEqual((choice["surprise"], choice["missing"]), ("x", "none"))
        import zipfile
        names = sorted(zipfile.ZipFile(app.folder / "study_files.zip").namelist())
        self.assertEqual(names, sorted(study.SHARE_FILES))
        self.assertTrue((app.folder / "my-skills" / "principles.md").exists())

    def test_server_needs_the_token(self):
        import threading, urllib.request, urllib.error
        _, server = self.webapp.serve(self.dir, "my-study", "claude", self.dir)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        base = f"http://127.0.0.1:{server.server_address[1]}"
        page = urllib.request.urlopen(base + "/").read().decode()
        token = page.split('const TOKEN = "')[1].split('"')[0]
        with self.assertRaises(urllib.error.HTTPError):
            urllib.request.urlopen(base + "/api/state")
        req = urllib.request.Request(base + "/api/state", headers={"X-Study-Token": token})
        self.assertEqual(json.loads(urllib.request.urlopen(req).read())["phase"], "review")
        self.assertEqual(server.server_address[0], "127.0.0.1")
