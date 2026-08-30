"""The translation layer itself.

A translated string is a second copy of a sentence, and copies drift. These
tests check the properties that make drift visible before a reader finds it:
every key exists in every language, and the ``str.format`` fields survive
translation.

That last one is the reason this file exists. A Chinese sentence that quietly
drops ``{months_required}`` still renders — ``str.format`` does not object to an
unused keyword — it just renders without the number that made it worth printing.
Nothing else in the suite would notice.

    python -m unittest discover tests
"""

from __future__ import annotations

import os
import re
import string
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from messages import DEFAULT_LANG, LANGS, MESSAGES, resolve_lang, text  # noqa: E402


def fields(template):
    return {f for _, f, _, _ in string.Formatter().parse(template) if f}


class Completeness(unittest.TestCase):

    def test_every_key_exists_in_every_language(self):
        for key, entry in MESSAGES.items():
            self.assertEqual(set(entry), set(LANGS), key)

    def test_no_translation_is_empty(self):
        for key, entry in MESSAGES.items():
            for lang, value in entry.items():
                self.assertTrue(value.strip(), "%s/%s" % (key, lang))

    def test_english_carries_no_chinese_characters(self):
        """The default output is what an English reader sees on the first run."""
        for key, entry in MESSAGES.items():
            han = [c for c in entry["en"] if "\u4e00" <= c <= "\u9fff"]
            self.assertFalse(han, "%s: %r" % (key, han))

    def test_chinese_is_actually_translated(self):
        """A copy-pasted English string in the zh slot would pass every other
        check here, so it gets its own."""
        for key, entry in MESSAGES.items():
            if key == "cli.arrow":
                continue          # a glyph, not a sentence
            self.assertNotEqual(entry["en"], entry["zh"], key)


class Templates(unittest.TestCase):

    def test_format_fields_survive_translation(self):
        """The failure this file was written for: a dropped {field} still
        renders, just without the number."""
        for key, entry in MESSAGES.items():
            per_lang = {lang: fields(entry[lang]) for lang in LANGS}
            first = per_lang[LANGS[0]]
            for lang in LANGS[1:]:
                self.assertEqual(
                    first, per_lang[lang],
                    "%s: %s has %s, %s has %s"
                    % (key, LANGS[0], sorted(first), lang, sorted(per_lang[lang])),
                )

    def test_every_template_renders_with_its_own_fields(self):
        """Catches a malformed spec (``{n_eff:g}`` against a string, say)."""
        sample = {"trials": 20, "n_eff": 4, "t_base": 2.0, "t_adjusted": 3.05,
                  "months_base": 48, "months_adjusted": 112, "ratio": 2.33,
                  "shrunk": "", "total_months": 66, "open_book_months": 58,
                  "open_book_share": 0.879, "effective_months": 8,
                  "target_sharpe": 1.0, "months_required": 48, "bar": "t>=2",
                  "verdict": "underpowered", "t_threshold": 2.0, "start": "2020-01",
                  "open_end": "2024-10", "need": 40, "ready": "2028-10",
                  "latest": "2021-06", "sharpe": 2.45, "cutoff": "2024-10",
                  "end": "2025-06", "t_eff": 3.05, "alpha_base": 0.02275,
                  "alpha_adjusted": 0.00114, "sr": 1.0, "have": 8, "err": "boom",
                  "m2": 28, "m1": 112, "m05": 448}
        for key, entry in MESSAGES.items():
            need = fields(entry["en"])
            args = {k: sample[k] for k in need if k in sample}
            self.assertEqual(need - set(args), set(),
                             "%s uses unknown field(s)" % key)
            for lang in LANGS:
                text(key, lang, **args)      # raises on a bad spec


class LanguageResolution(unittest.TestCase):

    def test_none_is_the_default(self):
        self.assertEqual(resolve_lang(None), DEFAULT_LANG)

    def test_region_tags_and_case_are_tolerated(self):
        for tag in ("zh-CN", "zh_TW", "ZH", "zh-Hans"):
            self.assertEqual(resolve_lang(tag), "zh", tag)
        for tag in ("en-GB", "EN", "en_US"):
            self.assertEqual(resolve_lang(tag), "en", tag)

    def test_an_unknown_language_falls_back_rather_than_raising(self):
        """Refusing to compute the window over a bad language tag would be a
        worse failure than answering in English."""
        for tag in ("tlh", "", "xx-YY", "123"):
            self.assertEqual(resolve_lang(tag), DEFAULT_LANG, repr(tag))

    def test_an_unknown_key_raises_rather_than_echoing_itself(self):
        """Returning the key as a placeholder would ship the bug to the reader."""
        with self.assertRaises(KeyError):
            text("no.such.key", "en")


if __name__ == "__main__":
    unittest.main()
