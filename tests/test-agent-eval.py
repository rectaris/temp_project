#!/usr/bin/env python3
"""Behavior tests for freezing evaluation experiments before execution.

Every test resolves against a disposable copy of `evals/` and the capability
registry, so no test writes into this repository. The development suite is
synthetic: these tests establish what the resolver records and refuses, never
how any model performs.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMMAND = ROOT / "scripts/agent-eval.py"
COMPARISON = ROOT / "template/.project-agent-workflow/scripts/compare-harness-runs.py"
EXPERIMENT = "evals/experiments/codex-replication-dev.json"
EXPERIMENT_ID = "codex-replication-dev"
SMALL_FIX = "evals/cases/coding-core-dev/small-fix"
CROSS_FILE = "evals/cases/coding-core-dev/cross-file-change"
CONFIGURATION = "evals/configurations/codex-current.json"
REPLICA = "evals/configurations/codex-current-replica.json"
ENVIRONMENT = "evals/environments/bwrap-default.json"
REGISTRY = "docs/agent/capability-registry.json"

# The commit a fixed two-file tree must yield on every host, so a baseline can
# never depend on this repository's history, the clock or the umask.
PINNED_TREE = [("pkg/mod.py", b"VALUE = 1\n"), ("README", b"fixture\n")]
PINNED_COMMIT = "fad29a08ec16748b1a5cbc4c7f3ef3680547a692437b58ce441bcbc36cb5b9dc"
PROFILE_ADVICE = b"Prefer the smallest change that passes the case checks.\n"

# The resolver's own sources, copied into the disposable repository so that
# the no-write boundary also covers whatever running the command writes.
TOOL_SOURCES = (
    "scripts/agent-eval.py",
    "scripts/project_workflow/__init__.py",
    "scripts/project_workflow/agent_eval_definitions.py",
    "template/.project-agent-workflow/scripts/compare-harness-runs.py",
    "template/.project-agent-workflow/scripts/check-harness-profile.py",
)

# Reference fixes that prove each development case is satisfiable.
REFERENCE_FIXES = {
    "small-fix": {
        "calc.py": '''"""Small arithmetic helpers."""


def clamp(value, low, high):
    """Return value limited to the inclusive range from low to high."""
    if value < low:
        return low
    if value > high:
        return high
    return value
''',
    },
    "cross-file-change": {
        "limits.py": '''"""Item limits shared by the report helpers."""

DEFAULT_LIMIT = 3


def apply_limit(items, limit):
    """Return the first limit items."""
    if limit < 0:
        raise ValueError("limit must not be negative")
    return list(items)[:limit]
''',
        "report.py": '''"""Plain-text report helpers."""

from limits import DEFAULT_LIMIT, apply_limit


def summarize(items, limit=DEFAULT_LIMIT):
    """Return a one-line summary of the leading items and the total count."""
    items = list(items)
    shown = apply_limit(items, limit)
    return f"{len(items)} items: " + ", ".join(str(item) for item in shown)
''',
    },
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


definitions = load_module(
    "test_agent_eval_definitions", ROOT / "scripts/project_workflow/agent_eval_definitions.py"
)
comparison = load_module("test_agent_eval_comparison", COMPARISON)


def sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def canonical(value) -> str:
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def read_json(root: Path, relative: str):
    return json.loads((root / relative).read_text(encoding="utf-8"))


def write_json(root: Path, relative: str, value) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def edit_json(root: Path, relative: str, change) -> None:
    value = read_json(root, relative)
    change(value)
    write_json(root, relative, value)


def snapshot(root: Path, exclude: Path | None = None) -> dict[str, tuple]:
    """Map every path below root to its type, mode and bytes."""

    state: dict[str, tuple] = {}
    for current, directories, files in os.walk(root):
        current_path = Path(current)
        if exclude is not None and (current_path == exclude or exclude in current_path.parents):
            directories[:] = []
            continue
        for name in directories + files:
            path = current_path / name
            if exclude is not None and path == exclude:
                continue
            info = os.lstat(path)
            relative = path.relative_to(root).as_posix()
            if os.path.islink(path):
                state[relative] = ("link", os.readlink(path))
            elif path.is_dir():
                state[relative] = ("dir", info.st_mode)
            else:
                state[relative] = ("file", info.st_mode, path.read_bytes())
    return state


class ResolverFixture(unittest.TestCase):
    """Give each test a disposable repository root holding the shipped suite."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "repository"
        self.root.mkdir()
        shutil.copytree(ROOT / "evals", self.root / "evals", symlinks=True)
        (self.root / "docs/agent").mkdir(parents=True)
        shutil.copyfile(ROOT / REGISTRY, self.root / REGISTRY)

    @property
    def output(self) -> Path:
        return self.root / ".agent-artifacts/evaluations" / EXPERIMENT_ID

    def resolve(self, experiment: str = EXPERIMENT, **environment: str) -> subprocess.CompletedProcess:
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", **environment)
        return subprocess.run(
            [sys.executable, str(COMMAND), "resolve", experiment, "--root", str(self.root)],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

    def assert_resolves(self, experiment: str = EXPERIMENT) -> dict:
        result = self.resolve(experiment)
        self.assertEqual(result.returncode, 0, result.stderr)
        return read_json(self.output, "experiment.json")

    def assert_refused(self, fragment: str, experiment: str = EXPERIMENT) -> None:
        result = self.resolve(experiment)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("agent-eval resolve failed:", result.stderr)
        self.assertIn(fragment, result.stderr)
        self.assertFalse(
            (self.root / ".agent-artifacts").exists(),
            "a refused resolve must not write anything",
        )


class DefinitionShapeTest(ResolverFixture):
    def test_unknown_and_missing_keys_are_refused_in_every_definition(self) -> None:
        targets = (
            (f"{SMALL_FIX}/case.json", "benchmark case"),
            (CONFIGURATION, "run configuration"),
            (ENVIRONMENT, "environment configuration"),
            (EXPERIMENT, "experiment definition"),
        )
        for relative, label in targets:
            original = (self.root / relative).read_bytes()
            for mutation, fragment in (
                (lambda value: value.update(extra=True), "unknown=['extra']"),
                (lambda value: value.pop("schema_version"), "missing=['schema_version']"),
            ):
                with self.subTest(definition=label, fragment=fragment):
                    edit_json(self.root, relative, mutation)
                    self.assert_refused(fragment)
                    self.assertIn(label, self.resolve().stderr)
                    (self.root / relative).write_bytes(original)

    def test_nested_objects_have_exact_keys(self) -> None:
        for relative, change, fragment in (
            (CONFIGURATION, lambda v: v["runtime"].update(os="linux"), "runtime has an invalid"),
            (CONFIGURATION, lambda v: v["reasoning"].pop("effort"), "reasoning has an invalid"),
            (EXPERIMENT, lambda v: v["budget"].update(tokens=1), "budget has an invalid"),
            (EXPERIMENT, lambda v: v["decision_limits"].pop("max_cost_ratio"), "decision_limits has"),
            (EXPERIMENT, lambda v: v["comparisons"][0].update(note="x"), "comparisons[0] has"),
        ):
            with self.subTest(fragment=fragment):
                original = (self.root / relative).read_bytes()
                edit_json(self.root, relative, change)
                self.assert_refused(fragment)
                (self.root / relative).write_bytes(original)

    def test_schema_version_must_be_the_integer_one(self) -> None:
        for relative in (f"{CROSS_FILE}/case.json", REPLICA, ENVIRONMENT, EXPERIMENT):
            original = (self.root / relative).read_bytes()
            for version in (True, 1.0, "1", 2, None):
                with self.subTest(definition=relative, version=version):
                    edit_json(self.root, relative, lambda value: value.update(schema_version=version))
                    self.assert_refused("schema_version must be the integer 1")
                    (self.root / relative).write_bytes(original)

    def test_repeated_json_key_is_refused(self) -> None:
        path = self.root / ENVIRONMENT
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace('"sandbox": "bubblewrap",', '"sandbox": "bubblewrap", "sandbox": "bubblewrap",'))
        self.assert_refused("repeats the JSON key 'sandbox'")

    def test_duplicate_ids_are_refused(self) -> None:
        cases = (
            (lambda v: v["cases"].append("coding-core-dev/small-fix"), "cases repeats"),
            (lambda v: v["configurations"].append("codex-current"), "configurations repeats"),
            (lambda v: v["comparisons"].append(dict(v["comparisons"][0], baseline="codex-current-replica", candidate="codex-current")), "repeats comparison_id"),
            (lambda v: v["comparisons"].append(dict(v["comparisons"][0], comparison_id="again")), "repeats the pair"),
        )
        original = (self.root / EXPERIMENT).read_bytes()
        for change, fragment in cases:
            with self.subTest(fragment=fragment):
                edit_json(self.root, EXPERIMENT, change)
                self.assert_refused(fragment)
                (self.root / EXPERIMENT).write_bytes(original)

    def raise_budget(self) -> None:
        """Leave room for one added case or configuration, so a reference check decides."""

        edit_json(self.root, EXPERIMENT, lambda v: v.update(budget={"max_total_runs": 12, "max_elapsed_seconds": 100000}))

    def test_one_case_id_in_two_suites_is_refused(self) -> None:
        self.raise_budget()
        shutil.copytree(self.root / SMALL_FIX, self.root / "evals/cases/other-suite/small-fix")
        edit_json(self.root, "evals/cases/other-suite/small-fix/case.json", lambda v: v.update(suite="other-suite"))
        edit_json(self.root, EXPERIMENT, lambda v: v["cases"].append("other-suite/small-fix"))
        self.assert_refused("experiment case ids repeats 'small-fix'")

    def test_undeclared_references_are_refused(self) -> None:
        self.raise_budget()
        cases = (
            (EXPERIMENT, lambda v: v["cases"].append("coding-core-dev/missing"), "benchmark case does not exist"),
            (EXPERIMENT, lambda v: v["configurations"].append("codex-missing"), "run configuration does not exist"),
            (EXPERIMENT, lambda v: v["comparisons"][0].update(candidate="codex-other"), "names an undeclared candidate configuration"),
            (EXPERIMENT, lambda v: v["comparisons"][0].update(candidate="codex-current"), "pairs a configuration with itself"),
            (CONFIGURATION, lambda v: v.update(environment_id="bwrap-missing"), "environment configuration does not exist"),
            (CONFIGURATION, lambda v: v.update(configuration_id="codex-renamed"), "differs from its file name"),
            (f"{SMALL_FIX}/case.json", lambda v: v.update(suite="other-suite"), "suite differs from its directory name"),
            (EXPERIMENT, lambda v: v.update(experiment_id="renamed"), "differs from its file name"),
        )
        for relative, change, fragment in cases:
            with self.subTest(fragment=fragment):
                original = (self.root / relative).read_bytes()
                edit_json(self.root, relative, change)
                self.assert_refused(fragment)
                (self.root / relative).write_bytes(original)

    def test_confined_paths_are_refused(self) -> None:
        prompts = self.root / "evals/prompts"
        os.symlink("task-frame-v1.md", prompts / "linked.md")
        os.symlink("prompts", self.root / "evals/linked-prompts")
        os.mkfifo(prompts / "pipe.md")
        cases = (
            ("/etc/hostname", "not absolute"),
            ("evals/../docs/agent/capability-registry.json", "must not traverse"),
            (REGISTRY, "must name a file inside evals/"),
            ("evals//prompts/task-frame-v1.md", "must be a normalized path"),
            ("evals/./prompts/task-frame-v1.md", "must be a normalized path"),
            ("evals\\prompts\\task-frame-v1.md", "backslash"),
            ("evals/prompts/linked.md", "symlinked component"),
            ("evals/linked-prompts/task-frame-v1.md", "symlinked component"),
            ("evals/prompts", "not a regular file"),
            ("evals/prompts/pipe.md", "not a regular file"),
        )
        original = (self.root / CONFIGURATION).read_bytes()
        for path, fragment in cases:
            with self.subTest(path=path):
                edit_json(self.root, CONFIGURATION, lambda v: v.update(instruction_assets=[path]))
                self.assert_refused(fragment)
                (self.root / CONFIGURATION).write_bytes(original)

    def test_experiment_argument_is_confined(self) -> None:
        shutil.copyfile(self.root / EXPERIMENT, self.root / "evals/codex-replication-dev.json")
        for argument, fragment in (
            (str(self.root / EXPERIMENT), "not absolute"),
            ("evals/codex-replication-dev.json", "evals/experiments/<id>.json"),
            ("evals/experiments/../experiments/codex-replication-dev.json", "must not traverse"),
        ):
            with self.subTest(argument=argument):
                self.assert_refused(fragment, experiment=argument)

    def test_symlinked_definition_and_fixture_member_are_refused(self) -> None:
        experiments = self.root / "evals/experiments"
        os.rename(experiments / "codex-replication-dev.json", self.root / "evals/real.json")
        os.symlink("../real.json", experiments / "codex-replication-dev.json")
        self.assert_refused("symlinked component")
        os.remove(experiments / "codex-replication-dev.json")
        os.rename(self.root / "evals/real.json", experiments / "codex-replication-dev.json")

        os.symlink("calc.py", self.root / SMALL_FIX / "repository/alias.py")
        self.assert_refused("fixture tree contains a symlink")
        os.remove(self.root / SMALL_FIX / "repository/alias.py")

        (self.root / SMALL_FIX / "repository/.git").mkdir()
        (self.root / SMALL_FIX / "repository/.git/HEAD").write_text("ref: refs/heads/main\n")
        self.assert_refused("must not name Git metadata")

    def test_fixture_directories_count_toward_the_entry_bound(self) -> None:
        repository = self.root / SMALL_FIX / "repository"
        for index in range(definitions.MAX_FIXTURE_ENTRIES):
            (repository / f"empty-{index:04d}").mkdir()
        self.assert_refused("files and directories")

    def test_sizes_are_bounded(self) -> None:
        cases = (
            (f"{SMALL_FIX}/case.json", definitions.MAX_DEFINITION_BYTES, "benchmark case exceeds"),
            (f"{SMALL_FIX}/task.md", definitions.MAX_TEXT_BYTES, "task exceeds"),
            ("evals/prompts/task-frame-v1.md", definitions.MAX_INSTRUCTION_ASSET_BYTES, "instruction asset exceeds"),
            (f"{SMALL_FIX}/repository/calc.py", definitions.MAX_FIXTURE_FILE_BYTES, "fixture tree file exceeds"),
        )
        for relative, limit, fragment in cases:
            with self.subTest(path=relative):
                path = self.root / relative
                original = path.read_bytes()
                # Trailing whitespace keeps a JSON definition valid, so only
                # the byte bound can refuse it.
                path.write_bytes(original + b" " * (limit + 1 - len(original)))
                self.assert_refused(fragment)
                path.write_bytes(original)

    def test_values_outside_phase_one_are_refused(self) -> None:
        for relative, change, fragment in (
            (ENVIRONMENT, lambda v: v.update(cache_policy="warm"), "cache_policy must be one of"),
            (ENVIRONMENT, lambda v: v.update(cpu_limit="2"), "cpu_limit must be one of"),
            (ENVIRONMENT, lambda v: v.update(sandbox="podman"), "sandbox must be one of"),
            (EXPERIMENT, lambda v: v.update(ordering="randomized"), "ordering must be one of"),
            (CONFIGURATION, lambda v: v["reasoning"].update(supported=False), "effort must be null"),
            (f"{SMALL_FIX}/case.json", lambda v: v.update(protected_paths=["calc.py"]), "both allowed and protected"),
            (f"{SMALL_FIX}/case.json", lambda v: v.update(allowed_write_paths=["../calc.py"]), "inside the fixture repository"),
            (f"{SMALL_FIX}/case.json", lambda v: v.update(validation_commands=[[]]), "validation_commands[0] must be a list"),
            (f"{SMALL_FIX}/case.json", lambda v: v.update(timeout_seconds=True), "timeout_seconds must be an integer"),
            (f"{CROSS_FILE}/case.json", lambda v: v.update(holdout="withheld"), "share one holdout status"),
        ):
            with self.subTest(fragment=fragment):
                original = (self.root / relative).read_bytes()
                edit_json(self.root, relative, change)
                self.assert_refused(fragment)
                (self.root / relative).write_bytes(original)

    def write_profile_catalog(self, asset_path: str) -> dict:
        """Install a one-revision catalog and return a selection of that revision."""

        write_json(self.root, "docs/agent/harness-instructions.json", {
            "schema_version": 1,
            "governing_sources": [],
            "supplemental_revisions": [{
                "id": "small-change",
                "revision": "v1",
                "content_digest": sha(PROFILE_ADVICE),
                "applicability": {"task_types": ["implementation"], "model_selector": None},
                "introduction_reason": "Synthetic revision for the resolver tests.",
                "failure_case_references": ["synthetic"],
                "review_evidence": {
                    "comparison_protocol_digest": sha(b"protocol"),
                    "comparison_report_digest": sha(b"report"),
                    "evidence_digests": [sha(b"evidence")],
                },
                "status": "active",
            }],
        })
        (self.root / asset_path).parent.mkdir(parents=True, exist_ok=True)
        (self.root / asset_path).write_bytes(PROFILE_ADVICE)
        return {
            "schema_version": 1,
            "selections": [{
                "id": "small-change",
                "revision": "v1",
                "content_digest": sha(PROFILE_ADVICE),
                "asset_path": asset_path,
            }],
        }

    def select_profile(self, path: str) -> None:
        edit_json(self.root, REPLICA, lambda v: v.update(harness_profile_selection={"path": path}))

    def test_harness_profile_selection_is_validated_and_its_assets_are_bound(self) -> None:
        advice = "docs/agent/advice/small-change.md"
        write_json(self.root, "evals/profiles/small-change.json", self.write_profile_catalog(advice))
        self.select_profile("evals/profiles/small-change.json")
        record = self.assert_resolves()
        current, replica = record["configurations"]
        selection = replica["harness_profile_selection"]
        self.assertEqual(selection["digest"], sha((self.root / "evals/profiles/small-change.json").read_bytes()))
        self.assertEqual(selection["catalog"]["digest"], sha((self.root / "docs/agent/harness-instructions.json").read_bytes()))
        self.assertEqual([item["id"] for item in selection["selected_revisions"]], ["small-change"])
        instructions = replica["dimensions"]["instructions"]
        self.assertEqual(instructions["harness_profile_selection_digest"], selection["digest"])
        self.assertEqual(instructions["instruction_asset_digests"][advice], sha(PROFILE_ADVICE))
        self.assertIn("evals/prompts/task-frame-v1.md", instructions["instruction_asset_digests"])
        self.assertIsNone(current["dimensions"]["instructions"]["harness_profile_selection_digest"])
        protocol = comparison.parse_protocol(str(self.output / "protocol.json"))
        self.assertEqual(protocol["comparisons"][0]["axis"], "instructions")

    def test_repository_profile_selection_path_is_accepted(self) -> None:
        self.write_profile_catalog("docs/agent/advice/small-change.md")
        write_json(self.root, "docs/agent/harness-profile.json", {"schema_version": 1, "selections": []})
        self.select_profile("docs/agent/harness-profile.json")
        record = self.assert_resolves()
        replica = record["configurations"][1]
        self.assertEqual(replica["harness_profile_selection"]["selected_revisions"], [])
        self.assertEqual(
            replica["dimensions"]["instructions"]["harness_profile_selection_digest"],
            sha((self.root / "docs/agent/harness-profile.json").read_bytes()),
        )

    def test_invalid_harness_profile_selections_are_refused(self) -> None:
        advice = "docs/agent/advice/small-change.md"
        valid = self.write_profile_catalog(advice)
        self.select_profile("evals/profiles/selection.json")
        unknown = json.loads(json.dumps(valid))
        unknown["selections"][0]["revision"] = "v2"
        drifted = json.loads(json.dumps(valid))
        drifted["selections"][0]["content_digest"] = sha(b"other advice")
        for document, fragment in (
            ({"schema_version": 1, "selections": [1]}, "refused by check-harness-profile.py"),
            (unknown, "unknown supplemental revision"),
            (drifted, "selection digest does not match catalog"),
            ({"schema_version": 1, "selections": {}}, "unsupported profile schema"),
        ):
            with self.subTest(fragment=fragment):
                write_json(self.root, "evals/profiles/selection.json", document)
                self.assert_refused(fragment)
        write_json(self.root, "evals/profiles/selection.json", valid)
        (self.root / advice).write_bytes(b"changed advice\n")
        self.assert_refused("supplemental asset digest mismatch")

    def test_selection_paths_stay_confined(self) -> None:
        self.write_profile_catalog("docs/agent/advice/small-change.md")
        write_json(self.root, "docs/agent/other-profile.json", {"schema_version": 1, "selections": []})
        self.select_profile("docs/agent/other-profile.json")
        self.assert_refused("must name a file inside evals/")
        write_json(self.root, "evals/profiles/overlap.json", self.write_profile_catalog("evals/prompts/advice.md"))
        edit_json(self.root, REPLICA, lambda v: v.update(
            instruction_assets=["evals/prompts/task-frame-v1.md", "evals/prompts/advice.md"],
            harness_profile_selection={"path": "evals/profiles/overlap.json"},
        ))
        self.assert_refused("names Harness Profile assets as instruction_assets too")


class BaselineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.count = 0

    def build(self, files) -> str:
        self.count += 1
        return definitions.build_fixture_baseline(
            files, self.base / f"{self.count}.git", self.base / f"scratch-{self.count}"
        )

    def git(self, repository: Path, *arguments: str) -> str:
        return subprocess.run(
            ["git", f"--git-dir={repository}", *arguments],
            capture_output=True, text=True, check=True,
            env=dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull),
        ).stdout

    def test_fixed_tree_yields_the_pinned_commit(self) -> None:
        self.assertEqual(self.build(PINNED_TREE), PINNED_COMMIT)
        self.assertEqual(self.build(list(reversed(PINNED_TREE))), PINNED_COMMIT)
        commit = self.git(self.base / "1.git", "cat-file", "-p", PINNED_COMMIT)
        identity = definitions.BASELINE_IDENTITY
        self.assertIn(f"author {identity['author']} {identity['timestamp']}\n", commit)
        self.assertIn(f"committer {identity['committer']} {identity['timestamp']}\n", commit)
        self.assertNotIn("parent ", commit)
        modes = {line.split()[0] for line in self.git(self.base / "1.git", "ls-tree", "-r", PINNED_COMMIT).splitlines()}
        self.assertEqual(modes, {"100644"})

    def test_host_modes_and_times_do_not_change_the_commit(self) -> None:
        tree = self.base / "tree"
        for mode, stamp in ((0o644, 1_000_000_000), (0o755, 1_700_000_000)):
            with self.subTest(mode=oct(mode)):
                if tree.exists():
                    shutil.rmtree(tree)
                for path, data in PINNED_TREE:
                    target = tree / "repository" / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                    os.chmod(target, mode)
                    os.utime(target, (stamp, stamp))
                files = definitions.read_fixture_tree(tree, "repository", "fixture")
                self.assertEqual(self.build(files), PINNED_COMMIT)

    def test_one_changed_byte_changes_the_commit(self) -> None:
        changed = [("pkg/mod.py", b"VALUE = 2\n"), ("README", b"fixture\n")]
        renamed = [("pkg/mod2.py", b"VALUE = 1\n"), ("README", b"fixture\n")]
        commits = {self.build(PINNED_TREE), self.build(changed), self.build(renamed)}
        self.assertEqual(len(commits), 3)

    def test_existing_destination_is_refused(self) -> None:
        (self.base / "taken.git").mkdir()
        with self.assertRaisesRegex(definitions.DefinitionError, "already exists"):
            definitions.build_fixture_baseline(PINNED_TREE, self.base / "taken.git", self.base / "s")


