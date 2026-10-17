"""Hyperliquid wallet check: is this record skill, or could it be luck?

The scoring that powers evidencedeflator.com/wallet/, in the standard library.
docs/assets/hl.js is the browser port; tools/check_hl_parity.py runs both on
the same portfolios and diffs them.

Returns come from the PnL history, not the account-value history: account
value moves with deposits and withdrawals, PnL does not. Each interval's return
is the change in cumulative PnL divided by account value at its start. History
is put on a weekly grid anchored at the last sample; a week with no new sample
is merged into the next interval, not scored as zero. The t statistic uses the
n - 1 variance for unequal intervals and Student's t on Satterthwaite degrees
of freedom, put back on the normal scale, so the bars are 2 for one record
picked blind and the Bonferroni best-of-N bar for one found on a leaderboard.

This is the one module in the package that touches the network, and only in
``fetch_portfolio`` (Hyperliquid's public info API, no key).
"""
from __future__ import annotations

import json
import math
import statistics
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

N = statistics.NormalDist()

INFO_URL = "https://api.hyperliquid.xyz/info"
WEEK_MS = 7 * 24 * 3600 * 1000
MIN_WEEKS = 8
MIN_AV = 1000.0  # weeks starting below this account value are skipped
ALPHA = 1 - N.cdf(2)


def bar(n):
    return N.inv_cdf(1 - ALPHA / n)


def months_to_clear(b, sharpe):
    return (b / sharpe) ** 2 * 12 if sharpe and sharpe > 0 else None


def _betacf(a, b, x):
    """Continued fraction for the incomplete beta function (Lentz)."""
    tiny, qab, qap, qam = 1e-300, a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        for aa in (m * (b - m) * x / ((qam + m2) * (a + m2)),
                   -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))):
            d = 1 + aa * d
            d = 1 / (d if abs(d) > tiny else tiny)
            c = 1 + aa / c
            c = c if abs(c) > tiny else tiny
            h *= d * c
        if abs(d * c - 1) < 1e-15:
            break
    return h


def _betai(a, b, x):
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return bt * _betacf(a, b, x) / a
    return 1 - bt * _betacf(b, a, 1 - x) / b


def t_to_z(t, dof):
    """The normal score with the same tail probability as Student's t with `dof` degrees of freedom.

    A t computed from a few intervals has fat tails: with 8 intervals and no skill,
    t >= 2 turns up about twice as often as the normal bar of 2 assumes. Putting t on
    the normal scale keeps the bars (2 and best-of-N) the same for every record length.
    """
    if t == 0:
        return 0.0
    p = 0.5 * _betai(dof / 2, 0.5, dof / (dof + t * t))  # P(T > |t|)
    return math.copysign(-N.inv_cdf(max(p, 1e-300)), t)


def weekly_returns(pf, since=None):
    """Returns between weekly grid nodes, merged where the source has no new sample.

    Each node takes the last source sample at or before it. Two nodes that land
    on the same sample carry no information about the week between them, so
    that week is merged into the next interval instead of being scored as a
    zero return (which would inflate the week count and shrink the spread).
    Returns (list of (return, interval_in_weeks), start ms, end ms, dollar PnL
    inside the counted intervals).

    With `since` (ms), the grid starts at `since` and steps forward, so only the
    record after that moment is scored (the forward record of a frozen cohort).
    The first node is the last sample at or before `since`.
    """
    av = [(t, float(v)) for t, v in pf["allTime"]["accountValueHistory"]]
    pnl = dict((t, float(v)) for t, v in pf["allTime"]["pnlHistory"])
    if len(av) < 2:
        return [], None, None, 0.0
    start, end = av[0][0], av[-1][0]
    if since is None:
        grid = list(range(end, start - 1, -WEEK_MS))[::-1]
    else:
        grid = list(range(since, end + 1, WEEK_MS))

    nodes, i = [], 0
    for g in grid:
        while i + 1 < len(av) and av[i + 1][0] <= g:
            i += 1
        if av[i][0] <= g and (not nodes or nodes[-1] != i):
            nodes.append(i)

    out, counted = [], 0.0
    for a, b in zip(nodes, nodes[1:]):
        ta, va = av[a]
        tb = av[b][0]
        if va < MIN_AV or ta not in pnl or tb not in pnl:
            continue
        out.append(((pnl[tb] - pnl[ta]) / va, (tb - ta) / WEEK_MS))
        counted += pnl[tb] - pnl[ta]
    return out, start, end, counted


