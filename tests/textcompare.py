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
"""

from __future__ import annotations

import re

# Ranges whose glyphs are set without spaces between them.
CJK = r"　-〿一-鿿＀-￯"

_COLLAPSE = re.compile(r"\s+")
_CJK_JOIN = re.compile(r"(?<=[" + CJK + r"]) (?=[" + CJK + r"])")


def flat(s: str) -> str:
    """Undo line wrapping so a wrapped rendering can be matched against its source.

    English keeps its spaces; a space between two CJK characters is removed,
    because it was a line break and never a space.
    """
    return _CJK_JOIN.sub("", _COLLAPSE.sub(" ", s).strip())