class ResolveTest(ResolverFixture):
    def test_record_binds_the_digest_of_every_input(self) -> None:
        record = self.assert_resolves()
        self.assertEqual(sorted(os.listdir(self.output)), ["experiment.json", "matrix.json", "protocol.json"])
        root = self.root
        self.assertEqual(record["definition"], {"path": EXPERIMENT, "digest": sha((root / EXPERIMENT).read_bytes())})
        self.assertEqual(record["capability_registry"], {"path": REGISTRY, "digest": sha((root / REGISTRY).read_bytes())})
        self.assertEqual([case["case_id"] for case in record["cases"]], ["small-fix", "cross-file-change"])
        for case, directory in zip(record["cases"], (SMALL_FIX, CROSS_FILE)):
            definition = read_json(root, f"{directory}/case.json")
            self.assertEqual(case["definition"]["digest"], sha((root / directory / "case.json").read_bytes()))
            self.assertEqual(case["task"]["digest"], sha((root / directory / "task.md").read_bytes()))
            self.assertEqual(case["acceptance"]["digest"], sha((root / directory / "acceptance.md").read_bytes()))
            self.assertEqual(case["validation_commands_digest"], canonical(definition["validation_commands"]))
            members = sorted(
                path.relative_to(root / directory / "repository").as_posix()
                for path in (root / directory / "repository").rglob("*") if path.is_file()
            )
            manifest = [
                {"path": member, "digest": sha((root / directory / "repository" / member).read_bytes())}
                for member in members
            ]
            self.assertEqual(case["fixture_tree"]["files"], manifest)
            self.assertEqual(case["fixture_tree"]["digest"], canonical(manifest))
            self.assertEqual(case["repository_baseline"], f"sha256:{case['baseline_commit']}")
        frame = sha((root / "evals/prompts/task-frame-v1.md").read_bytes())
        for configuration, relative in zip(record["configurations"], (CONFIGURATION, REPLICA)):
            self.assertEqual(configuration["definition"]["digest"], sha((root / relative).read_bytes()))
            self.assertEqual(configuration["instruction_assets"], [{"path": "evals/prompts/task-frame-v1.md", "digest": frame}])
            dimensions = configuration["dimensions"]
            self.assertEqual(dimensions["capability_registry_digest"], record["capability_registry"]["digest"])
            self.assertEqual(dimensions["environment_configuration_digest"], sha((root / ENVIRONMENT).read_bytes()))
        environment = record["environments"][0]
        self.assertEqual(environment["definition"]["digest"], sha((root / ENVIRONMENT).read_bytes()))
        self.assertEqual(
            (environment["sandbox"], environment["network"], environment["cache_policy"], environment["cpu_limit"], environment["memory_limit"]),
            ("bubblewrap", "shared_for_provider", "cold", "uncontrolled", "uncontrolled"),
        )
        self.assertEqual(record["comparison_command"]["digest"], sha(COMPARISON.read_bytes()))
        self.assertEqual(record["protocol"]["digest"], sha((self.output / "protocol.json").read_bytes()))
        self.assertEqual(record["matrix"]["digest"], sha((self.output / "matrix.json").read_bytes()))

    def test_changed_input_changes_its_bound_digest(self) -> None:
        first = self.assert_resolves()
        shutil.rmtree(self.root / ".agent-artifacts")
        path = self.root / CROSS_FILE / "repository/limits.py"
        path.write_bytes(path.read_bytes() + b"# changed\n")
        (self.root / SMALL_FIX / "acceptance.md").write_text("# Acceptance\n\n- changed\n")
        second = self.assert_resolves()
        self.assertEqual(first["cases"][0]["baseline_commit"], second["cases"][0]["baseline_commit"])
        self.assertNotEqual(first["cases"][0]["acceptance"]["digest"], second["cases"][0]["acceptance"]["digest"])
        self.assertNotEqual(first["cases"][1]["fixture_tree"]["digest"], second["cases"][1]["fixture_tree"]["digest"])
        self.assertNotEqual(first["cases"][1]["baseline_commit"], second["cases"][1]["baseline_commit"])

    def test_existing_experiment_directory_is_refused(self) -> None:
        self.assert_resolves()
        before = snapshot(self.root)
        result = self.resolve()
        self.assertEqual(result.returncode, 1)
        self.assertIn("experiment directory already exists", result.stderr)
        self.assertEqual(snapshot(self.root), before)

        shutil.rmtree(self.output)
        self.output.mkdir()
        result = self.resolve()
        self.assertEqual(result.returncode, 1)
        self.assertIn("experiment directory already exists", result.stderr)
        self.assertEqual(os.listdir(self.output), [])

    def test_symlinked_output_ancestor_is_refused(self) -> None:
        elsewhere = Path(self.temporary.name) / "elsewhere"
        elsewhere.mkdir()
        os.symlink(elsewhere, self.root / ".agent-artifacts")
        result = self.resolve()
        self.assertEqual(result.returncode, 1)
        self.assertIn("not a plain directory", result.stderr)
        self.assertEqual(os.listdir(elsewhere), [])

    def test_protocol_is_accepted_by_the_comparison_parser(self) -> None:
        record = self.assert_resolves()
        parsed = comparison.parse_protocol(str(self.output / "protocol.json"))
        self.assertEqual(parsed["schema_version"], 2)
        protocol = read_json(self.output, "protocol.json")
        for declared, resolved in zip(protocol["configurations"], record["configurations"]):
            self.assertEqual(declared["configuration_digest"], canonical(declared["dimensions"]))
            self.assertEqual(declared["configuration_digest"], resolved["configuration_digest"])
            self.assertEqual(declared["dimensions"], resolved["dimensions"])
        self.assertEqual(protocol["configurations"][0]["dimensions"], protocol["configurations"][1]["dimensions"])
        self.assertEqual(parsed["comparisons"][0]["classification"], "replication")
        self.assertEqual(
            [case["repository_baseline"] for case in protocol["cases"]],
            [case["repository_baseline"] for case in record["cases"]],
        )
        self.assertEqual({case["fixture_kind"] for case in protocol["cases"]}, {"synthetic"})
        self.assertEqual(protocol["freeze"]["holdout_status"], "used_for_tuning")
        self.assertIsNone(protocol["freeze"]["ordering_evidence"])

    def test_two_different_configurations_resolve_to_a_single_axis_comparison(self) -> None:
        edit_json(self.root, REPLICA, lambda v: v.update(model="gpt-5.6-luna"))
        self.assert_resolves()
        parsed = comparison.parse_protocol(str(self.output / "protocol.json"))
        entry = parsed["comparisons"][0]
        self.assertEqual((entry["classification"], entry["axis"]), ("single_axis_effect", "model"))
        digests = [item["configuration_digest"] for item in parsed["configurations"].values()]
        self.assertEqual(len(set(digests)), 2)

    def cells(self) -> list[tuple]:
        matrix = read_json(self.output, "matrix.json")
        return [(run["repetition"], run["case_id"], run["configuration_id"]) for run in matrix["runs"]]

    def test_balanced_ordering_alternates_the_first_configuration(self) -> None:
        self.assert_resolves()
        a, b = "codex-current", "codex-current-replica"
        self.assertEqual(self.cells(), [
            (1, "small-fix", a), (1, "small-fix", b), (1, "cross-file-change", a), (1, "cross-file-change", b),
            (2, "small-fix", b), (2, "small-fix", a), (2, "cross-file-change", b), (2, "cross-file-change", a),
        ])
        matrix = read_json(self.output, "matrix.json")
        self.assertEqual(matrix["run_count"], 8)
        self.assertEqual([run["order"] for run in matrix["runs"]], list(range(1, 9)))
        self.assertEqual(len({run["run_id"] for run in matrix["runs"]}), 8)
        record = read_json(self.output, "experiment.json")
        baselines = {case["case_id"]: case["repository_baseline"] for case in record["cases"]}
        for run in matrix["runs"]:
            self.assertEqual(run["repository_baseline"], baselines[run["case_id"]])

    def test_declared_ordering_keeps_the_declared_order(self) -> None:
        edit_json(self.root, EXPERIMENT, lambda v: v.update(ordering="declared"))
        self.assert_resolves()
        a, b = "codex-current", "codex-current-replica"
        self.assertEqual(self.cells(), [
            (1, "small-fix", a), (1, "small-fix", b), (1, "cross-file-change", a), (1, "cross-file-change", b),
            (2, "small-fix", a), (2, "small-fix", b), (2, "cross-file-change", a), (2, "cross-file-change", b),
        ])

    def test_balanced_ordering_rotates_three_configurations(self) -> None:
        third = read_json(self.root, REPLICA)
        third["configuration_id"] = "codex-third"
        write_json(self.root, "evals/configurations/codex-third.json", third)

        def change(value):
            value["cases"] = ["coding-core-dev/small-fix"]
            value["configurations"].append("codex-third")
            value["repetitions"] = 3
            value["budget"] = {"max_total_runs": 9, "max_elapsed_seconds": 5400}

        edit_json(self.root, EXPERIMENT, change)
        self.assert_resolves()
        a, b, c = "codex-current", "codex-current-replica", "codex-third"
        self.assertEqual([cell[2] for cell in self.cells()], [a, b, c, b, c, a, c, a, b])

    def test_run_ids_stay_unique_when_ids_contain_hyphens(self) -> None:
        # Joining these ids with hyphens would name (a, b-c) and (a-b, c) alike.
        for case_id in ("a", "a-b"):
            directory = self.root / "evals/cases/coding-core-dev" / case_id
            shutil.copytree(self.root / SMALL_FIX, directory)
            edit_json(self.root, f"evals/cases/coding-core-dev/{case_id}/case.json", lambda v, c=case_id: v.update(case_id=c))
        for configuration_id in ("b-c", "c"):
            value = read_json(self.root, CONFIGURATION)
            value["configuration_id"] = configuration_id
            write_json(self.root, f"evals/configurations/{configuration_id}.json", value)
        edit_json(self.root, EXPERIMENT, lambda v: v.update(
            cases=["coding-core-dev/a", "coding-core-dev/a-b"],
            configurations=["b-c", "c"],
            comparisons=[{"comparison_id": "hyphens", "baseline": "b-c", "candidate": "c"}],
        ))
        self.assert_resolves()
        runs = read_json(self.output, "matrix.json")["runs"]
        self.assertEqual(len(runs), 8)
        self.assertEqual(len({run["run_id"] for run in runs}), 8)
        self.assertEqual(len(set(self.cells())), 8)

    def test_budget_refusals_happen_before_any_write(self) -> None:
        original = (self.root / EXPERIMENT).read_bytes()
        for change, fragment in (
            (lambda v: v["budget"].update(max_total_runs=7), "exceeds the declared budget of 7 runs"),
            (lambda v: v["budget"].update(max_elapsed_seconds=5999), "worst-case elapsed time of 6000 seconds"),
            (
                lambda v: v.update(cases=["coding-core-dev/small-fix"], repetitions=7, budget={"max_total_runs": 100, "max_elapsed_seconds": 100000}),
                "needs 71 comparison input files",
            ),
        ):
            with self.subTest(fragment=fragment):
                edit_json(self.root, EXPERIMENT, change)
                self.assert_refused(fragment)
                (self.root / EXPERIMENT).write_bytes(original)

    def test_largest_matrix_that_fits_one_comparison_resolves(self) -> None:
        edit_json(self.root, EXPERIMENT, lambda v: v.update(
            cases=["coding-core-dev/small-fix"], repetitions=6,
            budget={"max_total_runs": 12, "max_elapsed_seconds": 7200},
        ))
        self.assert_resolves()
        matrix = read_json(self.output, "matrix.json")
        self.assertEqual(matrix["run_count"], 12)
        self.assertEqual(matrix["limits"]["comparison_input_files"], 61)
        self.assertLessEqual(61, comparison.MAX_INPUT_FILES)


