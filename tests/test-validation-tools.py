#!/usr/bin/env python3
"""Aggregate entrypoint for validation-tool test domains."""

from __future__ import annotations

import unittest

from validation_tools.changes import ValidateChangesTest
from validation_tools.external import RootExternalServicePolicyTest
from validation_tools.feature_scoring import CommittedFeatureScoringCasesTest, FeatureScoringTest
from validation_tools.generated import (
    GeneratedCiTest,
    LegacyExternalServiceMigrationTest,
    SecurityStaticCheckTest,
)
from validation_tools.plan import PlanOverviewTest, PlanValidationCommandsTest
from validation_tools.python_lint import PythonLintTest
from validation_tools.question_set import CommittedQuestionCasesTest, QuestionSetBuilderTest
from validation_tools.plan_authoring import PlanAuthoringInRepositoryTest, PlanAuthoringTest
from validation_tools.release_skill import (
    ReleaseRunbookExampleTest,
    ReleaseSkillDetectionTest,
    ReleaseSkillStructureTest,
)
from validation_tools.selector_agreement import SelectorAgreementTest
from validation_tools.smoke_source import SmokeCopySelectionTest, SmokeSourceTest
from validation_tools.worktrees import (
    ManagedPlanWorktreesTest,
    ParentDirectMemberHandoffTest,
    PlanIdentifierReservationTest,
    TaskPublicationTest,
    TaskWorktreeGuardTest,
)


if __name__ == "__main__":
    unittest.main()
