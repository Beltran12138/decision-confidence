#!/usr/bin/env python3
"""Regenerate the page's copy of the message table from src/messages.py.

    python tools/gen_js_messages.py            # rewrite the table in place
    python tools/gen_js_messages.py --check    # exit 1 if it is stale

``docs/index.html`` has to run with no build step, so it carries its own copy of
every user-facing string. Transcribing ninety of them by hand is a typo with a
delivery date, so the copy is generated — by this.

Generating it does not keep it in sync, because nothing re-runs a generator when
the source changes. That is what ``tools/check_js_parity.py`` is for: it diffs
the two tables entry by entry, in both languages, before it looks at any
rendered output. This script is the fix; that one is the alarm.

The page holds **every** entry, including ones only the CLI or the library use.
Filtering to "what the page currently renders" would mean the two tables are
allowed to differ, and then the diff has to encode which differences are fine —
which is how a checker stops being a checker.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from messages import DEFAULT_LANG, LANGS, MESSAGES  # noqa: E402

PAGE = os.path.join(ROOT, "docs", "index.html")
HEADER = "const I18N = {"


def render_table() -> str:
    rows = ["  %s: {%s}," % (
        json.dumps(key),
        ", ".join("%s: %s" % (lang, json.dumps(MESSAGES[key][lang], ensure_ascii=False))
                  for lang in LANGS),
    ) for key in MESSAGES]
    return HEADER + "\n" + "\n".join(rows) + "\n};\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="do not write; exit 1 if the page's table is stale")
    args = ap.parse_args()

    with open(PAGE, encoding="utf-8") as fh:
        page = fh.read()

    found = re.search(r"const I18N = \{.*?\n\};\n", page, re.S)
    if not found:
        print("no I18N table found in docs/index.html", file=sys.stderr)
        return 2

    fresh = render_table()
    if found.group(0) == fresh:
        print("up to date — %d entries x %d languages" % (len(MESSAGES), len(LANGS)))
        return 0

    if args.check:
        print("STALE: docs/index.html does not match src/messages.py.\n"
              "Run: python tools/gen_js_messages.py", file=sys.stderr)
        return 1

    with open(PAGE, "w", encoding="utf-8") as fh:
        fh.write(page[:found.start()] + fresh + page[found.end():])
    print("regenerated — %d entries x %d languages, default %s"
          % (len(MESSAGES), len(LANGS), DEFAULT_LANG))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
