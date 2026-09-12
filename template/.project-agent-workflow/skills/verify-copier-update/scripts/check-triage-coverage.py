#!/usr/bin/env python3
"""Fail when the triage table does not classify every reason code the verifier emits.

The verifier and the triage table are separate files, so a new stop path could
otherwise reach a downstream agent with no recorded owner and no next action. This
command reads the verifier's own syntax tree, propagates the literal values that
shape a reason code through the call graph, and requires the resulting codes and
the table to cover each other exactly.

Exit status:
  0  every emitted reason code resolves and every table entry is reachable
  1  the table and the verifier disagree
  2  the code space could not be enumerated
"""

from __future__ import annotations

import argparse
import ast
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

DYNAMIC = "\x00dynamic"
PROPAGATION_ROUNDS = 64


class CoverageError(Exception):
    """One bounded failure that leaves the code space unproven."""


def parse_module(path: Path) -> ast.Module:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except OSError as exc:
        raise CoverageError(f"verifier is unavailable: {exc}") from exc
    except SyntaxError as exc:
        raise CoverageError(f"verifier is not parsable: {exc}") from exc


def function_parameters(tree: ast.Module) -> dict[str, list[str]]:
    """Map each uniquely named function to its parameter names.

    A name defined more than once cannot be resolved from a call site alone, so it
    is dropped. An emitted code that depended on it is reported as unenumerable
    rather than silently omitted.
    """

    parameters: dict[str, list[str]] = {}
    duplicated: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        arguments = node.args
        names = [
            argument.arg
            for argument in list(getattr(arguments, "posonlyargs", []))
            + arguments.args
            + arguments.kwonlyargs
        ]
        if node.name in parameters and parameters[node.name] != names:
            duplicated.add(node.name)
            continue
        parameters[node.name] = names
    for name in duplicated:
        parameters.pop(name, None)
    return parameters


