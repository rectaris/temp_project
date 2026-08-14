#!/usr/bin/env python3
"""Aggregate entrypoint for generated Codex Hook test domains."""

from __future__ import annotations

import unittest

from hooks.context import ContextCompressionBoundaryTest
from hooks.gates import PreToolHardeningGateTest, StopReviewGateTest
from hooks.logging import (
    AgentLogEventTest,
    CodexTranscriptImportTest,
    RootLoggingCliDelegationTest,
)
from hooks.semantic import SemanticGuardAdvisoryTest


if __name__ == "__main__":
    unittest.main()
