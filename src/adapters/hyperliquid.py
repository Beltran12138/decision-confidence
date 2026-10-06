"""Hyperliquid ``portfolio`` payload → one daily return series per wallet.

Input is what ``POST https://api.hyperliquid.xyz/info`` returns for
``{"type": "portfolio", "user": "0x..."}`` — caller-fetched, as with every
adapter here; nothing in this package touches the network.

The payload is a list of ``[window, {"accountValueHistory": [[ms, "v"], ...],
"pnlHistory": [[ms, "v"], ...]}]`` pairs. Returns are built from **PnL, not
account value**: account value jumps on every deposit and withdrawal, and a
series that reads a deposit as a gain is the commonest way a leaderboard ROI
comes out at 37,000%. PnL is cumulative, so the day's PnL is the difference of
the last reading on that day and the last reading on the previous day, divided
by the account value at the previous day's close.

Days where the previous close was not positive are skipped rather than given a
return: dividing by a zero balance produces a number, not a measurement.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Optional

__all__ = ["daily_returns", "WINDOWS"]

WINDOWS = ("day", "week", "month", "allTime",
           "perpDay", "perpWeek", "perpMonth", "perpAllTime")


def _closes(points: List[List[Any]]) -> Dict[str, float]:
    """Last reading per UTC day, keyed ``YYYY-MM-DD``."""
    out: Dict[str, float] = {}
    for ms, value in sorted(points, key=lambda p: p[0]):
        day = _dt.datetime.fromtimestamp(ms / 1000, _dt.timezone.utc).date().isoformat()
        out[day] = float(value)
    return out


def daily_returns(payload: Any, window: str = "perpMonth") -> Dict[str, float]:
    """``{YYYY-MM-DD: return}`` for one wallet over one window.

    ``perpMonth`` by default: about a month at several readings a day, perps
    only, so spot balances parked on the account do not dilute the return.
    """
    if window not in WINDOWS:
        raise ValueError(f"unknown window {window!r}; expected one of {WINDOWS}")
    windows = dict(payload) if isinstance(payload, list) else payload
    w: Optional[Dict[str, Any]] = windows.get(window)
    if not w:
        return {}
    pnl = _closes(w.get("pnlHistory") or [])
    value = _closes(w.get("accountValueHistory") or [])
    days = sorted(set(pnl) & set(value))
    out: Dict[str, float] = {}
    for prev, day in zip(days, days[1:]):
        base = value[prev]
        if base > 0:
            out[day] = (pnl[day] - pnl[prev]) / base
    return out
