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


def _codex(ts, kind, cid, **payload):
    return json.dumps({"timestamp": ts, "type": "response_item",
                       "payload": dict(payload, type=kind, call_id=cid)})


class TestFormats(unittest.TestCase):
    """Three transcript formats, one Event. Shapes taken from real files."""

    def codex_lines(self):
        return [
            json.dumps({"timestamp": T % 0, "type": "session_meta", "payload": {"id": "x"}}),
            _codex(T % 1, "function_call", "c1", name="exec_command",
                   arguments=json.dumps({"cmd": "python run.py 数据.jsonl"})),   # ASCII-escaped
            _codex(T % 2, "function_call_output", "c1",
                   output=[{"type": "input_text", "text": "p=0.01"}]),
            _codex(T % 3, "custom_tool_call", "c2", name="exec",
                   input="await tools.shell_command({command: 'ls'})"),
            _codex(T % 4, "custom_tool_call_output", "c2", output="done"),
            json.dumps({"timestamp": T % 5, "type": "event_msg", "payload": {"type": "token_count"}}),
        ]

    def test_codex_calls_and_outputs_pair_by_call_id(self):
        t = ta.events_from_codex(self.codex_lines())
        self.assertEqual(t.format, "codex")
        self.assertEqual([(e.kind, e.tool) for e in t.events],
                         [("call", "exec_command"), ("output", "exec_command"),
                          ("call", "exec"), ("output", "exec")])
        self.assertEqual(t.events[1].text, "p=0.01")       # input_text blocks are read
        # Arguments are re-serialised so a pattern for a non-ASCII path matches
        # without knowing the source escaped it.
        self.assertIn("数据.jsonl", t.events[0].text)

    def test_generic_schema_and_its_required_fields(self):
        lines = [json.dumps({"ts": T % 1, "kind": "call", "tool": "shell",
                             "text": {"cmd": "python a.py"}, "call_id": "1"}),
                 json.dumps({"ts": T % 2, "kind": "output", "text": "ok", "call_id": "1"}),
                 json.dumps({"ts": T % 3, "kind": "call"}),           # no text
                 json.dumps({"kind": "call", "text": "x"}),           # no ts
                 json.dumps(["not", "an", "object"])]
        t = ta.events_from_jsonl(lines)
        self.assertEqual(len(t.events), 2)
        self.assertEqual(t.skipped_lines, 3)
        self.assertIn('"cmd"', t.events[0].text)

    def test_load_trace_detects_each_format(self):
        self.assertEqual(ta.load_trace(self.codex_lines()).format, "codex")
        cc = [json.dumps({"type": "mode", "sessionId": "s"}),
              _call(T % 1, "a", "Bash", command="x")]
        t = ta.load_trace(cc)
        self.assertEqual((t.format, len(t.events)), ("claude_code", 1))
        ev = [json.dumps({"ts": T % 1, "kind": "call", "text": "x"})]
        self.assertEqual(ta.load_trace(ev).format, "events")
        with self.assertRaises(ValueError):
            ta.load_trace(["{}", "[]"])
        with self.assertRaises(ValueError):
            ta.load_trace(cc, format="langchain")

    def test_non_reading_tools_follow_the_format(self):
        lines = [
            _codex(T % 1, "custom_tool_call", "p", name="apply_patch",
                   input="*** Add File: analyse.py\n+open('fresh.jsonl')"),
            _codex(T % 2, "function_call", "s", name="exec_command",
                   arguments=json.dumps({"cmd": "cat > PREREG.md"})),
        ]
        t = ta.events_from_codex(lines)
        r = ta.seal_check(t, seal=r"PREREG", holdout=HOLD)
        self.assertEqual(r.verdict, "untouched")             # apply_patch is not a read
        g = ta.Trace(t.events, 0, "events")                   # generic: nothing assumed
        self.assertEqual(ta.seal_check(g, seal=r"PREREG", holdout=HOLD).verdict,
                         "touched_before_seal")


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


def _user(ts, content, **extra):
    return json.dumps(dict({"type": "user", "timestamp": ts,
                            "message": {"role": "user", "content": content}}, **extra))