def enclosing_functions(tree: ast.Module) -> dict[ast.AST, str]:
    owners: dict[ast.AST, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                owners.setdefault(child, node.name)
    return owners


def exception_parameters(tree: ast.Module) -> dict[str, list[str]]:
    """Map each stop-exception class to the parameter names of its initializer."""

    constructors: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for member in node.body:
            if not isinstance(member, ast.FunctionDef) or member.name != "__init__":
                continue
            arguments = member.args
            names = [
                argument.arg
                for argument in list(getattr(arguments, "posonlyargs", []))
                + arguments.args
                + arguments.kwonlyargs
            ]
            if "reason_code" in names:
                constructors[node.name] = names[1:] if names[:1] == ["self"] else names
    return constructors


def called_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def bound_arguments(node: ast.Call, names: list[str]) -> list[tuple[str, ast.expr]]:
    # A method call binds its receiver to the leading self parameter.
    offset = 1 if names[:1] == ["self"] and isinstance(node.func, ast.Attribute) else 0
    bound: list[tuple[str, ast.expr]] = []
    for index, argument in enumerate(node.args):
        position = index + offset
        if position < len(names):
            bound.append((names[position], argument))
    for keyword in node.keywords:
        if keyword.arg is not None:
            bound.append((keyword.arg, keyword.value))
    return bound


def evaluate(
    node: ast.expr, caller: str | None, values: dict[tuple[str | None, str], set[str]]
) -> set[str]:
    if isinstance(node, ast.Constant):
        return {node.value} if isinstance(node.value, str) else {DYNAMIC}
    if isinstance(node, ast.Name):
        return set(values.get((caller, node.id), ()))
    if isinstance(node, ast.JoinedStr):
        accumulated = {""}
        for part in node.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                accumulated = {prefix + part.value for prefix in accumulated}
                continue
            if isinstance(part, ast.FormattedValue) and isinstance(part.value, ast.Name):
                substitutions = set(values.get((caller, part.value.id), ()))
                if not substitutions:
                    # The parameter has no known value yet; a later round supplies it.
                    return set()
                accumulated = {prefix + value for prefix in accumulated for value in substitutions}
                continue
            return {DYNAMIC}
        return accumulated
    return {DYNAMIC}


def emitted_codes(tree: ast.Module) -> set[str]:
    """Enumerate every reason code the verifier can write into a manifest.

    Every parameter is propagated rather than a named subset, because any helper
    may forward a caller's literal into the reason-code position of stop().
    """

    parameters = function_parameters(tree)
    constructors = exception_parameters(tree)
    owners = enclosing_functions(tree)
    bindings: list[tuple[str, str, ast.expr, str | None]] = []
    emissions: list[tuple[ast.expr, str | None]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = called_name(node)
        if name is None:
            continue
        if name in constructors:
            # Constructing the stop exception records its reason code as directly as
            # raising it, because the caller may store it and write it to the manifest.
            for parameter, argument in bound_arguments(node, constructors[name]):
                if parameter == "reason_code":
                    emissions.append((argument, owners.get(node)))
        if name not in parameters:
            continue
        bound = bound_arguments(node, parameters[name])
        for parameter, argument in bound:
            bindings.append((name, parameter, argument, owners.get(node)))
            if name == "stop" and parameter == "reason_code":
                emissions.append((argument, owners.get(node)))
            elif name == "run" and parameter == "failure_code":
                emissions.append((argument, owners.get(node)))
    if not emissions:
        raise CoverageError("the verifier emits no reason code, which cannot be right")

    values: dict[tuple[str | None, str], set[str]] = {}
    for _ in range(PROPAGATION_ROUNDS):
        changed = False
        for function, parameter, argument, caller in bindings:
            resolved = evaluate(argument, caller, values)
            known = values.setdefault((function, parameter), set())
            if not resolved <= known:
                known |= resolved
                changed = True
        if not changed:
            break
    else:
        raise CoverageError("the verifier's reason codes did not settle within the bounded rounds")

    codes: set[str] = set()
    for argument, caller in emissions:
        resolved = evaluate(argument, caller, values)
        if not resolved:
            raise CoverageError(
                "the verifier emits a reason code this check cannot enumerate at line "
                f"{getattr(argument, 'lineno', 0)}"
            )
        codes |= resolved
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if (
                isinstance(key, ast.Constant)
                and key.value == "reason_code"
                and isinstance(value, ast.Constant)
                and isinstance(value.value, str)
            ):
                codes.add(value.value)
    if DYNAMIC in codes:
        raise CoverageError("the verifier shapes a reason code from a value this check cannot enumerate")
    return codes


def load_resolver(directory: Path):
    try:
        return SourceFileLoader(
            "triage_copier_update", str(directory / "triage-copier-update.py")
        ).load_module()
    except Exception as exc:  # noqa: BLE001 - reported as one bounded failure
        raise CoverageError(f"resolver is unavailable: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--verifier", type=Path, default=here / "verify-copier-update.py")
    parser.add_argument(
        "--triage-table", type=Path, default=here.parent / "references" / "update-triage.yaml"
    )
    parser.add_argument(
        "--list-codes", action="store_true", help="print the enumerated code space and exit"
    )
    args = parser.parse_args(argv)

    try:
        resolver = load_resolver(here)
        codes = emitted_codes(parse_module(args.verifier))
    except CoverageError as exc:
        print(f"triage coverage failed: {exc}", file=sys.stderr)
        return 2

    if args.list_codes:
        for code in sorted(codes):
            print(code)
        return 0

    try:
        table = resolver.require_table(args.triage_table)
    except resolver.TriageError as exc:
        print(f"triage coverage failed: {exc}", file=sys.stderr)
        return 2

    failures: list[str] = []
    used_codes: set[str] = set()
    used_suffixes: set[str] = set()
    used_subjects: set[str] = set()
    for code in sorted(codes):
        try:
            entry = resolver.resolve_code(table, code)
        except resolver.TriageError as exc:
            failures.append(str(exc))
            continue
        if entry["match"] == "code":
            used_codes.add(entry["matched"])
        else:
            used_suffixes.add(entry["matched"])
            used_subjects.add(entry["subject"])

    for code in sorted(set(table["codes"]) - used_codes):
        failures.append(f"the table classifies reason code {code!r}, which the verifier never emits")
    for suffix in sorted(set(table["suffixes"]) - used_suffixes):
        failures.append(f"the table classifies suffix {suffix!r}, which the verifier never emits")
    for subject in sorted({str(subject) for subject in table["subjects"]} - used_subjects):
        failures.append(f"the table declares subject {subject!r}, which the verifier never shapes")

    if failures:
        for failure in failures:
            print(f"triage coverage failed: {failure}", file=sys.stderr)
        return 1

    print(f"triage coverage passed: {len(codes)} reason codes classified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