def flags(pf, rets, counted):
    """What t cannot see, reported next to it. Same rules as HL.flags in docs/assets/hl.js."""
    out = []
    if len(rets) >= MIN_WEEKS:
        if not any(r < 0 for r, _ in rets):
            out.append("no_losing_week")
        gains = [r for r, _ in rets if r > 0]
        if sum(r for r, _ in rets) > 0 and gains and max(gains) / sum(gains) > 0.5:
            out.append("one_week_majority")
    pnl = pf["allTime"]["pnlHistory"]
    total = float(pnl[-1][1]) - float(pnl[0][1]) if pnl else 0.0
    if total > 0 and (total - counted) / total > 0.5:
        out.append("pnl_outside_record")
    return out


def score(rets):
    """Evidence in returns over unequal intervals.

    mu is the drift per week (sum r / sum dt); the variance per week divides the
    squared residuals by W - sum(dt^2)/W rather than W, which is the n - 1 correction
    for unequal intervals (it is n - 1 when all intervals are one week). Then
    t_student = Sharpe * sqrt(years), and `t` is that value put on the normal scale
    (t_to_z), so short records are not over-read. Degrees of freedom are
    Satterthwaite's for these residuals, (tr A)^2 / tr(A^2), which in power sums
    S_k = sum dt^k is (W - S2/W)^2 / (S2 - 2 S3/W + S2^2/W^2): n - 1 for equal
    intervals, fewer when a few long intervals carry most of the record.
    """
    n = len(rets)
    if n < MIN_WEEKS:
        return {"weeks": n, "sharpe": None, "t": None}
    tot_r = sum(r for r, _ in rets)
    tot_w = sum(w for _, w in rets)
    mu = tot_r / tot_w
    ss = sum((r - mu * w) ** 2 for r, w in rets)
    s2 = sum(w * w for _, w in rets)
    s3 = sum(w ** 3 for _, w in rets)
    eff = tot_w - s2 / tot_w
    if ss == 0 or tot_w <= 0 or eff <= 0:
        return {"weeks": n, "sharpe": None, "t": None}
    sigma_w = math.sqrt(ss / eff)  # per sqrt(week)
    sharpe = mu / sigma_w * math.sqrt(52)
    t_student = tot_r / (sigma_w * math.sqrt(tot_w))
    dof = eff ** 2 / (s2 - 2 * s3 / tot_w + s2 * s2 / tot_w ** 2)
    return {"weeks": round(tot_w, 1), "intervals": n, "sharpe": round(sharpe, 3),
            "t_student": round(t_student, 3), "dof": round(dof, 1), "t": round(t_to_z(t_student, dof), 3)}


SIEGMUND = 0.5826  # -zeta(1/2) / sqrt(2 pi)


