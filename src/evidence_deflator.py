"""Evidence Deflator: the import name that matches the product name.

The package was first published as ``decision-confidence``. This module
re-exports the same public surface under the new name, so
``import evidence_deflator`` and ``import decision_confidence`` give the
same objects. Nothing here adds behaviour.
"""

from __future__ import annotations

from decision_confidence import *  # noqa: F401,F403
from decision_confidence import __all__ as _dc_all
from effective_window import effective_window, selection_penalty, months_for_power  # noqa: F401
from normalize import __version__  # noqa: F401

__all__ = list(_dc_all) + ["effective_window", "selection_penalty", "months_for_power", "__version__"]