class TestHumanTurns(unittest.TestCase):
    """Whether a person intervened is in the log; gaps read it instead of guessing."""

    def test_claude_code_keeps_typed_turns_and_drops_injected_ones(self):
        t = trace(
            _user(T % 1, "可以开工"),
            _user(T % 2, [{"type": "text", "text": "run it again"}]),
            _user(T % 3, "<system-reminder>x</system-reminder>"),
            _user(T % 4, "This session is being continued from a previous conversation"),
            _user(T % 5, "meta", isMeta=True),
            _user(T % 6, [{"type": "tool_result", "tool_use_id": "a", "content": "ok"}]),
        )
        prompts = [e.text for e in t.events if e.kind == "prompt"]
        self.assertEqual(prompts, ["可以开工", "run it again"])

    def test_codex_user_messages_are_prompts(self):
        t = ta.events_from_codex([json.dumps({
            "timestamp": T % 1, "type": "event_msg",
            "payload": {"type": "user_message", "message": "try fdv"}})])
        self.assertEqual([(e.kind, e.text) for e in t.events], [("prompt", "try fdv")])

    def test_generic_records_prompts_only_if_it_has_any(self):
        no = ta.events_from_jsonl([json.dumps({"ts": T % 1, "kind": "call", "text": "x"})])
        yes = ta.events_from_jsonl([json.dumps({"ts": T % 1, "kind": "prompt", "text": "go"})])
        self.assertFalse(no.records_prompts)
        self.assertTrue(yes.records_prompts)

    def test_gap_says_who_moved(self):
        lines = [
            _call(T % 1, "a", "Bash", command="python s.py"),
            _out(T % 2, "a", "-> FALSIFY"),
            _call(T % 3, "b", "Write", file_path="next.py", content=""),   # agent alone
            _call(T % 4, "c", "Bash", command="python next.py"),
            _out(T % 5, "c", "-> SUPPORT"),
            _user(T % 6, "check fdv too"),
            _call(T % 7, "d", "Write", file_path="fdv.py", content=""),    # after a human
        ]
        g = ta.gaps(trace(*lines), result=r"-> [A-Z]+", start=r'"file_path"')
        self.assertEqual([x.human_between for x in g], [False, True])
        # A format with no human turns cannot say; it must not say False.
        generic = ta.Trace([e for e in trace(*lines).events if e.kind != "prompt"],
                           0, "events", records_prompts=False)
        g2 = ta.gaps(generic, result=r"-> [A-Z]+", start=r'"file_path"')
        self.assertEqual([x.human_between for x in g2], [None, None])

    def test_prompts_are_not_events_for_counting_or_sealing(self):
        t = trace(_user(T % 1, "python backtest.py fresh.jsonl please"),
                  _call(T % 2, "a", "Write", file_path="PREREG.md", content="x"))
        tab = ta.count_units(t, [ta.Unit("runs", "call", "backtest")])
        self.assertIsNone(tab.row("runs").trials)
        self.assertEqual(ta.seal_check(t, seal=SEAL, holdout=HOLD).verdict, "untouched")
        out = ta.audit(t, units=[ta.Unit("runs", "call", "backtest")])
        self.assertEqual((out["events"], out["human_turns"]), (1, 1))


class TestAuditAndWindow(unittest.TestCase):
    def setUp(self):
        self.t = trace(
            _call(T % 1, "a", "Write", file_path="PREREG.md", content="x"),
            _call(T % 2, "b", "Bash", command="python run.py fresh.jsonl"),
            _out(T % 3, "b", "p=0.04 => SUPPORT"),
            _call(T % 9, "c", "Bash", command="python run2.py"),
        )

    def test_window_is_inclusive_and_takes_naive_times_as_utc(self):
        from datetime import datetime
        w = ta.window(self.t, datetime(2026, 10, 7, 16, 2), datetime(2026, 10, 7, 16, 3))
        self.assertEqual([e.call_id for e in w.events], ["b", "b"])
        self.assertEqual(w.format, self.t.format)

    def test_audit_is_json_safe_and_has_no_total(self):
        out = ta.audit(self.t, units=[ta.Unit("runs", "call", "python")],
                       seal=SEAL, holdout=HOLD,
                       gap_result="SUPPORT", gap_start="python")
        json.dumps(out)                                   # must not raise
        self.assertNotIn("count", out)
        self.assertEqual(out["spread"], [2, 2])
        self.assertEqual(out["seal"]["verdict"], "sealed_first")
        self.assertEqual(out["gaps"][0]["seconds"], 360.0)

    def test_audit_rejects_half_pairs_and_empty_requests(self):
        for kw in ({"seal": SEAL}, {"holdout": HOLD}, {"gap_result": "x"}, {}):
            with self.assertRaises(ValueError):
                ta.audit(self.t, **kw)


if __name__ == "__main__":
    unittest.main()
