"""Tests for reading an agent's trace.

Two claims are guarded here beyond the arithmetic. First, that the unit table
cannot be collapsed to one number by accident — the version of this module that
would be easiest to misuse is the one with a ``.count``. Second, that the seal
verdict separates an amended plan from a late one and carries what each early
touch got back, since the verdict alone cannot say whether a touch saw anything.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import trace_audit as ta


def _call(ts, cid, name, **inp):
    return json.dumps({"timestamp": ts, "message": {"content": [
        {"type": "tool_use", "id": cid, "name": name, "input": inp}]}})


def _out(ts, cid, body):
    return json.dumps({"timestamp": ts, "message": {"content": [
        {"type": "tool_result", "tool_use_id": cid, "content": body}]}})


T = "2026-10-07T16:%02d:00Z"


def trace(*lines):
    return ta.events_from_claude_code(lines)


class TestParse(unittest.TestCase):
    def test_pairs_results_with_their_tool_and_sorts(self):
        t = trace(_out(T % 2, "a", [{"type": "text", "text": "ok"}]),
                  _call(T % 1, "a", "Bash", command="python run.py"))
        self.assertEqual([e.kind for e in t.events], ["call", "output"])
        self.assertEqual(t.events[1].tool, "Bash")
        self.assertEqual(t.events[1].text, "ok")

    def test_unparseable_lines_are_counted_not_dropped(self):
        t = trace("{not json", _call(T % 1, "a", "Bash", command="x"), "")
        self.assertEqual(t.skipped_lines, 1)
        self.assertEqual(len(t.events), 1)

    def test_entries_without_tool_blocks_are_ignored(self):
        t = trace(json.dumps({"type": "mode", "mode": "normal"}),
                  json.dumps({"timestamp": T % 1, "message": {"content": "plain text"}}))
        self.assertEqual(t.events, [])
        self.assertEqual(t.skipped_lines, 0)


class TestUnits(unittest.TestCase):
    def setUp(self):
        self.t = trace(
            _call(T % 1, "a", "Bash", command="python backtest.py"),
            _out(T % 2, "a", "p=0.01 => SUPPORT\np=0.40\np=0.70"),
            _call(T % 3, "b", "Bash", command="python backtest.py"),   # identical rerun
            _out(T % 4, "b", "p=0.01 => SUPPORT\np=0.40\np=0.70"),
            _call(T % 5, "c", "Bash", command="python replication.py"),
            _out(T % 6, "c", "p=0.02 => FALSIFY\np=0.33"),
        )
        self.units = [ta.Unit("runs", "call", r"python \S+\.py"),
                      ta.Unit("verdicts", "output", r"=> [A-Z]+"),
                      ta.Unit("stats", "output", r"p=0\.\d+")]

    def test_each_unit_is_its_own_lower_bound_count(self):
        tab = ta.count_units(self.t, self.units)
        self.assertEqual(tab.row("runs").trials.count, 2)      # rerun counts once
        self.assertEqual(tab.row("runs").matches, 3)
        self.assertEqual(tab.row("verdicts").trials.count, 2)
        self.assertEqual(tab.row("stats").trials.count, 5)
        for r in tab.rows:
            self.assertEqual(r.trials.provenance, "log")
            self.assertTrue(r.trials.blind_to)                  # never claims completeness
            self.assertIn(r.unit.name, r.trials.derivation)

    def test_there_is_no_single_total_to_quote(self):
        tab = ta.count_units(self.t, self.units)
        self.assertFalse(hasattr(tab, "count"))
        self.assertEqual(tab.spread, (2, 5))
        self.assertIn("2", tab.note())
        self.assertIn("5", tab.note())
        self.assertIn("2.5", tab.note())

    def test_no_match_is_none_not_zero(self):
        tab = ta.count_units(self.t, [ta.Unit("runs", "call", r"python \S+\.py"),
                                      ta.Unit("ghost", "output", r"NEVER")])
        self.assertIsNone(tab.row("ghost").trials)
        self.assertEqual(tab.spread, (2, 2))
        none = ta.count_units(self.t, [ta.Unit("ghost", "call", "NEVER")])
        self.assertIsNone(none.spread)
        self.assertIn("not zero", none.note())

    def test_the_caller_must_name_the_unit(self):
        with self.assertRaises(ValueError):
            ta.count_units(self.t, [])
        with self.assertRaises(ValueError):
            ta.count_units(self.t, [ta.Unit("x", "call", "a"), ta.Unit("x", "call", "b")])
        with self.assertRaises(ValueError):
            ta.Unit("x", "file", "a")
        with self.assertRaises(Exception):
            ta.Unit("x", "call", "(")

    def test_skipped_lines_reach_the_blind_spots(self):
        t = trace("{broken", *[l for l in (
            _call(T % 1, "a", "Bash", command="python backtest.py"),)])
        tab = ta.count_units(t, [ta.Unit("runs", "call", "backtest")])
        self.assertTrue(any("1" in b for b in tab.row("runs").trials.blind_to))

    def test_note_renders_in_chinese(self):
        tab = ta.count_units(self.t, self.units, lang="zh")
        self.assertIn("倍", tab.note())


SEAL = r'"file_path": "[^"]*PREREG'
HOLD = r"fresh\.jsonl"


class TestSeal(unittest.TestCase):
    def _t(self, *events):
        return trace(*events)

    def test_unsealed(self):
        r = ta.seal_check(self._t(_call(T % 1, "a", "Bash", command="cat fresh.jsonl")),
                          seal=SEAL, holdout=HOLD)
        self.assertEqual(r.verdict, "unsealed")
        self.assertEqual(len(r.touches), 1)

    def test_untouched(self):
        r = ta.seal_check(self._t(_call(T % 1, "a", "Write", file_path="PREREG.md", content="x")),
                          seal=SEAL, holdout=HOLD)
        self.assertEqual(r.verdict, "untouched")

    def test_sealed_first(self):
        r = ta.seal_check(self._t(
            _call(T % 1, "a", "Write", file_path="PREREG.md", content="x"),
            _call(T % 2, "b", "Bash", command="python analyse.py fresh.jsonl")),
            seal=SEAL, holdout=HOLD)
        self.assertEqual(r.verdict, "sealed_first")
        self.assertEqual(r.touches_before_last_seal, [])

    def test_amended_after_touch_is_distinct_from_late(self):
        between = ta.seal_check(self._t(
            _call(T % 1, "a", "Write", file_path="PREREG.md", content="x"),
            _call(T % 2, "b", "Bash", command="capture --out fresh.jsonl"),
            _call(T % 3, "c", "Write", file_path="PREREG.md", content="x + addendum")),
            seal=SEAL, holdout=HOLD)
        self.assertEqual(between.verdict, "touched_between")
        self.assertEqual(len(between.touches_before_last_seal), 1)
        late = ta.seal_check(self._t(
            _call(T % 1, "b", "Bash", command="head fresh.jsonl"),
            _call(T % 2, "a", "Write", file_path="PREREG.md", content="x")),
            seal=SEAL, holdout=HOLD)
        self.assertEqual(late.verdict, "touched_before_seal")

    def test_a_plan_that_names_the_holdout_is_not_a_touch(self):
        r = ta.seal_check(self._t(
            _call(T % 1, "a", "Write", file_path="PREREG.md", content="test on fresh.jsonl")),
            seal=SEAL, holdout=HOLD)
        self.assertEqual(r.verdict, "untouched")

    def test_writing_a_script_that_names_the_holdout_is_not_a_touch(self):
        r = ta.seal_check(self._t(
            _call(T % 1, "a", "Write", file_path="analyse.py", content="open('fresh.jsonl')"),
            _call(T % 2, "b", "Write", file_path="PREREG.md", content="x")),
            seal=SEAL, holdout=HOLD)
        self.assertEqual(r.verdict, "untouched")
        # ...unless the caller says Write counts
        r2 = ta.seal_check(self._t(
            _call(T % 1, "a", "Write", file_path="analyse.py", content="open('fresh.jsonl')"),
            _call(T % 2, "b", "Write", file_path="PREREG.md", content="x")),
            seal=SEAL, holdout=HOLD, exclude_tools=())
        self.assertEqual(r2.verdict, "touched_before_seal")

    def test_each_early_touch_carries_what_it_got_back(self):
        r = ta.seal_check(self._t(
            _call(T % 1, "a", "Write", file_path="PREREG.md", content="x"),
            _call(T % 2, "b", "Bash", command="capture --out fresh.jsonl"),
            _out(T % 2, "b", "Command running in background"),
            _call(T % 3, "c", "Write", file_path="PREREG.md", content="x2")),
            seal=SEAL, holdout=HOLD)
        early = r.touches_before_last_seal[0]
        self.assertIn("background", r.output_of(early).text)
        self.assertTrue(r.blind_to)

    def test_notes_render_for_every_verdict(self):
        for v in ta.SEAL_VERDICTS:
            for lang in ("en", "zh"):
                rep = ta.SealReport(v, [], [], [], lang=lang)
                self.assertTrue(rep.note())


class TestGaps(unittest.TestCase):
    def test_raw_seconds_to_the_next_matching_call(self):
        t = trace(
            _call(T % 1, "a", "Bash", command="python strata.py"),
            _out("2026-10-07T16:01:10Z", "a", "median drop 9% -> FALSIFY"),
            _call("2026-10-07T16:01:27Z", "b", "Write", file_path="explore.py", content=""),
            _call(T % 5, "c", "Bash", command="python explore.py"),
            _out(T % 6, "c", "-> SUPPORT"),
        )
        g = ta.gaps(t, result=r"-> [A-Z]+", start=r'"file_path"')
        self.assertEqual(len(g), 2)
        self.assertEqual(g[0].seconds, 17.0)
        self.assertIn("FALSIFY", g[0].result_line)
        self.assertIsNone(g[1].next_call)
        self.assertIsNone(g[1].seconds)


if __name__ == "__main__":
    unittest.main()
