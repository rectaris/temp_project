#!/usr/bin/env python3
"""Render one root plan and its index update from a checked authoring input.

`check` reports the complete requirement-to-scope-to-condition-to-witness
correspondence and the exact input digest without writing to the repository.
`write` reproduces that digest from the same bytes and renders this
repository's plan schema under the shared plan lifecycle lock.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from project_workflow import plan_authoring  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    return plan_authoring.main(argv, default_profile=plan_authoring.PROFILE_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
