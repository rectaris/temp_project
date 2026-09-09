#!/usr/bin/env python3
"""Aggregate entrypoint for generated Codex Hook test domains."""

from __future__ import annotations

import unittest

from hooks.context import ContextCompressionBoundaryTest
from hooks.gates import (
    PreToolHardeningGateTest,
    StopReviewGateTest,
    TaskWorktreeGateTest,
)
from hooks.logging import (
    AgentLogEventTest,
    CodexTranscriptImportTest,
    EvidenceDigestValidationTest,
    RootLoggingCliDelegationTest,
)
from hooks.resource_summary import ResourceSummaryTest
from hooks.semantic import SemanticGuardAdvisoryTest


if __name__ == "__main__":
    unittest.main()
