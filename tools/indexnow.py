"""Tell IndexNow search engines (Bing and others) which pages changed.

Usage:
    python tools/indexnow.py /wallet/ /           # these paths
    python tools/indexnow.py --all                # every URL in docs/sitemap.xml

The key is public by design: the engines fetch https://evidencedeflator.com/<key>.txt
to confirm the submitter controls the host. A 200 or 202 means accepted, not crawled.
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_site import DOCS, INDEXNOW_KEY, SITE  # noqa: E402

ENDPOINT = "https://api.indexnow.org/indexnow"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    if a.all:
        with open(os.path.join(DOCS, "sitemap.xml"), encoding="utf-8") as f:
            urls = re.findall(r"<loc>([^<]+)</loc>", f.read())
    else:
        urls = [SITE + p for p in a.paths]
    if not urls:
        sys.exit("no URLs")
    body = json.dumps({"host": SITE.split("//", 1)[1], "key": INDEXNOW_KEY,
                       "keyLocation": f"{SITE}/{INDEXNOW_KEY}.txt", "urlList": urls}).encode()
    req = urllib.request.Request(ENDPOINT, data=body, headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(r.status, len(urls), "URLs")
    except urllib.error.HTTPError as e:
        sys.exit(f"{e.code} {e.read()[:300]!r} for {len(urls)} URLs")


if __name__ == "__main__":
    main()
