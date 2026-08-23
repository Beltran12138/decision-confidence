#!/bin/sh
# Live demo: pull a venue snapshot, then count how many independent sources
# it actually contains. Two commands on purpose — the first one is the only
# thing that touches the network, and the second one is the product.
#
#   sh tools/demo_okx.sh
set -e
cd "$(dirname "$0")/.."
export PYTHONPATH=src
python tools/fetch_okx.py --out corpus/okx-live.jsonl
python tools/neff.py corpus/okx-live.jsonl
