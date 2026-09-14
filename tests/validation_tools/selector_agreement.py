"""Agreement between what the shipped selector emits and what it may run.

The change-aware selector picks commands, then validates its own selection
against the same allowlist the plan commands use. Those two sides are written
separately, so they can disagree: a command the selector emits for a real
changed file may be refused, or admitted and then not actually run.

The guard here derives the emission by running the shipped selector over a real
tree rather than restating the commands it is expected to produce. A filter, a
reassignment, or a substituted iterable that drops a changed Python file fails
these tests because the file is no longer in the emission they read back.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from .support import PLAN_COMMAND_MODULES, load_module


TEMPLATE_PLAN_COMMANDS = PLAN_COMMAND_MODULES[1]
TEMPLATE_SELECTOR = (
    Path(__file__).resolve().parents[2]
    / "template/.project-agent-workflow/scripts/validate-changes.py"
)
COMPILE_PREFIX = ["python3", "-m", "py_compile"]

# Valid Git paths that the previous shell round trip refused, plus the root-level
# option-looking name that was admitted without ever being compiled.
AWKWARD_SOURCE_NAMES = (
    "src/a b.py",
    "src/a$HOME.py",
    "src/it's.py",
    'src/say "hi".py',
    "src/a;b.py",
    "src/a&b.py",
    "-q.py",
    "src/plain.py",
)

# Source roots a template cannot enumerate, plus the ones it does.
WIDE_SOURCE_TREE = (
    "src/build/lookup.py",
    "app/api/routes.py",
    "lib/pkg/helper.py",
    "packages/core/src/index.py",
    "domain/model.py",
    "services/billing/handler.py",
    "internal/tool/run.py",
    "scripts/tool.py",
    "tests/test_thing.py",
    ".project-agent-workflow/scripts/planlib.py",
    ".project-agent-workflow/skills/release/scripts/check.py",
    "setup.py",
)


def shape_corpus() -> tuple[str, ...]:
    """Vary every path property a narrowing filter could key on.

    A listed corpus only proves the names it contains, so a filter written
    against a root, a depth, a digit, a separator count, or a name length that
    nobody listed survives it. These names are generated across those
    properties rather than chosen, and the expectation below is computed from
    the same input by the test's own rule, so no filter inside the selector can
    agree with it by accident.
    """

    roots = (
        "src",
        "app",
        "lib",
        "packages",
        "domain",
        "services",
        "internal",
        "scripts",
        "tests",
        ".project-agent-workflow",
        "vendor",
        "third_party",
        "build",
        "node_modules",
        "Backend",
        "api.v2",
        "x",
        "a_very_long_directory_name_that_no_template_would_ever_enumerate",
    )
    names = (
        "plain.py",
        "user_service.py",
        "base64.py",
        "v2.py",
        "UPPER.py",
        "a" * 60 + ".py",
    )
    paths: list[str] = ["setup.py", "conftest.py", "_bootstrap.py"]
    for index, root in enumerate(roots):
        depth = index % 6
        middle = "/".join(f"level{position}" for position in range(depth))
        prefix = f"{root}/{middle}" if middle else root
        for offset, name in enumerate(names):
            if (index + offset) % 2:
                paths.append(f"{prefix}/{name}")
            else:
                paths.append(f"{prefix}/pkg{offset}/{name}")
    return tuple(paths)


SHAPE_CORPUS = shape_corpus()


def resolves_inside(root: Path, name: str) -> bool:
    """Decide containment here, independently of the selector's own helper."""

    try:
        resolved = (root / name).resolve()
    except OSError:
        return False
    return resolved == root or root in resolved.parents


def expected_compile_targets(root: Path, paths: tuple[str, ...]) -> list[str]:
    """State the rule the selector is supposed to follow, not its output.

    Every changed Python file this repository owns is compiled, named in a form
    a checker reads as a filename, in the order it was changed. Nothing about a
    path's root, depth, spelling, or length enters this rule.
    """

    targets: list[str] = []
    for path in paths:
        name = f"./{path}" if path.startswith("-") else path
        if not name.endswith(".py"):
            continue
        if not (root / name).exists() or not resolves_inside(root, name):
            continue
        targets.append(name)
    return targets


