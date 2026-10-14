"""Package the plugin for the OpenAI plugin directory: dist/evidence-deflator-openai.zip.

Agent Plugins format (developers.openai.com/plugins/deploy/submission): the skill and the
hosted MCP server. The Claude Code backtest-counting hook is left out, because packages
with lifecycle hooks cannot be submitted to the directory.

Usage: python tools/build_openai_plugin.py
"""
import io
import json
import os
import zipfile

from PIL import Image, ImageDraw

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SITE = "https://evidencedeflator.com"
REPO = "https://github.com/Beltran12138/evidence-deflator"
MCP_URL = "https://api.evidencedeflator.com/mcp"
TOOL = "hyperliquid_wallet"


def logo(size, dark=False):
    """The site mark (favicon geometry, 24-unit grid) as a square PNG."""
    s = size / 24
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(4 * s), fill="#15171C" if not dark else "#FAF9F6")
    bar = "#FAF9F6" if not dark else "#15171C"
    d.rectangle([3 * s, 4 * s, 21 * s, 6 * s], fill="#E66A4B")
    for x, y, h in ((4.5, 13, 7), (9.5, 9.5, 10.5), (14.5, 15, 5)):
        d.rectangle([x * s, y * s, (x + 3) * s, (y + h) * s], fill=bar)
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


def manifest():
    case = lambda desc, prompt, expect: {"description": desc, "prompt": prompt,
                                         "tools_triggered": TOOL, "expected_behavior": expect}
    return {
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        "name": "evidence-deflator",
        "version": "0.3.0",
        "description": "Is that trading record skill, or could it be luck? Scores a Hyperliquid wallet's public record, allowing for having picked it off a leaderboard.",
        "author": {"name": "Evidence Deflator", "url": SITE},
        "homepage": SITE,
        "repository": REPO,
        "license": "MIT",
        "keywords": ["trading", "hyperliquid", "copy trading", "statistics", "leaderboard"],
        "extensions": {"com.openai": {
            "interface": {
                "displayName": "Evidence Deflator",
                "shortDescription": "Is that trader skilled or just lucky?",
                "longDescription": (
                    "Paste a Hyperliquid wallet address and get an evidence verdict on its trading record. "
                    "Evidence Deflator reads the wallet's public history, turns it into weekly returns (from PnL, so "
                    "deposits and withdrawals are not counted as returns), and tells you whether the record can be told "
                    "apart from luck, once you allow for having picked it from a leaderboard of about 47,000 accounts. "
                    "It also flags what the number cannot see, such as a record with no losing week or profit booked into "
                    "a near-empty account. Read-only, no account needed, open source. Not investment advice."),
                "developerName": "Evidence Deflator",
                "category": "Finance",
                "capabilities": ["Check a Hyperliquid wallet's track record", "Explain whether a leaderboard rank is evidence of skill"],
                "websiteURL": SITE,
                "supportURL": REPO + "/issues",
                "privacyPolicyURL": SITE + "/privacy/",
                "termsOfServiceURL": SITE + "/terms/",
                "defaultPrompt": [
                    "Is Hyperliquid wallet 0x4ec8fe22a531a96c8a846aaf5cbef73202649a80 skilled or lucky? I found it on the PnL leaderboard.",
                    "Should a leaderboard's #1 trader count as evidence of skill?",
                    "Check this Hyperliquid address before I copy it: 0x393d0b87ed38fc779fd9611144ae649ba6082109",
                ],
                "brandColor": "#15171C",
                "brandColorDark": "#FAF9F6",
                "composerIcon": "./assets/icon.png",
                "composerIconDark": "./assets/icon-dark.png",
                "logo": "./assets/logo.png",
                "logoDark": "./assets/logo-dark.png",
            },
            "review": {
                "test_cases": {
                    "positive": [
                        case("Losing wallet found on a leaderboard",
                             "Is 0x4ec8fe22a531a96c8a846aaf5cbef73202649a80 a good Hyperliquid trader to copy? I found it near the top of the all-time PnL leaderboard.",
                             "Calls the tool with picked_from about 47,000. Reports verdict 'loses' (t at or below -2), the bar of about 4.9, and the pnl_outside_record flag, and does not recommend copying."),
                        case("Record indistinguishable from luck",
                             "Check Hyperliquid wallet 0x393d0b87ed38fc779fd9611144ae649ba6082109. Someone sent it to me directly.",
                             "Calls the tool without picked_from (one wallet, picked blind). Reports verdict 'luck', t below 2, and the months of record still needed, without calling the trader unskilled."),
                        case("Record too short to judge",
                             "The top 30-day ROI wallet on Hyperliquid is 0x4d21e561c54302a4e6646fa9051aae68960d10fe. Is that skill?",
                             "Calls the tool. Reports 'too_short' (fewer than 8 measurable weeks) and says the record cannot tell yet, not that there is no skill."),
                        case("Asks how the wallet was found",
                             "Is 0x393d0b87ed38fc779fd9611144ae649ba6082109 skilled?",
                             "Asks, or states the assumption about, how the wallet was found, because a leaderboard pick raises the bar from 2 to about 4.9; then reports the verdict and flags."),
                        case("Invalid address",
                             "Check Hyperliquid wallet 0x1234.",
                             "The tool returns an error for a malformed address; the assistant asks for a full 0x address of 40 hex characters and does not invent a result."),
                    ],
                    "negative": [
                        {"description": "Investment advice", "prompt": "Should I buy HYPE today?"},
                        {"description": "Trading on the user's behalf", "prompt": "Copy all trades from wallet 0x393d0b87ed38fc779fd9611144ae649ba6082109 into my account."},
                        {"description": "Unsupported venue", "prompt": "How good is my Binance futures account's trading record?"},
                    ],
                },
                "commerce": False,
                "commerce_description": "This plugin does not sell products or process payments.",
            },
            "publication": {
                "release_notes": "Initial release: Hyperliquid wallet evidence check (hosted MCP tool) and a skill explaining how to read and report the verdict.",
            },
        }},
    }


def main():
    out = os.path.join(ROOT, "dist", "evidence-deflator-openai.zip")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(os.path.join(ROOT, "plugins", "evidence-deflator", "skills", "evidence-deflator", "SKILL.md"), encoding="utf-8") as f:
        skill = f.read()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("plugin.json", json.dumps(manifest(), indent=2, ensure_ascii=False) + "\n")
        z.writestr("mcp.json", json.dumps({
            "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
            "mcpServers": {"evidence-deflator": {"type": "streamable-http", "url": MCP_URL}},
        }, indent=2) + "\n")
        z.writestr("skills/evidence-deflator/SKILL.md", skill)
        z.writestr("assets/logo.png", logo(512))
        z.writestr("assets/logo-dark.png", logo(512, dark=True))
        z.writestr("assets/icon.png", logo(128))
        z.writestr("assets/icon-dark.png", logo(128, dark=True))
    print("wrote", os.path.relpath(out, ROOT), os.path.getsize(out))


if __name__ == "__main__":
    main()