def drawdown(rets):
    """Where the record stands against its own peak, and how ordinary that is if its edge is real.

    The path adds up the scored weekly returns: the same arithmetic returns t is built
    from. Most accounts add and withdraw money, so compounding would describe a portfolio
    nobody held (a volatile account with a positive mean compounds toward zero). `now` and
    `deepest` are sums of weekly returns below the running peak, so they can exceed 1.
    For a path drifting at m per week with variance s2 per week, the distance below the
    running peak settles to an exponential
    with rate 2m/s2 (reflected Brownian motion), so the share of time spent at least d
    below the peak is exp(-2 m d / s2). Measured weekly, the walk overshoots the peak
    between samples; Siegmund's correction (d + 0.5826 s) keeps the share within about 2%
    of simulation up to Sharpe 3, where the plain formula is 1.6x too high
    (tests/test_drawdown.py). m and s2 are measured on the same record, with the same
    estimator as score(). Same as HL.drawdown in docs/assets/hl.js.

    The edge is measured on the record itself, often one picked for being good, so it is
    more likely overstated than understated; a smaller true edge makes drawdowns more
    common, so share_if_real leans toward calling a drawdown unusual.
    """
    if len(rets) < MIN_WEEKS:
        return None
    w = peak = max_dd = since = tot_r = tot_w = 0.0
    for r, dt in rets:
        w += r
        tot_r += r
        tot_w += dt
        if w >= peak:
            peak, since = w, 0.0
        else:
            since += dt
        max_dd = max(max_dd, peak - w)
    mu = tot_r / tot_w
    ss = sum((r - mu * dt) ** 2 for r, dt in rets)
    s2 = sum(dt * dt for _, dt in rets)
    eff = tot_w - s2 / tot_w
    v = ss / eff if eff > 0 else 0.0
    m, d = mu, peak - w
    return {"now": round(d, 4), "weeks_below": round(since, 1), "deepest": round(max_dd, 4),
            "share_if_real": (None if not (m > 0 and v > 0) else 1.0 if d == 0 else
                              round(math.exp(-2 * m * (d + SIEGMUND * math.sqrt(v)) / v), 4))}


def verdict(sc: Dict[str, Any], picked_from: Optional[int] = None) -> Dict[str, Any]:
    """Same keys as HL.verdict in docs/assets/hl.js."""
    b = bar(picked_from) if picked_from and picked_from > 1 else 2.0
    t = sc.get("t")
    if t is None:
        key = "too_short"
    elif t >= b and picked_from and picked_from > 1:
        key = "clears_board"
    elif t >= 2:
        key = "clears_single"
    elif t <= -2:
        key = "loses"
    else:
        key = "luck"
    return {"key": key, "bar": round(b, 2)}


def fetch_portfolio(address: str, timeout: float = 30.0) -> Dict[str, Any]:
    """Portfolio history from Hyperliquid's public info API (no key)."""
    body = json.dumps({"type": "portfolio", "user": address}).encode()
    req = urllib.request.Request(INFO_URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    if not isinstance(data, list) or not data:
        raise ValueError("no portfolio history for " + address)
    return dict(data)


def check(address: str, picked_from: Optional[int] = None, pf: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Score one wallet. Pass ``pf`` to score a portfolio you already have."""
    pf = pf if pf is not None else fetch_portfolio(address)
    rets, start, end, counted = weekly_returns(pf)
    sc = score(rets)
    v = verdict(sc, picked_from)
    months = (months_to_clear(v["bar"], sc["sharpe"]) if sc.get("sharpe") else None)
    have = (sc["weeks"] or 0) / 4.345 if sc.get("t") is not None else 0
    day = lambda ms: datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d") if ms is not None else None
    return {
        "address": address,
        **sc,
        "verdict": v["key"],
        "bar": v["bar"],
        "picked_from": picked_from,
        "months_more_to_clear": (None if months is None else round(max(months - have, 0), 1)),
        "flags": flags(pf, rets, counted),
        "drawdown": drawdown(rets),
        "history_from": day(start),
        "history_to": day(end),
    }


def main(argv: Optional[List[str]] = None) -> None:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m hl_wallet",
                                 description="Is this Hyperliquid wallet's record skill, or could it be luck?")
    ap.add_argument("address")
    ap.add_argument("--picked-from", type=int, default=None,
                    help="how many wallets it was chosen from (the leaderboard size if found on one)")
    a = ap.parse_args(argv)
    print(json.dumps(check(a.address.lower(), picked_from=a.picked_from), indent=2))


if __name__ == "__main__":
    main()
