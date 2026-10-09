"""Read an agent's execution trace for the two things a research summary leaves out.

An agent that runs a study for hours reports a result. The trace behind it holds
what the result cannot: how many things were tried before this one, and whether
the data held back for the final test was looked at before the plan was fixed.
A human researcher keeps both in their head, where nobody can recount them. An
agent leaves them in a log — every experiment is a tool call with a timestamp —
which makes this the one setting where ``trial_count``'s ``log`` provenance is
the natural case rather than the rare one.

Two questions, answered from the trace and nothing else:

``count_units``
    How many trials? **Not one number.** Run on a real trace, the count moves
    by an order of magnitude depending on what one trial is taken to be —
    script runs, hypotheses, verdict lines, individual statistics — and the
    trace does not say which unit is right. So the caller names each unit as a
    pattern, every unit comes back as its own ``TrialCount``, and the result has
    no single ``count`` attribute to quote. The spread is reported instead,
    because the spread is the finding.

``seal_check``
    Was the held-out data touched before the plan was sealed? The caller names
    which calls seal the plan (writing a preregistration, say) and which calls
    touch the holdout. The answer is an ordering of timestamps, so it is
    arithmetic, not judgement — and every matched event is returned alongside
    the verdict, because a wrong pattern produces a confident wrong verdict and
    the only defence is that a reader can see what was matched.

``gaps``
    How soon after seeing a result did the next analysis start? Returned as raw
    intervals with no threshold and no verdict. A short gap is what "adjusting
    direction on intermediate results" looks like in a log; how short is too
    short has not been measured, and a threshold invented here would be quoted
    later as if it had been.

What none of these can see, and every report says so: a script that reads a
file internally without naming it on the command line; the content of tool
output (a touch is detected from the call, not from what came back); whether a
touch was a read or a write. Patterns are regular expressions over the call's
JSON input, so they inherit every blind spot of a regex.

Stdlib only. No filesystem — callers pass lines in. Three parsers yield the
same ``Event``: ``events_from_claude_code`` (Claude Code session JSONL),
``events_from_codex`` (Codex CLI rollout JSONL) and ``events_from_jsonl``, a
plain one-event-per-line schema for any other harness — an OpenAI Agents SDK
run, a LangGraph trace — so that supporting one means writing a ten-line
exporter, not a parser here. ``load_trace`` picks one.

**Patterns are harness-specific.** Tool names differ (``Bash`` and ``Write`` in
Claude Code, ``shell_command`` and ``apply_patch`` in Codex) and so does the
JSON a call is serialised to, so a pattern written against one transcript
format will not match another. That is also why which tools count as
non-reading is looked up per format rather than fixed.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import trial_count as tc
from messages import resolve_lang, text

__all__ = [
    "Event",
    "Trace",
    "Unit",
    "UnitRow",
    "UnitTable",
    "SealReport",
    "Gap",
    "events_from_claude_code",
    "events_from_codex",
    "events_from_jsonl",
    "load_trace",
    "FORMATS",
    "NON_READING_TOOLS_BY_FORMAT",
    "count_units",
    "seal_check",
    "gaps",
    "window",
    "audit",
    "SEAL_VERDICTS",
    "NON_READING_TOOLS",
]

SEAL_VERDICTS = (
    "unsealed",              # no sealing event matched
    "untouched",             # sealed, holdout never touched in the trace
    "sealed_first",          # every touch comes after the last seal
    "touched_between",       # plan amended after the holdout was first touched
    "touched_before_seal",   # holdout touched before the plan existed
)

# Tools that create or modify files without reading data. A Write whose content
# names the holdout path is a script being written, not data being looked at.
NON_READING_TOOLS = ("Write", "Edit", "NotebookEdit")
NON_READING_TOOLS_BY_FORMAT = {
    "claude_code": NON_READING_TOOLS,
    "codex": ("apply_patch",),
    # A generic trace names its own tools; nothing can be assumed about them.
    "events": (),
}
FORMATS = tuple(NON_READING_TOOLS_BY_FORMAT)


@dataclass
class Event:
    """One tool call or one tool result, in trace order.

    ``text`` is the call's input serialised as JSON (for calls) or the result's
    text (for outputs). Patterns match against it, so what a pattern can see is
    exactly what is in this string.
    """
    ts: datetime
    kind: str            # "call" | "output" | "prompt" (a human turn)
    tool: str
    text: str
    call_id: str = ""

    def excerpt(self, n: int = 100) -> str:
        s = " ".join(self.text.split())
        return s if len(s) <= n else s[: n - 1] + "…"


@dataclass
class Trace:
    events: List[Event]
    skipped_lines: int = 0      # lines that were not valid JSON or had no timestamp
    format: str = "claude_code"
    # Whether this format records human turns at all. When it does not, "no
    # prompt between two events" means nothing, and gaps report None.
    records_prompts: bool = True


def _ts(raw: str) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


# Text a harness injects as a "user" turn that no human typed: compaction
# summaries, slash-command echoes, system reminders, interruption markers.
_INJECTED = ("<", "This session is being continued", "Caveat:", "[Request interrupted")


def _human_text(content: Any) -> Optional[str]:
    if isinstance(content, list):
        content = " ".join(b.get("text", "") for b in content
                           if isinstance(b, dict) and b.get("type") == "text")
    if not isinstance(content, str) or not content.strip():
        return None
    if content.lstrip().startswith(_INJECTED):
        return None
    return content


def _result_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(c.get("text", "") for c in content
                         if isinstance(c, dict) and c.get("type") in ("text", "input_text"))
    return ""


def events_from_claude_code(lines: Iterable[str]) -> Trace:
    """Parse a Claude Code session transcript (one JSON object per line).

    A line that does not parse is counted in ``skipped_lines`` rather than
    dropped silently: a truncated transcript should show up as a number in the
    report, not as fewer trials.
    """
    events: List[Event] = []
    tools: Dict[str, str] = {}
    skipped = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            skipped += 1
            continue
        content = (d.get("message") or {}).get("content")
        ts = _ts(d.get("timestamp", ""))
        if d.get("type") == "user" and not d.get("isMeta") and ts is not None:
            human = _human_text(content)
            if human is not None:
                events.append(Event(ts, "prompt", "", human))
        if not isinstance(content, list):
            continue
        for b in content:
            if not isinstance(b, dict):
                continue
            kind = b.get("type")
            if kind not in ("tool_use", "tool_result"):
                continue
            if ts is None:
                skipped += 1
                continue
            if kind == "tool_use":
                cid = b.get("id", "")
                name = b.get("name", "")
                tools[cid] = name
                events.append(Event(ts, "call", name,
                                    json.dumps(b.get("input", {}), ensure_ascii=False), cid))
            else:
                cid = b.get("tool_use_id", "")
                events.append(Event(ts, "output", "",
                                    _result_text(b.get("content")), cid))
    # Name outputs after parsing, so a result written before its call still
    # gets the right tool.
    for e in events:
        if e.kind == "output":
            e.tool = tools.get(e.call_id, "")
    events.sort(key=lambda e: e.ts)
    return Trace(events, skipped, "claude_code")


def _canonical_json(raw: Any) -> str:
    """Re-serialise JSON the way the Claude Code parser does.

    Codex stores arguments as a JSON string, often with non-ASCII escaped. A
    pattern for a Chinese path should not have to know that.
    """
    if isinstance(raw, str):
        try:
            return json.dumps(json.loads(raw), ensure_ascii=False)
        except ValueError:
            return raw
    return json.dumps(raw, ensure_ascii=False)


def events_from_codex(lines: Iterable[str]) -> Trace:
    """Parse a Codex CLI rollout (``~/.codex/sessions/**/rollout-*.jsonl``).

    Calls are ``function_call`` (``arguments`` is a JSON string) and
    ``custom_tool_call`` (``input`` is free text — for ``exec`` it is the
    script that in turn calls the shell). Outputs are the matching
    ``*_output`` items, joined to their call by ``call_id``.
    """
    events: List[Event] = []
    tools: Dict[str, str] = {}
    skipped = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            skipped += 1
            continue
        if not isinstance(d, dict):
            continue
        p = d.get("payload") or {}
        if d.get("type") == "event_msg" and p.get("type") == "user_message":
            t = _ts(d.get("timestamp", ""))
            if t is not None:
                events.append(Event(t, "prompt", "", str(p.get("message", ""))))
            continue
        if d.get("type") != "response_item":
            continue
        kind = p.get("type")
        if kind not in ("function_call", "custom_tool_call",
                        "function_call_output", "custom_tool_call_output"):
            continue
        ts = _ts(d.get("timestamp", ""))
        if ts is None:
            skipped += 1
            continue
        cid = p.get("call_id", "")
        if kind.endswith("_output"):
            events.append(Event(ts, "output", "", _result_text(p.get("output")), cid))
            continue
        name = p.get("name", "")
        tools[cid] = name
        if kind == "function_call":
            body = _canonical_json(p.get("arguments", ""))
        else:
            body = str(p.get("input", ""))
        events.append(Event(ts, "call", name, body, cid))
    for e in events:
        if e.kind == "output":
            e.tool = tools.get(e.call_id, "")
    events.sort(key=lambda e: e.ts)
    return Trace(events, skipped, "codex")


def events_from_jsonl(lines: Iterable[str]) -> Trace:
    """Parse the generic schema: one event per line.

        {"ts": "2026-10-07T16:04:08Z", "kind": "call",   "tool": "shell",
         "text": "python analyse.py fresh.jsonl", "call_id": "c1"}
        {"ts": "2026-10-07T16:04:09Z", "kind": "output", "tool": "shell",
         "text": "...", "call_id": "c1"}

    ``kind`` is ``call``, ``output`` or ``prompt`` (a turn a human typed —
    include these if the harness has them, or ``gaps`` cannot say whether a
    person intervened). ``ts``, ``kind`` and ``text`` are required; a line missing one is counted
    in ``skipped_lines``. ``text`` may be any JSON value and is serialised.
    """
    events: List[Event] = []
    skipped = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            skipped += 1
            continue
        if not isinstance(d, dict):
            skipped += 1
            continue
        ts = _ts(str(d.get("ts", "")))
        kind = d.get("kind")
        if ts is None or kind not in ("call", "output", "prompt") or "text" not in d:
            skipped += 1
            continue
        body = d["text"]
        events.append(Event(ts, kind, str(d.get("tool", "")),
                            body if isinstance(body, str) else _canonical_json(body),
                            str(d.get("call_id", ""))))
    events.sort(key=lambda e: e.ts)
    # A generic exporter may or may not include human turns; only their
    # presence shows that it does.
    return Trace(events, skipped, "events",
                 records_prompts=any(e.kind == "prompt" for e in events))


_PARSERS = {"claude_code": events_from_claude_code,
            "codex": events_from_codex,
            "events": events_from_jsonl}


def _sniff(line: str) -> Optional[str]:
    try:
        d = json.loads(line)
    except ValueError:
        return None
    if not isinstance(d, dict):
        return None
    if "kind" in d and "ts" in d:
        return "events"
    if d.get("type") in ("session_meta", "response_item", "event_msg", "turn_context"):
        return "codex"
    if "sessionId" in d or "message" in d:
        return "claude_code"
    return None


def load_trace(lines: Iterable[str], format: Optional[str] = None) -> Trace:
    """Parse with the named format, or detect it from the first lines.

    Detection reads up to 50 lines and takes the first recognisable one. It is
    a convenience, not a guess that hides itself: the returned ``Trace``
    carries the format it used, and a wrong format shows up as zero events.
    """
    it = iter(lines)
    head: List[str] = []
    if format is None:
        for line in it:
            head.append(line)
            format = _sniff(line.strip()) if line.strip() else None
            if format or len(head) >= 50:
                break
        if format is None:
            raise ValueError("could not detect the transcript format; pass format= "
                             "one of " + ", ".join(FORMATS))
    if format not in _PARSERS:
        raise ValueError(f"format must be one of {FORMATS}, got {format!r}")

    def chained():
        yield from head
        yield from it
    return _PARSERS[format](chained())


# ---- how many trials -------------------------------------------------------

@dataclass
class Unit:
    """One candidate definition of "a trial".

    ``kind="call"``: each distinct matching tool call is one trial (an identical
    command run twice is one). ``kind="output"``: each distinct matching line of
    tool output is one trial (an identical line printed twice is one).
    """
    name: str
    kind: str
    pattern: str

    def __post_init__(self) -> None:
        if self.kind not in ("call", "output"):
            raise ValueError(f"unit {self.name!r}: kind must be 'call' or 'output'")
        re.compile(self.pattern)


@dataclass
class UnitRow:
    unit: Unit
    matches: int
    trials: Optional[tc.TrialCount]     # None when nothing matched — not zero


@dataclass
class UnitTable:
    """Counts under several definitions of a trial — deliberately with no total.

    There is no ``count`` property. A caller who wants one number has to pick a
    row by name, which puts the choice of unit in their code where it can be
    read, instead of in this module where it would be a default.
    """
    rows: List[UnitRow]
    lang: str = "en"

    def row(self, name: str) -> UnitRow:
        for r in self.rows:
            if r.unit.name == name:
                return r
        raise KeyError(name)

    @property
    def spread(self) -> Optional[Tuple[int, int]]:
        counts = [r.trials.count for r in self.rows if r.trials is not None]
        return (min(counts), max(counts)) if counts else None

    def note(self, lang: str = None) -> str:
        lang = resolve_lang(lang or self.lang)
        sp = self.spread
        if sp is None:
            return text("trace.spread_none", lang)
        lo, hi = sp
        if lo == hi:
            return text("trace.spread_flat", lang, n=lo)
        return text("trace.spread", lang, lo=lo, hi=hi, ratio=f"{hi / lo:.1f}")


def count_units(trace: Trace, units: Sequence[Unit], *, lang: str = None) -> UnitTable:
    """Count trials under each unit. Nothing is summed across units."""
    if not units:
        raise ValueError("name at least one unit — this module will not choose one")
    lang = resolve_lang(lang)
    names = [u.name for u in units]
    if len(set(names)) != len(names):
        raise ValueError("unit names must be distinct")
    coverage = text("trace.blind_coverage", lang)
    rows: List[UnitRow] = []
    for u in units:
        rx = re.compile(u.pattern)
        keys: List[Dict[str, str]] = []
        for e in trace.events:
            if e.kind != u.kind:
                continue
            if u.kind == "call":
                if rx.search(e.text):
                    keys.append({"k": " ".join(e.text.split())})
            else:
                for ln in e.text.splitlines():
                    if rx.search(ln):
                        keys.append({"k": ln.strip()})
        if not keys:
            rows.append(UnitRow(u, 0, None))
            continue
        t = tc.from_runs(keys, fields=["k"], coverage=coverage, lang=lang)
        t.derivation = f"{u.name}: {t.derivation}, pattern /{u.pattern}/ on {u.kind}s"
        if trace.skipped_lines:
            t.blind_to.append(text("trace.blind_skipped", lang, n=trace.skipped_lines))
        rows.append(UnitRow(u, len(keys), t))
    return UnitTable(rows, lang)


# ---- was the holdout touched before the plan was sealed --------------------

@dataclass
class SealReport:
    verdict: str
    seals: List[Event]
    touches: List[Event]
    touches_before_last_seal: List[Event]
    blind_to: List[str] = field(default_factory=list)
    lang: str = "en"
    # What each touch got back, keyed by call id. A touch whose output is a
    # "started in background" notice showed nothing; one whose output is a
    # table of results may have shown everything. The verdict cannot tell
    # these apart — this is what lets a reader do it in seconds.
    outputs: Dict[str, Event] = field(default_factory=dict)

    def output_of(self, touch: Event) -> Optional[Event]:
        return self.outputs.get(touch.call_id)

    def note(self, lang: str = None) -> str:
        lang = resolve_lang(lang or self.lang)
        fmt = lambda e: e.ts.strftime("%Y-%m-%d %H:%M:%S") if e else "-"
        return text("trace.seal." + self.verdict, lang,
                    seals=len(self.seals), touches=len(self.touches),
                    first_seal=fmt(self.seals[0] if self.seals else None),
                    last_seal=fmt(self.seals[-1] if self.seals else None),
                    first_touch=fmt(self.touches[0] if self.touches else None),
                    early=len(self.touches_before_last_seal))


def seal_check(
    trace: Trace,
    *,
    seal: str,
    holdout: str,
    exclude_tools: Optional[Sequence[str]] = None,
    lang: str = None,
) -> SealReport:
    """Order the sealing calls against the calls that touch the holdout.

    ``seal`` and ``holdout`` are regexes over call input. A call matching
    ``seal`` is a seal and never also a touch: writing a preregistration that
    names the holdout file is the plan, not a peek. Calls by ``exclude_tools``
    are never touches, for the reason given at ``NON_READING_TOOLS``; left as
    ``None`` it is looked up from the trace's format.

    The verdict distinguishes an amended plan from a late one. Touching the
    holdout and *then* adding to the preregistration (``touched_between``) is
    not the same failure as having no plan when the holdout was opened
    (``touched_before_seal``), and a single boolean would merge them.
    """
    lang = resolve_lang(lang)
    if exclude_tools is None:
        exclude_tools = NON_READING_TOOLS_BY_FORMAT.get(trace.format, ())
    rs, rh = re.compile(seal), re.compile(holdout)
    calls = [e for e in trace.events if e.kind == "call"]
    seals = [e for e in calls if rs.search(e.text)]
    touches = [e for e in calls
               if e.tool not in exclude_tools and not rs.search(e.text) and rh.search(e.text)]
    blind = [text("trace.blind_seal", lang)]
    if trace.skipped_lines:
        blind.append(text("trace.blind_skipped", lang, n=trace.skipped_lines))
    if not seals:
        verdict, early = "unsealed", list(touches)
    elif not touches:
        verdict, early = "untouched", []
    else:
        first_seal, last_seal, first_touch = seals[0].ts, seals[-1].ts, touches[0].ts
        early = [t for t in touches if t.ts < last_seal]
        if first_touch < first_seal:
            verdict = "touched_before_seal"
        elif early:
            verdict = "touched_between"
        else:
            verdict = "sealed_first"
    ids = {t.call_id for t in touches}
    outs = {e.call_id: e for e in trace.events if e.kind == "output" and e.call_id in ids}
    return SealReport(verdict, seals, touches, early, blind, lang, outs)


# ---- how soon after a result did the next analysis start -------------------

@dataclass
class Gap:
    result: Event
    result_line: str
    next_call: Optional[Event]
    seconds: Optional[float]
    # Did a human turn fall between the result and the next analysis? None when
    # the format does not record human turns, or there is no next call.
    human_between: Optional[bool] = None


def gaps(trace: Trace, *, result: str, start: str) -> List[Gap]:
    """For each output line matching ``result``, time to the next call matching ``start``.

    Raw intervals, plus whether a human turn fell in between. That flag is
    the thing a seconds threshold would be guessing at, and the transcript
    records it directly. Across 807 result-to-new-script transitions in the
    author's own transcripts (``tools/gap_survey.py``; 43 sessions, one
    user), the gap with no human turn had a median of 46 s and the gap with
    one 872 s, and the best single threshold (about 200 s) still
    misclassified 2.7 % of them against the flag. A threshold would be a
    noisier proxy for a fact already in the log, so none is applied.
    """
    rr, rst = re.compile(result), re.compile(start)
    out: List[Gap] = []
    ev = trace.events
    for i, e in enumerate(ev):
        if e.kind != "output":
            continue
        hit = next((ln.strip() for ln in e.text.splitlines() if rr.search(ln)), None)
        if hit is None:
            continue
        nxt = next((x for x in ev[i + 1:]
                    if x.kind == "call" and x.ts >= e.ts and rst.search(x.text)), None)
        between: Optional[bool] = None
        if nxt is not None and trace.records_prompts:
            between = any(x.kind == "prompt" and e.ts < x.ts < nxt.ts for x in ev)
        out.append(Gap(e, hit, nxt,
                       (nxt.ts - e.ts).total_seconds() if nxt else None, between))
    return out


# ---- one call for every surface --------------------------------------------

def window(trace: Trace, since: Optional[datetime] = None,
           until: Optional[datetime] = None) -> Trace:
    """Keep events in ``[since, until]``. Naive datetimes are taken as UTC."""
    def utc(d):
        return d if d is None or d.tzinfo else d.replace(tzinfo=timezone.utc)
    since, until = utc(since), utc(until)
    ev = [e for e in trace.events
          if (since is None or e.ts >= since) and (until is None or e.ts <= until)]
    return Trace(ev, trace.skipped_lines, trace.format, trace.records_prompts)


def _event_dict(e: Optional[Event], n: int = 160) -> Optional[Dict[str, Any]]:
    return None if e is None else {"ts": e.ts.isoformat(), "tool": e.tool,
                                   "excerpt": e.excerpt(n)}


def audit(
    trace: Trace,
    *,
    units: Sequence[Unit] = (),
    seal: Optional[str] = None,
    holdout: Optional[str] = None,
    gap_result: Optional[str] = None,
    gap_start: Optional[str] = None,
    lang: str = None,
) -> Dict[str, Any]:
    """Run whichever checks were asked for and return one JSON-safe dict.

    The CLI's ``--json`` and the MCP tool both return exactly this, so the two
    surfaces cannot drift. Patterns come in pairs (``seal`` with ``holdout``,
    ``gap_result`` with ``gap_start``); half a pair is an error, not a skip.
    """
    if bool(seal) != bool(holdout):
        raise ValueError("seal and holdout go together")
    if bool(gap_result) != bool(gap_start):
        raise ValueError("gap_result and gap_start go together")
    if not (units or seal or gap_result):
        raise ValueError("nothing to do: give units, seal/holdout or gap_result/gap_start")
    lang = resolve_lang(lang)
    out: Dict[str, Any] = {"format": trace.format,
                           "events": sum(e.kind != "prompt" for e in trace.events),
                           "human_turns": (sum(e.kind == "prompt" for e in trace.events)
                                           if trace.records_prompts else None),
                           "skipped_lines": trace.skipped_lines}
    if units:
        tab = count_units(trace, units, lang=lang)
        out["units"] = [{"name": r.unit.name, "kind": r.unit.kind,
                         "pattern": r.unit.pattern, "matches": r.matches,
                         "trials": r.trials.to_dict() if r.trials else None,
                         "note": r.trials.note(lang) if r.trials else text("trace.no_match", lang)}
                        for r in tab.rows]
        out["spread"] = list(tab.spread) if tab.spread else None
        out["units_note"] = tab.note(lang)
    if seal:
        rep = seal_check(trace, seal=seal, holdout=holdout, lang=lang)
        out["seal"] = {
            "verdict": rep.verdict,
            "note": rep.note(lang),
            "seals": [_event_dict(e) for e in rep.seals],
            "touches": [dict(_event_dict(e), output=_event_dict(rep.output_of(e)),
                             before_last_seal=e in rep.touches_before_last_seal)
                        for e in rep.touches],
            "blind_to": rep.blind_to,
        }
    if gap_result:
        out["gaps"] = [{"result": _event_dict(g.result), "line": g.result_line,
                        "next_call": _event_dict(g.next_call), "seconds": g.seconds,
                        "human_between": g.human_between}
                       for g in gaps(trace, result=gap_result, start=gap_start)]
    return out
