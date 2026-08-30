"""The MCP surface — what an agent can actually reach, and what it is told.

``mcp`` is an optional extra, so this skips when it is absent rather than
failing: the library is dependency-free and a missing dev extra is not a broken
library.

Two things are worth testing here and neither is arithmetic. First, that the
tool is *registered* — a function that exists but was never decorated is
invisible to every agent and no unit test of the function would notice. Second,
that the description still carries the instruction that makes the tool safe to
use: an MCP tool's docstring is its entire interface, and the one line that
turns "declaring no trials is a claim" into agent behaviour is
``ask the user — do not omit it``. Delete that sentence and the tool still
works, still returns correct numbers, and quietly lets a model assert on the
user's behalf that they got it right the first time.

    python -m unittest discover tests
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

try:
    import mcp_server
    HAVE_MCP = True
except SystemExit:          # the module's own guard when `mcp` is missing
    HAVE_MCP = False
except ImportError:
    HAVE_MCP = False

from effective_window import effective_window, remedies  # noqa: E402
from messages import text  # noqa: E402


@unittest.skipUnless(HAVE_MCP, "optional 'mcp' extra not installed")
class ToolRegistration(unittest.TestCase):

    def tools(self):
        return {t.name: t for t in asyncio.run(mcp_server.mcp.list_tools())}

    def test_all_three_tools_are_reachable(self):
        self.assertEqual(
            set(self.tools()),
            {"decision_confidence", "knowledge_window", "list_supported_vendors"},
        )

    def test_the_time_axis_is_its_own_tool(self):
        """Not folded into decision_confidence.

        A subject and a backtest are different objects; merging them would be
        the category error the library exists to catch, and an agent scoring a
        token must not be made to supply backtest dates.
        """
        schema = self.tools()["decision_confidence"].inputSchema["properties"]
        for leaked in ("cutoff", "start", "end", "trials"):
            self.assertNotIn(leaked, schema)

    def test_the_dates_are_required_and_the_rest_are_not(self):
        kw = self.tools()["knowledge_window"].inputSchema
        self.assertEqual(set(kw.get("required", [])), {"cutoff", "start", "end"})
        for optional in ("target_sharpe", "t_threshold", "trials", "effective_trials"):
            self.assertIn(optional, kw["properties"])


@unittest.skipUnless(HAVE_MCP, "optional 'mcp' extra not installed")
class ToolDescription(unittest.TestCase):
    """The docstring is the interface. These assert on its load-bearing lines."""

    def description(self):
        tools = {t.name: t for t in asyncio.run(mcp_server.mcp.list_tools())}
        return tools["knowledge_window"].description or ""

    def test_it_tells_the_agent_to_ask_rather_than_omit_the_trial_count(self):
        d = self.description()
        self.assertIn("ask the user", d)
        self.assertIn("not a neutral default", d)

    def test_it_forbids_estimating_the_independence_discount(self):
        """A freely chosen discount is an escape hatch, not a correction."""
        d = self.description()
        self.assertIn("measured", d)
        self.assertIn("Do not estimate it", d)

    def test_it_says_underpowered_is_not_a_negative_result(self):
        """The single most likely misreport, so it is spelled out for the model."""
        self.assertIn('not as "the strategy does not work"', self.description())

    def test_it_says_sufficient_is_not_evidence(self):
        self.assertIn("not* evidence the strategy works", self.description())


@unittest.skipUnless(HAVE_MCP, "optional 'mcp' extra not installed")
class ToolBehaviour(unittest.TestCase):

    def test_it_returns_the_same_numbers_as_the_library(self):
        got = mcp_server.knowledge_window("2024-10", "2020-01", "2025-06", trials=20)
        want = effective_window("2024-10", "2020-01", "2025-06", trials=20)
        self.assertEqual(got["verdict"], want.verdict)
        self.assertEqual(got["months_required"], want.months_required)
        self.assertEqual(got["selection"]["t_adjusted"], want.selection.t_adjusted)

    def test_it_ships_the_remedies_rather_than_leaving_the_agent_to_invent_them(self):
        got = mcp_server.knowledge_window("2024-10", "2020-01", "2025-06", trials=20)
        self.assertEqual(got["remedies"],
                         remedies(effective_window("2024-10", "2020-01", "2025-06",
                                                   trials=20)))
        self.assertTrue(got["summary"])

    def test_an_undeclared_trial_count_comes_back_visible(self):
        got = mcp_server.knowledge_window("2024-10", "2020-01", "2025-06")
        self.assertIsNone(got["selection"])
        self.assertIn(text("undeclared_selection", "en"), got["note"])
        self.assertIn(text("remedy.declare_trials", "en"), got["remedies"])

    def test_the_tool_answers_in_english_by_default(self):
        """An agent surface with Chinese output would strand every English host."""
        got = mcp_server.knowledge_window("2024-10", "2020-01", "2025-06", trials=20)
        blob = got["note"] + " " + " ".join(got["remedies"]) + " " + got["summary"]
        self.assertFalse([c for c in blob if "一" <= c <= "鿿"],
                         "Chinese characters in the default MCP response")

    def test_caller_errors_raise_rather_than_return_a_plausible_number(self):
        with self.assertRaises(ValueError):
            mcp_server.knowledge_window("2024-13", "2020-01", "2025-06")
        with self.assertRaises(ValueError):
            mcp_server.knowledge_window("2024-10", "2020-01", "2025-06",
                                        trials=5, effective_trials=9)


if __name__ == "__main__":
    unittest.main()