# The child installs an audit hook before running the command, so every socket,
# process launch and file-system mutation the resolver performs is observed.
AUDIT_CHILD = r"""
import json, os, runpy, sys
command, log, *arguments = sys.argv[1:]
WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC
events = []
recording = True
def text(value):
    return os.fsdecode(value) if isinstance(value, (str, bytes, os.PathLike)) else repr(value)
def hook(event, args):
    if not recording:
        return
    if event.startswith("socket."):
        events.append(["socket", event])
    elif event == "subprocess.Popen":
        events.append(["popen", text(args[0]), [text(item) for item in args[1]]])
    elif event in ("os.exec", "os.posix_spawn", "os.spawn", "os.system", "os.fork", "os.forkpty"):
        events.append(["process", event])
    elif event == "open":
        path, mode, flags = args
        writes = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
            isinstance(flags, int) and flags & WRITE_FLAGS
        )
        if writes and not isinstance(path, int):
            events.append(["write", os.path.abspath(text(path))])
    elif event in ("os.mkdir", "os.remove", "os.rmdir", "os.rename", "os.replace", "os.symlink",
                   "os.link", "os.chmod", "os.truncate", "shutil.rmtree", "os.utime"):
        # A dir_fd-relative operation belongs to an enclosing shutil.rmtree,
        # whose own event records the absolute tree it removes.
        if event in ("os.remove", "os.rmdir") and args[1] not in (None, -1):
            return
        if event == "os.mkdir" and args[2] not in (None, -1):
            return
        for item in args[:2] if event in ("os.rename", "os.replace", "os.link", "os.symlink") else args[:1]:
            if not isinstance(item, int) and item is not None:
                events.append(["mutate", event, os.path.abspath(text(item))])
sys.addaudithook(hook)
sys.argv = [command, *arguments]
status = 0
try:
    runpy.run_path(command, run_name="__main__")
except SystemExit as exc:
    status = exc.code if isinstance(exc.code, int) else 1
recording = False
with open(log, "w", encoding="utf-8") as stream:
    json.dump({"status": status, "events": events}, stream)
"""


