#!/usr/bin/env python3
"""Aggregate entrypoint for generated Codex Hook test domains."""

from __future__ import annotations

import unittest

from hook_tests_context import ContextCompressionBoundaryTest
from hook_tests_gates import PreToolHardeningGateTest, StopReviewGateTest
from hook_tests_logging import (
    AgentLogEventTest,
    CodexTranscriptImportTest,
    RootLoggingCliDelegationTest,
)
from hook_tests_semantic import SemanticGuardAdvisoryTest


if __name__ == "__main__":
    unittest.main()
