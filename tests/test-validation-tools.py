#!/usr/bin/env python3
"""Aggregate entrypoint for validation-tool test domains."""

from __future__ import annotations

import unittest

from validation_tools.changes import ValidateChangesTest
from validation_tools.external import RootExternalServicePolicyTest
from validation_tools.generated import (
    GeneratedCiTest,
    LegacyExternalServiceMigrationTest,
    SecurityStaticCheckTest,
)
from validation_tools.plan import PlanValidationCommandsTest


if __name__ == "__main__":
    unittest.main()
