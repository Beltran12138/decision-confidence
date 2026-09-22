"""Comparing wrapped console output against the unwrapped source string.

Not a test module (the discovery pattern is ``test*.py``), a helper for the two
that need it.

It exists because the same bug was written twice. The library returns one
sentence; a CLI wraps it and indents the continuations, so any assertion has to
undo the wrapping first. Collapsing whitespace is the obvious move and it is
half right: a line break between two Chinese characters carries no space in the
source, so turning it into one leaves ``少试， 不能`` where the original says
``少试，不能``. That was fixed in the window CLI's tests, then reintroduced in
the perturbation CLI's — by copying the idea instead of the function.

Third instance, 2026-09-22: requiring CJK on *both* sides is also half right.
A wrap can land between a CJK character and a Latin one — ``（Zhang & Stadie，``
then a break, then ``arXiv:2608.02985）`` — and that space is just as phantom.
The rule is now "a space with CJK on either side", because CJK text does not
separate its glyphs with spaces at all, so any space adjacent to one that came
out of a wrapper was not in the source.

Where the source genuinely does put a space around a Latin word (``用 curl 直连``)
both sides of the comparison lose it, so matching is unaffected; the cost is
that this helper can no longer detect a *missing* space next to CJK. That was
already true of the two-sided rule for CJK-CJK pairs, and it is the trade this
module exists to make: it compares wrapped output against its source, and the
wrapper's spaces are noise in exactly this position.
"""

from __future__ import annotations

import re

# Ranges whose glyphs are set without spaces between them.
CJK = r"　-〿一-鿿＀-￯"

_COLLAPSE = re.compile(r"\s+")
# CJK on *either* side, not both — see the third instance in the module docstring.
_CJK_JOIN = re.compile(r"(?<=[" + CJK + r"]) | (?=[" + CJK + r"])")


def flat(s: str) -> str:
    """Undo line wrapping so a wrapped rendering can be matched against its source.

    English keeps its spaces; a space adjacent to a CJK character is removed,
    because it was a line break and never a space.
    """
    return _CJK_JOIN.sub("", _COLLAPSE.sub(" ", s).strip())