class SelectorAgreementTest(unittest.TestCase):
    """Load the shipped pair against a real tree and compare both sides."""

    def selector_in(self, root: Path) -> object:
        """Load the shipped selector so its repository root is ``root``.

        The module reads its root once at import time, so the working directory
        must already be the tree under test.
        """

        dependency = load_module(TEMPLATE_PLAN_COMMANDS, "plan_validation_commands")
        sys.modules["plan_validation_commands"] = dependency
        self.assertEqual(Path.cwd(), root)
        return load_module(TEMPLATE_SELECTOR, "selector_agreement_validate_changes")

    def compiles(self, commands: list[list[str]]) -> list[list[str]]:
        return [
            command for command in commands if command[: len(COMPILE_PREFIX)] == COMPILE_PREFIX
        ]

    def build(self, root: Path, names: tuple[str, ...]) -> None:
        for name in names:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("value = 1\n", encoding="utf-8")

    def test_every_awkward_source_name_is_selected_compiled_and_admitted(self) -> None:
        """A valid Git path may not abort the run or be skipped by the checker."""

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            self.build(root, AWKWARD_SOURCE_NAMES)
            previous = Path.cwd()
            os.chdir(root)
            try:
                module = self.selector_in(root)
                for mode in ("staged", "all"):
                    with self.subTest(mode=mode):
                        commands = module.select_commands(
                            list(AWKWARD_SOURCE_NAMES), mode
                        )
                        # The selection is validated before it runs, so this is
                        # the exact gate a generated project hits.
                        module.validate_selected_commands(commands)
                        compiles = self.compiles(commands)
                        self.assertEqual(1, len(compiles), commands)
                        emitted = compiles[0][len(COMPILE_PREFIX) :]
                        self.assertEqual(
                            len(AWKWARD_SOURCE_NAMES),
                            len(emitted),
                            "the selector dropped a changed Python file",
                        )
                        # Derive membership from the emission rather than from a
                        # restated command, so any narrowing shows up here.
                        for name in AWKWARD_SOURCE_NAMES:
                            self.assertIn(
                                root / name,
                                [Path(value).resolve() for value in emitted],
                                f"the selector dropped {name}",
                            )
                        # An admitted command that the checker parses as options
                        # reports success without checking anything, so the
                        # emission is run rather than only inspected.
                        result = subprocess.run(
                            compiles[0],
                            cwd=root,
                            capture_output=True,
                            text=True,
                        )
                        self.assertEqual(
                            0,
                            result.returncode,
                            f"{result.stdout}\n{result.stderr}",
                        )
            finally:
                os.chdir(previous)

    def test_a_broken_source_still_fails_the_emitted_compile(self) -> None:
        """The emission must be a real check, not a command that always passes."""

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            self.build(root, ("src/plain.py",))
            (root / "-q.py").write_text("def broken(\n", encoding="utf-8")
            previous = Path.cwd()
            os.chdir(root)
            try:
                module = self.selector_in(root)
                commands = module.select_commands(["-q.py", "src/plain.py"], "all")
                module.validate_selected_commands(commands)
                compiles = self.compiles(commands)
                self.assertEqual(1, len(compiles), commands)
                result = subprocess.run(
                    compiles[0],
                    cwd=root,
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(
                    0,
                    result.returncode,
                    "a root-level name beginning with a hyphen is still unchecked",
                )
            finally:
                os.chdir(previous)

    def test_a_compile_target_resolving_outside_the_repository_is_not_emitted(
        self,
    ) -> None:
        """Lexical containment cannot see a symlink, so resolution decides."""

        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw).resolve()
            root = base / "repository"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            (outside / "escaped.py").write_text("value = 1\n", encoding="utf-8")
            self.build(root, ("src/inside.py",))
            (root / "src/escaped.py").symlink_to(outside / "escaped.py")
            (root / "src/self.py").symlink_to(root / "src/inside.py")
            previous = Path.cwd()
            os.chdir(root)
            try:
                module = self.selector_in(root)
                changed = ["src/inside.py", "src/escaped.py", "src/self.py"]
                commands = module.select_commands(changed, "all")
                module.validate_selected_commands(commands)
                compiles = self.compiles(commands)
                self.assertEqual(1, len(compiles), commands)
                emitted = compiles[0][len(COMPILE_PREFIX) :]
                self.assertEqual(
                    ["src/inside.py", "src/self.py"],
                    emitted,
                    "the selector emitted a target resolving outside the repository",
                )
            finally:
                os.chdir(previous)

    def test_the_emission_is_exactly_the_rule_and_not_a_listed_corpus(self) -> None:
        """Compare the emission against the rule, restated nowhere.

        An enlarged list of names only moves the blind spot: a filter keyed on a
        root, a depth, a digit, a name length, or a call count that the list
        happens not to contain still survives it. The expectation is computed
        from the same input by `expected_compile_targets`, which knows nothing
        about any root, so a narrowing written anywhere in the selector - the
        comprehension, the rebound `paths`, `checkable_name`, `existing`,
        `inside_repository`, or `add_command` - disagrees with it here.
        """

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            self.build(root, SHAPE_CORPUS)
            previous = Path.cwd()
            os.chdir(root)
            try:
                module = self.selector_in(root)
                expected = expected_compile_targets(root, SHAPE_CORPUS)
                self.assertEqual(
                    len(SHAPE_CORPUS),
                    len(expected),
                    "the corpus fixture no longer builds every generated name",
                )
                for mode in ("staged", "all"):
                    with self.subTest(mode=mode):
                        commands = module.select_commands(list(SHAPE_CORPUS), mode)
                        module.validate_selected_commands(commands)
                        compiles = self.compiles(commands)
                        self.assertEqual(1, len(compiles), commands)
                        self.assertEqual(
                            expected,
                            compiles[0][len(COMPILE_PREFIX) :],
                            "the emission no longer follows the rule it is meant to",
                        )
            finally:
                os.chdir(previous)

    def test_the_containment_helpers_carry_no_rule_of_their_own(self) -> None:
        """Pin the helpers the emission guard reaches only through the selector.

        A narrowing moved into `existing` or `inside_repository` changes what is
        emitted without touching any statement a shape guard reads. Both are
        compared against the same independent containment rule, over the same
        varied shapes, so neither can carry a policy of its own.
        """

        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw).resolve()
            root = base / "repository"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            (outside / "escaped.py").write_text("value = 1\n", encoding="utf-8")
            self.build(root, SHAPE_CORPUS)
            (root / "src/escaped.py").symlink_to(outside / "escaped.py")
            previous = Path.cwd()
            os.chdir(root)
            try:
                module = self.selector_in(root)
                probes = (*SHAPE_CORPUS, "src/escaped.py", "absent.py", "README.md")
                for name in probes:
                    with self.subTest(path=name):
                        inside = resolves_inside(root, name)
                        self.assertEqual(
                            inside,
                            module.inside_repository(name),
                            "inside_repository carries a rule of its own",
                        )
                        self.assertEqual(
                            (root / name).exists() and inside,
                            module.existing(name),
                            "existing carries a rule of its own",
                        )
            finally:
                os.chdir(previous)

    def test_the_selector_emits_no_command_its_own_allowlist_refuses(self) -> None:
        """Run the whole emission, not the compile alone, through the allowlist."""

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            self.build(root, SHAPE_CORPUS)
            (root / "scripts/build.sh").write_text("true\n", encoding="utf-8")
            previous = Path.cwd()
            os.chdir(root)
            try:
                module = self.selector_in(root)
                dependency = module.plan_validation_commands
                changed = [*SHAPE_CORPUS, "scripts/build.sh", "README.md"]
                for mode in ("staged", "all"):
                    with self.subTest(mode=mode):
                        commands = module.select_commands(changed, mode)
                        for command in commands:
                            dependency.validate_argv(
                                tuple(command), " ".join(command)
                            )
            finally:
                os.chdir(previous)

    def test_a_shell_script_outside_the_enumerated_roots_still_disagrees(self) -> None:
        """Record the one disagreement this plan does not close.

        The selector emits `sh -n` for any changed shell script, but the
        allowlist admits only four enumerated roots, so a shell script anywhere
        else aborts the whole run. Widening that rule is separately authorized
        work and is not admitted here, so the remaining gap is asserted rather
        than left to a corpus that happens to avoid it. This test fails once the
        gap is closed, which is the point at which it must be rewritten.
        """

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            for name in ("build.sh", "src/entry.sh", "ci/deploy.sh"):
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("true\n", encoding="utf-8")
            (root / "scripts/inside.sh").parent.mkdir(parents=True, exist_ok=True)
            (root / "scripts/inside.sh").write_text("true\n", encoding="utf-8")
            previous = Path.cwd()
            os.chdir(root)
            try:
                module = self.selector_in(root)
                # The selector reloads its dependency under the same module
                # name, so the exception class must come from the instance the
                # selector actually raises through.
                dependency = module.plan_validation_commands
                module.validate_selected_commands(
                    module.select_commands(["scripts/inside.sh"], "all")
                )
                for name in ("build.sh", "src/entry.sh", "ci/deploy.sh"):
                    with self.subTest(changed=name):
                        commands = module.select_commands([name], "all")
                        self.assertIn(["sh", "-n", name], commands)
                        with self.assertRaises(dependency.ValidationCommandError):
                            module.validate_selected_commands(commands)
            finally:
                os.chdir(previous)

    def test_a_target_dropped_for_containment_is_reported(self) -> None:
        """A dropped check must not look like a check that passed."""

        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw).resolve()
            root = base / "repository"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            (outside / "escaped.py").write_text("value = 1\n", encoding="utf-8")
            self.build(root, ("src/inside.py",))
            (root / "src/escaped.py").symlink_to(outside / "escaped.py")
            previous = Path.cwd()
            os.chdir(root)
            try:
                module = self.selector_in(root)
                module.select_commands(["src/inside.py", "src/escaped.py"], "all")
                self.assertEqual(
                    ["src/escaped.py"],
                    module.SKIPPED_OUTSIDE_REPOSITORY,
                    "the containment drop is silent",
                )
            finally:
                os.chdir(previous)

    def test_the_real_git_pipeline_delivers_every_awkward_name(self) -> None:
        """Selection starts at Git, so the corpus must survive that step too.

        Passing names straight to the selector proves nothing about the name
        Git actually reports. A path holding a quote or a non-ASCII byte is
        C-quoted in Git's default output, and the quoted text does not end in
        .py, so the file would leave the selection before any guard above sees
        it. This drives the shipped entry point over a real repository instead.
        """

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            for command in (
                ["git", "init", "--quiet", "-b", "main"],
                ["git", "config", "user.email", "test@example.invalid"],
                ["git", "config", "user.name", "test"],
            ):
                subprocess.run(command, cwd=root, check=True, capture_output=True)
            names = (*AWKWARD_SOURCE_NAMES, "src/\u65e5\u672c\u8a9e.py", "src/back\\slash.py")
            for name in names:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("value = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
            result = subprocess.run(
                [
                    sys.executable,
                    str(TEMPLATE_SELECTOR),
                    "--staged",
                    "--print-only",
                    "--json",
                ],
                cwd=root,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONPATH": str(TEMPLATE_PLAN_COMMANDS.parent)},
            )
            self.assertEqual(0, result.returncode, result.stderr)
            report = json.loads(result.stdout)
            compiles = [
                record["argv"]
                for record in report["commands"]
                if record["argv"][: len(COMPILE_PREFIX)] == COMPILE_PREFIX
            ]
            self.assertEqual(1, len(compiles), report)
            self.assertEqual(
                {root / name for name in names},
                {(root / value).resolve() for value in compiles[0][len(COMPILE_PREFIX) :]},
                "Git's own report dropped a changed source file",
            )

    def test_the_real_git_pipeline_runs_the_checks_it_selects(self) -> None:
        """A selected check that never runs is the failure this plan is about."""

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            for command in (
                ["git", "init", "--quiet", "-b", "main"],
                ["git", "config", "user.email", "test@example.invalid"],
                ["git", "config", "user.name", "test"],
            ):
                subprocess.run(command, cwd=root, check=True, capture_output=True)
            (root / "src").mkdir()
            (root / "src/ok.py").write_text("value = 1\n", encoding="utf-8")
            (root / "-q.py").write_text("def broken(\n", encoding="utf-8")
            subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
            result = subprocess.run(
                [sys.executable, str(TEMPLATE_SELECTOR), "--staged", "--json"],
                cwd=root,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONPATH": str(TEMPLATE_PLAN_COMMANDS.parent)},
            )
            self.assertNotEqual(0, result.returncode, result.stdout)
            report = json.loads(result.stdout)
            self.assertEqual("failed", report["status"], report)

