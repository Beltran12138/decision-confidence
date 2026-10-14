"""PostToolUse hook: every backtest the agent runs raises the bar for the one it reports.

Reads the hook event on stdin. When a Bash command matches the backtest pattern, it
appends the run to a per-session log under CLAUDE_PLUGIN_DATA and tells the agent, in
context, how many runs this session has made and what the best of them now has to clear.

Standard library only. Silent (no output) for commands that are not backtests.
"""
import json
import math
import os
import re
import sys
import time
from statistics import NormalDist

DEFAULT_PATTERN = (r"backtest|backtrader|vectorbt|zipline|freqtrade\s+(backtesting|hyperopt)"
                   r"|lean\s+backtest|qlib|nautilus|bt\.run|walk[-_ ]?forward|optuna|hyperopt")
ALPHA = 1 - NormalDist().cdf(2)  # one result picked blind needs t >= 2


def bar(n):
    """t the best of n independent tries must clear (Bonferroni on 1 - Phi(2))."""
    return NormalDist().inv_cdf(1 - ALPHA / max(n, 1))


def months_needed(t_bar, sharpe):
    return (t_bar / sharpe) ** 2 * 12


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return
    if event.get("tool_name") != "Bash":
        return
    cmd = (event.get("tool_input") or {}).get("command") or ""
    pattern = os.environ.get("CLAUDE_PLUGIN_OPTION_BACKTEST_PATTERN") or DEFAULT_PATTERN
    try:
        if not re.search(pattern, cmd, re.I):
            return
    except re.error:
        if not re.search(DEFAULT_PATTERN, cmd, re.I):
            return

    data = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.join(os.path.expanduser("~"), ".evidence-deflator")
    sid = re.sub(r"[^A-Za-z0-9_-]", "-", str(event.get("session_id") or "unknown"))
    path = os.path.join(data, "sessions", sid + ".json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, encoding="utf-8") as f:
            log = json.load(f)
    except (OSError, ValueError):
        log = {"runs": []}
    log["runs"].append({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "command": cmd[:500]})
    with open(path, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=1)

    n = len(log["runs"])
    b = bar(n)
    msg = (f"Evidence Deflator: backtest run #{n} in this session (log: {path}). "
           f"If you report the best of these {n} runs, it was picked from {n}, so it needs t >= {b:.2f} "
           f"(t = annualised Sharpe x sqrt(years)), not 2. At a true Sharpe of 1 that takes "
           f"{months_needed(b, 1):.0f} months of out-of-sample data; at Sharpe 2, {months_needed(b, 2):.0f}. "
           f"When you report a result, state that it is the best of {n} runs and compare it with {b:.2f}. "
           "Reruns of an edited strategy count as new tries; reruns of an unchanged one with a different "
           "random seed count too, because the seed was chosen by looking.")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}))


if __name__ == "__main__":
    main()
