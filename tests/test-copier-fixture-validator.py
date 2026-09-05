#!/usr/bin/env python3
"""Aggregate entrypoint for the Copier fixture validator test domains.

Every fixture the domains use is written in `copier_fixture_validator/support.py`.
The runtime candidate `tests/copier-update.sh` is never read as expected output and
is never executed, so the contract is proven against supplied bytes only.
"""

from __future__ import annotations

import unittest

from copier_fixture_validator.contract import (
    AcceptedFixtureTest,
    CommandLineTest,
    ModuleBoundaryTest,
    StructureRejectionTest,
    VersionCommitTest,
    VersionTagExistenceTest,
)
from copier_fixture_validator.inventory import (
    IndirectDispatchTest,
    InventoryDeclarationTest,
    InventoryRegionTest,
    OperandReadingTest,
    PositionalParameterTest,
)
from copier_fixture_validator.execution import (
    BoundedPollTest,
    ChildReapTest,
    DirectInvocationTest,
    GuardianTest,
    OperationEvidenceTest,
    OperationTargetTest,
    ReleasePathTest,
    SnapshotIndirectionTest,
    StateOrderTest,
    UnboundedPollTest,
    UnresolvedDispatchTest,
    UpdateChildTest,
    WrittenFormTest,
)
from copier_fixture_validator.grammar import (
    AliasCollectionTest,
    CommandShadowingTest,
    NameBindingTest,
    SourcedLibraryTest,
    WordGrammarTest,
)
from copier_fixture_validator.placement import (
    AlternatePathDestinationTest,
    AlternatePathTest,
    CopierWriteTest,
    ResolutionAuthorityTest,
    ShadowedAssignmentTest,
    SubshellDirectoryTest,
    TrailingSeparatorDestinationTest,
)


if __name__ == "__main__":
    unittest.main()
