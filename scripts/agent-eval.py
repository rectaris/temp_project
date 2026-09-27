#!/usr/bin/env python3
"""Freeze repository-local evaluation experiments before any run.

`resolve` reads one experiment definition under `evals/experiments/`, binds the
digest of every case, run configuration, instruction asset, capability
registry and environment it uses, and writes the resolved experiment record,
the schema-2 comparison protocol and the run matrix under
`.agent-artifacts/evaluations/<experiment-id>/`. It launches no model and opens
no network socket. This command is root-only and never ships in the template.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

# Resolve writes only inside its experiment directory, so importing this
# command's own modules must not leave bytecode caches in the checkout.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from project_workflow import agent_eval_definitions as definitions  # noqa: E402


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    resolve = commands.add_parser(
        "resolve",
        help="freeze one experiment's digests, comparison protocol and run matrix",
    )
    resolve.add_argument("experiment", help="evals/experiments/<experiment-id>.json")
    resolve.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root that holds evals/ (default: this repository)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        record = definitions.resolve_experiment(args.root, args.experiment)
    except definitions.DefinitionError as exc:
        print(f"agent-eval resolve failed: {exc}", file=sys.stderr)
        return 1
    print(f"experiment: {record['experiment_id']}")
    print(f"runs: {record['run_count']} ({record['ordering']} ordering)")
    print(f"protocol: {record['protocol']['digest']}")
    print(f"matrix: {record['matrix']['digest']}")
    print(f"output: {record['output_directory']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