class NoExecutionBoundaryTest(ResolverFixture):
    def test_resolve_launches_no_model_opens_no_socket_and_writes_only_its_directory(self) -> None:
        sandbox = Path(self.temporary.name)
        for relative in TOOL_SOURCES:
            (self.root / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, self.root / relative)
        command = self.root / "scripts/agent-eval.py"
        home = sandbox / "home"
        home.mkdir()
        fake_bin = sandbox / "bin"
        fake_bin.mkdir()
        marker = sandbox / "model-launched"
        for name in ("codex", "opencode"):
            fake = fake_bin / name
            fake.write_text(f"#!/bin/sh\ntouch '{marker}'\n")
            fake.chmod(0o755)
        child = sandbox / "audit_child.py"
        child.write_text(AUDIT_CHILD)
        log = sandbox / "audit.json"
        before = snapshot(self.root)
        # Bytecode caching stays at the interpreter default, so the boundary
        # covers every file running the real command would write.
        env = {key: value for key, value in os.environ.items() if not key.startswith("PYTHON")}
        env.update(PATH=f"{fake_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}", HOME=str(home))
        result = subprocess.run(
            [sys.executable, str(child), str(command), str(log), "resolve", EXPERIMENT],
            capture_output=True, text=True, env=env, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        audit = json.loads(log.read_text())
        self.assertEqual(audit["status"], 0, result.stderr)
        events = audit["events"]

        self.assertEqual([event for event in events if event[0] in ("socket", "process")], [])
        launches = [event for event in events if event[0] == "popen"]
        self.assertTrue(launches)
        self.assertEqual({event[1] for event in launches}, {"git"})
        self.assertFalse(marker.exists())

        output = str(self.output)
        allowed_ancestors = {str(self.root / ".agent-artifacts"), str(self.output.parent)}
        for event in events:
            if event[0] in ("write", "mutate"):
                path = event[-1]
                with self.subTest(event=event):
                    self.assertTrue(
                        path == output or path.startswith(output + os.sep)
                        or (event[0] == "mutate" and event[1] == "os.mkdir" and path in allowed_ancestors),
                        path,
                    )

        self.assertEqual(snapshot(self.root, exclude=self.output), {
            **before,
            ".agent-artifacts": snapshot(self.root)[".agent-artifacts"],
            ".agent-artifacts/evaluations": snapshot(self.root)[".agent-artifacts/evaluations"],
        })
        self.assertEqual(sorted(os.listdir(self.output)), ["experiment.json", "matrix.json", "protocol.json"])
        self.assertEqual(os.listdir(home), [])


class DevelopmentSuiteTest(unittest.TestCase):
    def run_validation(self, directory: Path, commands) -> list[int]:
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        return [
            subprocess.run(command, cwd=directory, capture_output=True, env=env, timeout=120, check=False).returncode
            for command in commands
        ]

    def test_validation_fails_at_the_baseline_and_passes_with_a_reference_fix(self) -> None:
        for directory in (SMALL_FIX, CROSS_FILE):
            case = read_json(ROOT, f"{directory}/case.json")
            with self.subTest(case=case["case_id"]), tempfile.TemporaryDirectory() as temporary:
                checkout = Path(temporary)
                for path, data in definitions.read_fixture_tree(ROOT, f"{directory}/repository", "fixture"):
                    (checkout / path).parent.mkdir(parents=True, exist_ok=True)
                    (checkout / path).write_bytes(data)
                self.assertTrue(any(self.run_validation(checkout, case["validation_commands"])))
                fixes = REFERENCE_FIXES[case["case_id"]]
                self.assertLessEqual(set(fixes), set(case["allowed_write_paths"]))
                for path, text in fixes.items():
                    (checkout / path).write_text(text)
                self.assertEqual(set(self.run_validation(checkout, case["validation_commands"])), {0})

    def test_suite_is_synthetic_and_used_for_tuning(self) -> None:
        for directory in (SMALL_FIX, CROSS_FILE):
            case = read_json(ROOT, f"{directory}/case.json")
            self.assertEqual((case["fixture_kind"], case["holdout"]), ("synthetic", "used_for_tuning"))

    def test_replica_differs_only_in_configuration_id(self) -> None:
        current = read_json(ROOT, CONFIGURATION)
        replica = read_json(ROOT, REPLICA)
        self.assertEqual((current["model"], current["reasoning"]), ("gpt-5.6-terra", {"supported": True, "effort": "medium"}))
        self.assertNotEqual(current["configuration_id"], replica["configuration_id"])
        self.assertEqual(
            {key: value for key, value in current.items() if key != "configuration_id"},
            {key: value for key, value in replica.items() if key != "configuration_id"},
        )


def build_suite() -> unittest.TestSuite:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for case_class in (
        DefinitionShapeTest,
        BaselineTest,
        ResolveTest,
        NoExecutionBoundaryTest,
        DevelopmentSuiteTest,
    ):
        suite.addTests(loader.loadTestsFromTestCase(case_class))
    return suite


if __name__ == "__main__":
    if sys.argv[1:]:
        raise SystemExit(f"unsupported arguments: {sys.argv[1:]}")
    runner = unittest.TextTestRunner(verbosity=1)
    raise SystemExit(0 if runner.run(build_suite()).wasSuccessful() else 1)
