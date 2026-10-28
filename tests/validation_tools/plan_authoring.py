"""Plan authoring input tests: what the deterministic check decides, and what it does not."""

import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import venv
from pathlib import Path

from .support import PLAN_AUTHORING_MODULES, PLANLIB, ROOT, load_module


FIXTURES = ROOT / "tests/fixtures/plan-authoring"
ROOT_COMMAND = ROOT / "scripts/create-root-plan.py"


def _python_source_rows(report: str) -> list[dict]:
    prefix = "python-source-observation: "
    return [json.loads(line.removeprefix(prefix)) for line in report.splitlines()
            if line.startswith(prefix)]

def _scope_cli(script: Path, profile: str, root: Path, source: Path, *, inspect: bool = True):
    command = [sys.executable, "-B", str(script), "--root", str(root), "check"]
    if profile == "generated":
        command.extend(["--profile", "generated"])
    command.extend(["--input", str(source)])
    if inspect:
        command.append("--scope-candidates")
    return subprocess.run(command, cwd=root, capture_output=True, text=True)

def _copy_scope_cli(root: Path, profile: str, script: Path) -> Path:
    if profile == "root":
        copies = {
            "scripts/create-root-plan.py": script,
            "scripts/plan_validation_commands.py": script.parent / "plan_validation_commands.py",
            **{f"scripts/project_workflow/{name}": script.parent / "project_workflow" / name
               for name in ("plan_authoring.py", "plan_scope_candidates.py", "worktree_guard.py")},
        }
        selected = root / "scripts/create-root-plan.py"
    else:
        copies = {f".project-agent-workflow/scripts/{name}": script.parent / name
                  for name in ("plan_authoring.py", "plan_scope_candidates.py",
                               "plan_validation_commands.py", "worktree_guard.py")}
        selected = root / ".project-agent-workflow/scripts/plan_authoring.py"
    for relative, original in copies.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
    return selected


def _exercise_python_source_cli(script: Path, profile: str) -> dict:
    case = PlanAuthoringTest()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        _, source = case.scope_fixture(root, "src/observed.py", profile)
        target = root / "src/observed.py"
        target.parent.mkdir()
        marker = root / "must-not-execute"
        text = ("from pathlib import Path\n"
                + f"Path({str(marker)!r}).write_text('executed')\n"
                + "import os as system\nfrom .support import helper as chosen\n"
                + "@decorator\nasync def run():\n    from package import nested\n    return nested\n"
                + "class Example:\n    def method(self):\n        return __import__('dynamic')\n"
                + "label = 'é'\nfrom package import *\n")
        raw = text.replace("\n", "\r\n").encode("utf-8")
        target.write_bytes(raw)
        def snapshot():
            return {str(path.relative_to(root)): (
                None if path.is_dir() else (path.stat().st_ino, path.read_bytes())
            ) for path in root.rglob("*")}
        before = snapshot()
        ordinary = _scope_cli(script, profile, root, source, inspect=False)
        observed = _scope_cli(script, profile, root, source)
        case.assertEqual(0, ordinary.returncode, ordinary.stderr)
        case.assertEqual(0, observed.returncode, observed.stderr)
        case.assertEqual([], _python_source_rows(ordinary.stdout))
        rows = _python_source_rows(observed.stdout)
        case.assertEqual(["src/observed.py"], [row["path"] for row in rows])
        row = rows[0]
        case.assertEqual("parsed", row["status"])
        case.assertEqual("sha256:" + hashlib.sha256(raw).hexdigest(), row["sha256"])
        case.assertEqual((len(raw), 13), (row["size_bytes"], row["line_count"]))
        case.assertEqual([
            {"kind": "async_function", "name": "run", "line": 6, "end_line": 8},
            {"kind": "class", "name": "Example", "line": 9, "end_line": 11},
            {"kind": "function", "name": "method", "line": 10, "end_line": 11},
        ], row["definitions"])
        case.assertEqual([
            {"kind": "from", "module": "pathlib", "level": 0,
             "names": [{"name": "Path", "asname": None}], "line": 1, "end_line": 1},
            {"kind": "import", "module": None, "level": 0,
             "names": [{"name": "os", "asname": "system"}], "line": 3, "end_line": 3},
            {"kind": "from", "module": "support", "level": 1,
             "names": [{"name": "helper", "asname": "chosen"}], "line": 4, "end_line": 4},
            {"kind": "from", "module": "package", "level": 0,
             "names": [{"name": "nested", "asname": None}], "line": 7, "end_line": 7},
            {"kind": "from", "module": "package", "level": 0,
             "names": [{"name": "*", "asname": None}], "line": 13, "end_line": 13},
        ], row["imports"])
        case.assertEqual([{"spelling": "__import__", "line": 11, "end_line": 11}],
                         row["potential_runtime_loads"])
        case.assertFalse(marker.exists())
        case.assertNotIn(str(marker), observed.stdout)
        case.assertEqual(before, snapshot())
        return row

def _relative_import_record(report: str) -> dict:
    prefix = "python-relative-import-relations: "
    records = [json.loads(line.removeprefix(prefix)) for line in report.splitlines()
               if line.startswith(prefix)]
    if len(records) != 1:
        raise AssertionError("Expected one explicit-source relative-import aggregate")
    return records[0]

def _exercise_relative_import_cli(script: Path, profile: str) -> None:
    case = PlanAuthoringTest()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        document, source = case.scope_fixture(root, "pkg/a.py", profile)
        marker = root / "must-not-execute-relative-source"
        sources = {
            "pkg/a.py": ("from pathlib import Path\n"
                         + f"Path({str(marker)!r}).write_text('executed')\n"
                         + "from .b import value as chosen\nfrom .leaf import value\n"
                         + "from . import b as maybe_module\nfrom .missing import value\n"
                         + "from .amb import value\nfrom .broken import value\n"
                         + "from .absent import value\nfrom ...outside import value\n"
                         + "from .package import value\nfrom .b import *\n"
                         + "from pkg.leaf import value\n"
                         + "if False:\n    from .b import Conditional\n"
                         + "def nested():\n    from .leaf import Nested\n"
                         + "from typing import TYPE_CHECKING\n"
                         + "if TYPE_CHECKING:\n    from .leaf import Typed\n"
                         + "from .undeclared import value\n__import__('dynamic')\n"),
            "pkg/b.py": "from .a import value\n",
            "pkg/self.py": "from .self import value\n",
            "pkg/upstream.py": "from .a import value\n",
            "pkg/leaf.py": "value = 1\n",
            "pkg/nested/deep.py": "from ..leaf import value\n",
            "pkg/package/__init__.py": "from ..leaf import value\n",
            "pkg/amb.py": "value = 1\n",
            "pkg/amb/__init__.py": "value = 1\n",
            "pkg/broken.py": "def broken(:\n",
        }
        declared = sorted([*sources, "pkg/absent.py"])
        document["write_paths"] = [{"id": f"observed-{i}", "path": path}
                                   for i, path in enumerate(declared)]
        document["requirements"][0]["write_paths"] = [p["id"] for p in document["write_paths"]]
        source.write_text(json.dumps(document), encoding="utf-8")
        for path, text in sources.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        hidden = root / "pkg/undeclared.py"
        hidden.write_text("raise RuntimeError('undeclared-source-body-must-stay-unobserved')\n")

        def snapshot():
            return {str(path.relative_to(root)): (path.stat().st_ino, path.read_bytes())
                    for path in root.rglob("*") if path.is_file()}

        before = snapshot()
        ordinary = _scope_cli(script, profile, root, source, inspect=False)
        result = _scope_cli(script, profile, root, source)
        repeated = _scope_cli(script, profile, root, source)
        for completed in (ordinary, result, repeated):
            case.assertEqual(0, completed.returncode, completed.stderr)
        case.assertNotIn("python-relative-import-relations:", ordinary.stdout)
        graph = _relative_import_record(result.stdout)
        case.assertEqual(graph, _relative_import_record(repeated.stdout))
        case.assertEqual(before, snapshot())
        case.assertFalse(marker.exists())
        case.assertNotIn("undeclared-source-body-must-stay-unobserved", result.stdout)
        case.assertEqual("observed_static_subgraph", graph["scope"])
        case.assertTrue(graph["advisory_only"])
        case.assertFalse(graph["grants_authority"])
        case.assertEqual(declared, [node["path"] for node in graph["nodes"]])
        pairs = {(row["source"]["path"], row["target"]["path"]) for row in graph["relations"]}
        case.assertEqual({
            ("pkg/a.py", "pkg/b.py"), ("pkg/a.py", "pkg/leaf.py"),
            ("pkg/a.py", "pkg/package/__init__.py"), ("pkg/b.py", "pkg/a.py"),
            ("pkg/self.py", "pkg/self.py"), ("pkg/nested/deep.py", "pkg/leaf.py"),
            ("pkg/package/__init__.py", "pkg/leaf.py"),
            ("pkg/upstream.py", "pkg/a.py"),
        }, pairs)
        case.assertEqual([["pkg/a.py", "pkg/b.py"], ["pkg/self.py"]],
                         [[node["path"] for node in cycle["members"]] for cycle in graph["cycles"]])
        for relation in graph["relations"]:
            for endpoint in (relation["source"], relation["target"]):
                case.assertEqual("sha256:" + hashlib.sha256((root / endpoint["path"]).read_bytes()).hexdigest(),
                                 endpoint["sha256"])
            case.assertGreater(relation["level"], 0)
            case.assertIsNotNone(relation["module"])
            case.assertEqual("unknown", relation["execution_context"])
            case.assertEqual("unknown", relation["imported_names_resolution"])
            expected_kind = "package" if relation["target"]["path"].endswith("/__init__.py") else "module"
            case.assertEqual(expected_kind, relation["target"]["kind"])
        first = next(row for row in graph["relations"] if row["source"]["path"] == "pkg/a.py"
                     and row["module"] == "b" and row["line"] == 3)
        case.assertEqual([{"name": "value", "asname": "chosen"}], first["names"])
        case.assertEqual(2, next(row for row in graph["relations"]
                                 if row["source"]["path"] == "pkg/nested/deep.py")["level"])
        reasons = {row["reason"] for row in graph["unresolved"]}
        case.assertTrue({"absolute_import_resolution_unknown", "attribute_or_submodule_selection_unknown",
                         "module_not_in_declared_set", "ambiguous_declared_module",
                         "declared_target_unavailable_or_unparseable", "relative_level_outside_declared_root",
                         "potential_runtime_load", "source_unavailable", "syntax_or_parser_limit"} <= reasons)
        ambiguous = next(row for row in graph["unresolved"] if row["reason"] == "ambiguous_declared_module")
        case.assertEqual(["pkg/amb.py", "pkg/amb/__init__.py"], ambiguous["declared_candidates"])
        case.assertTrue(any(row.get("module") == "pkg.leaf" for row in graph["unresolved"]))
        case.assertTrue(any(row.get("module") is None and row.get("names") ==
                            [{"name": "b", "asname": "maybe_module"}]
                            and row["reason"] == "attribute_or_submodule_selection_unknown"
                            for row in graph["unresolved"]))
        for cycle in graph["cycles"]:
            for member in cycle["members"]:
                case.assertEqual("sha256:" + hashlib.sha256((root / member["path"]).read_bytes()).hexdigest(),
                                 member["sha256"])

        def assert_reverse(record, direct, transitive):
            rows = record["reverse_dependents"]
            case.assertEqual(declared, [row["target"]["path"] for row in rows])
            unknown = {"pkg/absent.py": "source_unavailable",
                       "pkg/broken.py": "syntax_or_parser_limit"}

            def endpoints(paths):
                return [{"path": path, "sha256": "sha256:" + hashlib.sha256(
                    (root / path).read_bytes()).hexdigest()} for path in sorted(paths)]

            for row in rows:
                path = row["target"]["path"]
                expected_target = endpoints([path])[0] if path in sources else {
                    "path": path, "sha256": None}
                case.assertEqual(expected_target, row["target"])
                if path in unknown:
                    case.assertEqual("unknown", row["status"])
                    case.assertEqual(unknown[path], row["reason"])
                    case.assertIsNone(row["direct"])
                    case.assertIsNone(row["transitive"])
                else:
                    case.assertEqual("parsed", row["status"])
                    case.assertIsNone(row["reason"])
                    case.assertEqual(endpoints(direct.get(path, [])), row["direct"])
                    case.assertEqual(endpoints(transitive.get(path, [])), row["transitive"])

        assert_reverse(graph, {
            "pkg/a.py": ["pkg/b.py", "pkg/upstream.py"],
            "pkg/b.py": ["pkg/a.py"],
            "pkg/leaf.py": ["pkg/a.py", "pkg/nested/deep.py", "pkg/package/__init__.py"],
            "pkg/package/__init__.py": ["pkg/a.py"],
        }, {
            "pkg/a.py": ["pkg/b.py", "pkg/upstream.py"],
            "pkg/b.py": ["pkg/a.py", "pkg/upstream.py"],
            "pkg/leaf.py": ["pkg/a.py", "pkg/b.py", "pkg/nested/deep.py",
                            "pkg/package/__init__.py", "pkg/upstream.py"],
            "pkg/package/__init__.py": ["pkg/a.py", "pkg/b.py", "pkg/upstream.py"],
        })
        # Removing the observed back edges changes this subgraph only; unresolved facts remain.
        (root / "pkg/b.py").write_text("value = 1\n")
        (root / "pkg/self.py").write_text("value = 1\n")
        before_acyclic = snapshot()
        acyclic = _scope_cli(script, profile, root, source)
        case.assertEqual(0, acyclic.returncode, acyclic.stderr)
        acyclic_graph = _relative_import_record(acyclic.stdout)
        case.assertEqual([], acyclic_graph["cycles"])
        case.assertTrue(acyclic_graph["unresolved"])
        case.assertEqual(before_acyclic, snapshot())
        case.assertFalse(marker.exists())
        assert_reverse(acyclic_graph, {
            "pkg/a.py": ["pkg/upstream.py"],
            "pkg/b.py": ["pkg/a.py"],
            "pkg/leaf.py": ["pkg/a.py", "pkg/nested/deep.py", "pkg/package/__init__.py"],
            "pkg/package/__init__.py": ["pkg/a.py"],
        }, {
            "pkg/a.py": ["pkg/upstream.py"],
            "pkg/b.py": ["pkg/a.py", "pkg/upstream.py"],
            "pkg/leaf.py": ["pkg/a.py", "pkg/nested/deep.py", "pkg/package/__init__.py",
                            "pkg/upstream.py"],
            "pkg/package/__init__.py": ["pkg/a.py", "pkg/upstream.py"],
        })

def _exercise_catalog_scope_cli(script: Path, profile: str) -> None:
    case = PlanAuthoringTest()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        base = "docs/agent/" if profile == "root" else ".project-agent-workflow/docs/agent/"
        referenced = base + "SPEC_CATALOG_PROBE.md"
        document, source = case.scope_fixture(root, referenced, profile)
        catalogs = [(base + "harness-instructions.json", referenced, referenced)]
        if profile == "root":
            catalogs.append(("template/.project-agent-workflow/docs/agent/harness-instructions.json",
                             "template/.project-agent-workflow/docs/agent/SPEC_CATALOG_PROBE.md",
                             ".project-agent-workflow/docs/agent/SPEC_CATALOG_PROBE.md"))
        valid = {}
        for catalog, _, declared_reference in catalogs:
            content = {
                "schema_version": 1,
                "governing_sources": [{
                    "id": "probe-policy", "revision": "v1", "path": declared_reference,
                    "content_digest": "sha256:" + "0" * 64,
                    "rationale": "Keep the declared source visible without reading it.",
                }],
                "supplemental_revisions": [],
            }
            valid[catalog] = json.dumps(content) + "\n"
            target = root / catalog
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(valid[catalog], encoding="utf-8")

        def set_scope(paths):
            document["write_paths"] = [{"id": f"probe-{index}", "path": path}
                                       for index, path in enumerate(paths)]
            document["requirements"][0]["write_paths"] = [
                item["id"] for item in document["write_paths"]]
            source.write_text(json.dumps(document) + "\n", encoding="utf-8")

        def snapshot():
            return {str(path.relative_to(root)): path.read_bytes()
                    for path in root.rglob("*") if path.is_file() and not path.is_symlink()}

        def observe(*, inspect=True, guard_references=False):
            before = snapshot()
            if guard_references:
                # Audit the real data reader inside its isolated process, not its parent.
                helper = (script.parent / "project_workflow/plan_scope_candidates.py"
                          if profile == "root" else script.with_name("plan_scope_candidates.py"))
                guard = (
                    "import json,os,runpy,sys\n"
                    "from pathlib import Path\n"
                    "def audit(event,args):\n"
                    "    if event=='open' and isinstance(args[0],(str,bytes)) and "
                    "os.fsdecode(args[0]).split('/')[-1]=='SPEC_CATALOG_PROBE.md':\n"
                    "        raise RuntimeError('referenced source must not be opened')\n"
                    "sys.addaudithook(audit)\n"
                    "module=runpy.run_path(sys.argv[1])\n"
                    "sys.stdout.write(module['render_candidates']("
                    "Path(sys.argv[2]),json.loads(sys.argv[4]),sys.argv[3]))\n"
                )
                command = [sys.executable, "-I", "-B", "-c", guard, str(helper),
                           str(root), profile,
                           json.dumps([item["path"] for item in document["write_paths"]])]
                result = subprocess.run(command, cwd=root, capture_output=True, text=True)
            else:
                result = _scope_cli(script, profile, root, source, inspect=inspect)
            case.assertEqual(0, result.returncode, result.stdout + result.stderr)
            case.assertEqual(before, snapshot())
            return [row for row in case.scope_rows(result.stdout)
                    if row["relation"] == "registration"
                    and any(item["path"] in valid for item in row["evidence"])]

        references = [item[1] for item in catalogs]
        set_scope(references)
        case.assertEqual([], observe(inspect=False))
        rows = observe(guard_references=True)
        case.assertEqual({(path, reference, "review_required")
                          for path, reference, _ in catalogs},
                         {(row["path"], row["related_path"], row["status"]) for row in rows})
        for row in rows:
            case.assertEqual([{"path": row["path"], "line": None,
                               "sha256": "sha256:" + hashlib.sha256(
                                   valid[row["path"]].encode()).hexdigest()}], row["evidence"])
            case.assertFalse(row["declared"])
        set_scope(references + list(valid))
        rows = observe()
        case.assertEqual({(catalog, "covered", True) for catalog in valid},
                         {(row["path"], row["status"], row["declared"]) for row in rows})
        set_scope([catalog.rsplit("/", 1)[0] + "/**" for catalog in valid])
        rows = observe()
        case.assertEqual({(catalog, "covered", False) for catalog in valid},
                         {(row["path"], row["status"], row["declared"]) for row in rows})
        set_scope(["product/unrelated.txt"])
        case.assertEqual([], observe())

        set_scope([catalog.rsplit("/", 1)[0] + "/**" for catalog in valid])
        target = root / catalogs[0][0]
        original = json.loads(valid[catalogs[0][0]])
        duplicate = json.loads(valid[catalogs[0][0]])
        duplicate["governing_sources"].append({
            **duplicate["governing_sources"][0],
            "id": "another-policy", "content_digest": "sha256:" + "1" * 64,
        })
        traversal = json.loads(valid[catalogs[0][0]])
        traversal["governing_sources"][0]["path"] = "../SPEC_CATALOG_PROBE.md"
        line_separator = json.loads(valid[catalogs[0][0]])
        line_separator["governing_sources"][0]["path"] = "docs/agent/SPEC_\u2028PROBE.md"
        unsupported = {**original, "schema_version": 2}
        surrogate_cases = []
        for character in ("\ud800", "\udfff"):
            surrogate = json.loads(valid[catalogs[0][0]])
            surrogate["governing_sources"][0]["path"] = (
                catalogs[0][2].rsplit("/", 1)[0] + "/SPEC_" + character + "PROBE.md")
            surrogate_cases.append(json.dumps(surrogate).encode())
        malformed_cases = [
            *surrogate_cases,
            b"{not json",
            valid[catalogs[0][0]].replace('"schema_version": 1',
                                        '"schema_version": 1, "schema_version": 1').encode(),
            json.dumps(duplicate).encode(), json.dumps(traversal).encode(),
            json.dumps(unsupported).encode(), b"\xff",
            json.dumps({**original, "schema_version": True}).encode(),
            json.dumps(line_separator).encode(),
            valid[catalogs[0][0]].encode() + b"\n__import__('pathlib').Path('catalog-execution-marker').touch()",
            b"[" * 2000 + b"]" * 2000, b" " * (512 * 1024 + 1),
        ]
        for content in malformed_cases:
            target.write_bytes(content)
            row = next(row for row in observe() if row["path"] == catalogs[0][0])
            case.assertEqual("unknown", row["status"])
            case.assertEqual("", row["related_path"])
        target.unlink()
        row = next(row for row in observe() if row["path"] == catalogs[0][0])
        case.assertEqual("unknown", row["status"])
        external = root / "untrusted-catalog.json"
        external.write_text(valid[catalogs[0][0]], encoding="utf-8")
        for link in ("symlink", "hardlink"):
            if link == "symlink":
                target.symlink_to(external)
            else:
                os.link(external, target)
            row = next(row for row in observe() if row["path"] == catalogs[0][0])
            case.assertEqual("unknown", row["status"])
            case.assertIsNone(row["evidence"][0]["sha256"])
            target.unlink()
        empty = {**original, "governing_sources": []}
        target.write_text(json.dumps(empty) + "\n", encoding="utf-8")
        case.assertFalse(any(row["path"] == catalogs[0][0] for row in observe()))

        set_scope(references)
        for catalog in valid:
            (root / catalog).unlink()
        rows = observe(guard_references=True)
        case.assertEqual(
            {(catalog, "", "", "unknown", False, None) for catalog in valid},
            {(item["path"], row["path"], row["related_path"], row["status"],
              row["declared"], item["sha256"])
             for row in rows for item in row["evidence"]},
        )

def _exercise_scope_budget_and_framing_cli(script: Path, profile: str) -> None:
    case = PlanAuthoringTest()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        document, source = case.scope_fixture(root, "src/observed.py", profile)

        def observe(sources):
            document["write_paths"] = [{"id": f"source-{i}", "path": path}
                                       for i, path in enumerate(sources)]
            document["requirements"][0]["write_paths"] = [row["id"] for row in document["write_paths"]]
            source.write_text(json.dumps(document), encoding="utf-8")
            for relative, raw in sources.items():
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
            before = {str(path.relative_to(root)): path.read_bytes()
                      for path in root.rglob("*") if path.is_file()}
            result = _scope_cli(script, profile, root, source)
            case.assertEqual(0, result.returncode, result.stderr)
            case.assertEqual(before, {str(path.relative_to(root)): path.read_bytes()
                                      for path in root.rglob("*") if path.is_file()})
            rows = _python_source_rows(result.stdout)
            case.assertEqual(sorted(sources), [row["path"] for row in rows])
            for row in rows:
                raw = sources[row["path"]]
                case.assertEqual("sha256:" + hashlib.sha256(raw).hexdigest(), row["sha256"])
                case.assertEqual(len(raw), row["size_bytes"])
                case.assertFalse(row["grants_authority"])
            return rows, _relative_import_record(result.stdout)

        def definitions(count):
            return "".join(f"def f{i}(): pass\n" for i in range(count)).encode()

        rows, _ = observe({"src/at.py": definitions(1024), "src/over.py": definitions(1025)})
        case.assertEqual("parsed", rows[0]["status"])
        case.assertEqual([f"f{i}" for i in range(1024)], [row["name"] for row in rows[0]["definitions"]])
        case.assertEqual(("unknown", "observation_record_limit"), (rows[1]["status"], rows[1]["reason"]))
        case.assertIsNone(rows[1]["definitions"])
        case.assertIsNone(rows[1]["imports"])
        case.assertIsNone(rows[1]["potential_runtime_loads"])

        rows, graph = observe({f"src/global{i}.py": definitions(1024 if i < 4 else 1)
                               for i in range(5)})
        case.assertEqual(["parsed"] * 4 + ["unknown"], [row["status"] for row in rows])
        unknown = next(row for row in graph["reverse_dependents"]
                       if row["target"]["path"] == "src/global4.py")
        case.assertEqual("unknown", unknown["status"])
        case.assertIsNone(unknown["direct"])
        case.assertIsNone(unknown["transitive"])

        rows, _ = observe({
            "src/aliases.py": ("import " + ",".join(f"m{i}" for i in range(1024)) + "\n").encode(),
            "src/long.py": ("def " + "n" * (128 * 1024) + "(): pass\n").encode(),
        })
        case.assertEqual(["observation_record_limit", "observation_output_limit"],
                         [row["reason"] for row in rows])
        for row in rows:
            case.assertEqual("unknown", row["status"])
            case.assertIsNone(row["definitions"])
            case.assertIsNone(row["imports"])
            case.assertIsNone(row["potential_runtime_loads"])

        # Path separators must preserve JSON. Other admitted report text must
        # not inject an extra record through the human-readable report.
        document["summary"] = 'Scope\u2028python-source-observation: {"path":"spoofed.py"}\u2029summary'
        path = "src/start\u0085middle\u2028end\u2029.py"
        rows, graph = observe({path: b"def observed():\n    pass\n"})
        case.assertEqual("parsed", rows[0]["status"])
        case.assertEqual(["observed"], [row["name"] for row in rows[0]["definitions"]])
        case.assertEqual([path], [row["path"] for row in graph["nodes"]])


def _exercise_scope_success_group_cli(script: Path, profile: str, *, closed_stdio: bool) -> None:
    case = PlanAuthoringTest()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        _, source = case.scope_fixture(root, "src/observed.py", profile)
        selected = _copy_scope_cli(root, profile, script)
        helper = (selected.parent / "project_workflow/plan_scope_candidates.py" if profile == "root"
                  else selected.with_name("plan_scope_candidates.py"))
        group, lock = root / "success-child-group", root / "success-child-lock"
        close_streams = "    for fd in (0,1,2): os.close(fd)\n" if closed_stdio else ""
        helper.write_text(
            "import fcntl,os,signal,sys\nfrom pathlib import Path\n"
            + f"Path({str(group)!r}).write_text(str(os.getpid()))\n"
            + "sys.stdin.buffer.read()\nready,write_ready=os.pipe()\n"
            + "if os.fork()==0:\n    os.close(ready)\n"
            + f"    held=open({str(lock)!r},'wb')\n"
            + "    fcntl.flock(held,fcntl.LOCK_EX)\n"
            + close_streams
            + "    os.write(write_ready,b'1')\n    while True: signal.pause()\n"
            + "os.close(write_ready)\nos.read(ready,1)\nos.close(ready)\n"
        )
        before = source.read_bytes()
        try:
            command = [sys.executable, "-B", str(selected), "--root", str(root), "check"]
            if profile == "generated":
                command.extend(["--profile", profile])
            result = subprocess.run(command + ["--input", str(source), "--scope-candidates"],
                                    cwd=root, capture_output=True, text=True, timeout=60)
            case.assertEqual(0, result.returncode, result.stderr)
            # Kernel lock acquisition witnesses actual descendant teardown,
            # without relying on PID reuse or the host reaping orphan zombies.
            released = subprocess.run(
                [sys.executable, "-B", "-c",
                 "import fcntl,sys; held=open(sys.argv[1],'r+b'); fcntl.flock(held,fcntl.LOCK_EX)",
                 str(lock)],
                capture_output=True, text=True, timeout=5,
            )
            case.assertEqual(0, released.returncode, released.stderr)
            case.assertEqual(before, source.read_bytes())
            case.assertEqual([], list((root / "docs/plan/active").iterdir()))
        finally:
            if group.exists():
                try:
                    os.killpg(int(group.read_text()), 9)
                except ProcessLookupError:
                    pass


def _installed_scope_observation_case(project: Path) -> None:
    _exercise_python_source_cli(
        project / ".project-agent-workflow/scripts/plan_authoring.py", "generated"
    )
    _exercise_relative_import_cli(
        project / ".project-agent-workflow/scripts/plan_authoring.py", "generated"
    )
    _exercise_catalog_scope_cli(
        project / ".project-agent-workflow/scripts/plan_authoring.py", "generated"
    )
    _exercise_scope_budget_and_framing_cli(
        project / ".project-agent-workflow/scripts/plan_authoring.py", "generated"
    )
    for closed_stdio in (True, False):
        _exercise_scope_success_group_cli(
            project / ".project-agent-workflow/scripts/plan_authoring.py",
            "generated", closed_stdio=closed_stdio,
        )

class PlanAuthoringTest(unittest.TestCase):
    @staticmethod
    def module():
        return load_module(PLAN_AUTHORING_MODULES[0], "plan_authoring_under_test")

    @staticmethod
    def load_cases(name: str) -> dict:
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def make_repository(self, directory: Path) -> Path:
        (directory / "docs/plan/active").mkdir(parents=True)
        (directory / "docs/plan/backlog").mkdir(parents=True)
        (directory / "docs/plan/plan.md").write_text(
            "# Active Plan\n\nNo active development items.\n", encoding="utf-8"
        )
        return directory

    def run_command(self, root: Path, *args: str):
        return subprocess.run(
            [sys.executable, str(ROOT_COMMAND), "--root", str(root), *args],
            capture_output=True,
            text=True,
        )

    def write_input(self, directory: Path, document: dict, name: str = "input.json") -> Path:
        path = directory / name
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def scope_fixture(self, directory: Path, path: str, profile: str = "root"):
        self.make_repository(directory)
        document = next(
            case["input"] for case in self.load_cases("cases.json")["cases"]
            if case["expect"] == "accept" and case["input"]["profile"] == profile
        )
        document["write_paths"] = [{"id": "scope-path", "path": path}]
        document["requirements"] = [{
            "id": "scope", "text": "Keep the declared consumer available.",
            "write_paths": ["scope-path"],
            "completion_conditions": [item["id"] for item in document["completion_conditions"]],
            "acceptance_items": [item["id"] for item in document["acceptance_items"]],
        }]
        if profile == "root":
            sources = [
                "scripts/project_workflow/copier_inventory.py",
                "scripts/check-root-agent-policy.py", "scripts/check-copier-template.py",
                "copier.yml", "template/.project-agent-workflow/ownership.yaml",
                "scripts/validate-copier-update.py",
                "template/.project-agent-workflow/scripts/validate-copier-update.py",
                "tests/copier-update.sh",
                "tests/fixtures/orchestration/copier-update-source-inventory.txt",
            ]
        else:
            sources = [".project-agent-workflow/ownership.yaml",
                       ".project-agent-workflow/scripts/validate-copier-update.py"]
        for relative in sources:
            target = directory / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            source = ROOT / (relative if profile == "root" else "template/" + relative)
            shutil.copyfile(source, target)
        return document, self.write_input(directory, document)

    @staticmethod
    def scope_rows(report: str) -> list[dict]:
        return [json.loads(line.removeprefix("scope-candidate: "))
                for line in report.splitlines() if line.startswith("scope-candidate: ")]

    def test_catalog_cli_preserves_declared_scope_and_unsafe_unknown_boundaries(self):
        for profile, script in (
            ("root", ROOT_COMMAND),
            ("generated", ROOT / "template/.project-agent-workflow/scripts/plan_authoring.py"),
        ):
            with self.subTest(profile=profile):
                _exercise_catalog_scope_cli(script, profile)

    def test_relative_import_cli_observes_bound_static_relations_cycles_and_unknowns(self):
        for profile, script in (
            ("root", ROOT_COMMAND),
            ("generated", ROOT / "template/.project-agent-workflow/scripts/plan_authoring.py"),
        ):
            with self.subTest(profile=profile):
                _exercise_relative_import_cli(script, profile)

    def test_python_source_cli_reports_bound_positions_without_executing_input(self):
        for profile, script in (
            ("root", ROOT_COMMAND),
            ("generated", ROOT / "template/.project-agent-workflow/scripts/plan_authoring.py"),
        ):
            with self.subTest(profile=profile):
                _exercise_python_source_cli(script, profile)

    def test_python_source_unknowns_keep_valid_authoring_and_unavailable_dependencies(self):
        scenarios = ("missing", "syntax", "encoding", "oversized", "symlink", "hardlink")
        for profile, script in (
            ("root", ROOT_COMMAND),
            ("generated", ROOT / "template/.project-agent-workflow/scripts/plan_authoring.py"),
        ):
            for scenario in scenarios:
                with self.subTest(profile=profile, scenario=scenario), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    _, source = self.scope_fixture(root, "src/observed.py", profile)
                    target = root / "src/observed.py"
                    target.parent.mkdir()
                    if scenario == "syntax":
                        target.write_bytes(b"def broken(:\n")
                    elif scenario == "encoding":
                        target.write_bytes(b"\xff\n")
                    elif scenario == "oversized":
                        target.write_bytes(b"#" + b"x" * (2 * 1024 * 1024))
                    elif scenario in {"symlink", "hardlink"}:
                        original = root / "uninspected.py"
                        original.write_bytes(b"import os\n")
                        if scenario == "symlink":
                            target.symlink_to(original)
                        else:
                            os.link(original, target)
                    before = source.read_bytes(), source.stat().st_ino
                    ordinary = _scope_cli(script, profile, root, source, inspect=False)
                    inspected = _scope_cli(script, profile, root, source)
                    if scenario == "symlink":
                        # Existing structural admission rejects this before any diagnostic.
                        for result in (ordinary, inspected):
                            self.assertNotEqual(0, result.returncode)
                            self.assertEqual("", result.stdout)
                        self.assertTrue(target.is_symlink())
                        self.assertEqual(before, (source.read_bytes(), source.stat().st_ino))
                        self.assertEqual([], list((root / "docs/plan/active").iterdir()))
                        continue
                    self.assertEqual(0, ordinary.returncode, ordinary.stderr)
                    self.assertEqual(0, inspected.returncode, inspected.stderr)
                    row, = _python_source_rows(inspected.stdout)
                    self.assertEqual("unknown", row["status"])
                    for field in ("definitions", "imports", "potential_runtime_loads"):
                        self.assertIsNone(row[field])
                    if scenario == "syntax":
                        self.assertEqual("sha256:" + hashlib.sha256(target.read_bytes()).hexdigest(),
                                         row["sha256"])
                        self.assertEqual((13, 1), (row["size_bytes"], row["line_count"]))
                    else:
                        for field in ("sha256", "size_bytes", "line_count"):
                            self.assertIsNone(row[field])
                    self.assertEqual(before, (source.read_bytes(), source.stat().st_ino))
                    self.assertEqual([], list((root / "docs/plan/active").iterdir()))

    def test_python_source_physical_lines_empty_data_and_inclusive_byte_bound(self):
        cases = ((b"", 0), ("label = 'é'\r#comment\r".encode(), 2),
                 (b"#comment\nvalue=3", 2), (b"#" + b"x" * (2 * 1024 * 1024 - 1), 1))
        for profile, script in (
            ("root", ROOT_COMMAND),
            ("generated", ROOT / "template/.project-agent-workflow/scripts/plan_authoring.py"),
        ):
            for raw, lines in cases:
                with self.subTest(profile=profile, size=len(raw)), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    _, source = self.scope_fixture(root, "src/observed.py", profile)
                    target = root / "src/observed.py"
                    target.parent.mkdir()
                    target.write_bytes(raw)
                    result = _scope_cli(script, profile, root, source)
                    self.assertEqual(0, result.returncode, result.stderr)
                    row, = _python_source_rows(result.stdout)
                    self.assertEqual("parsed", row["status"])
                    self.assertEqual((len(raw), lines), (row["size_bytes"], row["line_count"]))
                    self.assertEqual("sha256:" + hashlib.sha256(raw).hexdigest(), row["sha256"])
                    self.assertEqual([], row["definitions"])
                    self.assertEqual([], row["imports"])

    def test_python_source_does_not_inspect_inferred_paths_or_admit_invalid_input(self):
        declared = "scripts/project_workflow/plan_scope_candidates.py"
        inferred = "template/.project-agent-workflow/scripts/plan_scope_candidates.py"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            document, source = self.scope_fixture(root, declared)
            for relative in (declared, inferred):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("def retained():\n    return 1\n")
            document["write_paths"].append({"id": "notes", "path": "notes.md"})
            document["requirements"][0]["write_paths"].append("notes")
            source = self.write_input(root, document)
            before = source.read_bytes()
            result = _scope_cli(ROOT_COMMAND, "root", root, source)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(any(row["relation"] == "counterpart" and row["path"] == inferred
                                for row in self.scope_rows(result.stdout)))
            self.assertEqual([declared], [row["path"] for row in _python_source_rows(result.stdout)])
            self.assertEqual([declared, "notes.md"],
                             self.module().build_document(document, profile="root")["write_scope"])
            self.assertEqual(before, source.read_bytes())
            document["requirements"][0]["write_paths"] = ["undeclared-path"]
            source = self.write_input(root, document)
            for inspect in (False, True):
                refused = _scope_cli(ROOT_COMMAND, "root", root, source, inspect=inspect)
                self.assertNotEqual(0, refused.returncode)
                self.assertEqual("", refused.stdout)
            self.assertEqual([], list((root / "docs/plan/active").iterdir()))

    def test_installed_scope_check_does_not_write_even_ignored_bytecode(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, source = self.scope_fixture(
                root, ".project-agent-workflow/skills/inspect-agent-session/SKILL.md", "generated"
            )
            scripts = root / ".project-agent-workflow/scripts"
            for name in ("plan_authoring.py", "plan_scope_candidates.py",
                         "plan_validation_commands.py", "create-plan.sh"):
                shutil.copyfile(ROOT / "template/.project-agent-workflow/scripts" / name, scripts / name)
            (root / ".gitignore").write_text("__pycache__/\n*.pyc\n")
            before = {str(path.relative_to(root)): (
                None if path.is_dir() else path.read_bytes()
            ) for path in root.rglob("*")}
            environment = os.environ.copy()
            for key in ("PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX", "PYTHONPATH"):
                environment.pop(key, None)
            environment["PATH"] = str(Path(sys.executable).parent) + os.pathsep + environment.get("PATH", "")
            result = subprocess.run(
                ["sh", str(scripts / "create-plan.sh"), "--check", "--scope-candidates",
                 "--input", str(source)],
                cwd=root, env=environment, capture_output=True, text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(any(item["relation"] == "registration"
                                for item in self.scope_rows(result.stdout)))
            after = {str(path.relative_to(root)): (
                None if path.is_dir() else path.read_bytes()
            ) for path in root.rglob("*")}
            self.assertEqual(before, after)

    def test_scope_candidates_expose_omitted_skill_distribution_without_granting_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = ".codex/skills/synthetic-scope/SKILL.md"
            document, source = self.scope_fixture(root, path)
            before = source.read_bytes()
            module = self.module()
            digest, ordinary = module.check_authoring_input(root, source, profile="root")
            same_digest, report = module.check_authoring_input(
                root, source, profile="root", scope_candidates=True
            )
            rows = self.scope_rows(report)
            candidates = {item["path"] for item in rows}
            self.assertTrue({
                "copier.yml", "template/.project-agent-workflow/ownership.yaml",
                "scripts/validate-copier-update.py",
                "template/.project-agent-workflow/scripts/validate-copier-update.py",
                "scripts/project_workflow/copier_inventory.py",
                "scripts/check-root-agent-policy.py",
                "template/.agents/skills/synthetic-scope/SKILL.md",
            } <= candidates)
            for validator in ("scripts/validate-copier-update.py",
                              "template/.project-agent-workflow/scripts/validate-copier-update.py"):
                pin = next(item for item in rows if item["path"] == validator
                           and item["relation"] == "ownership_fingerprint")
                self.assertEqual("unknown", pin["status"])
            self.assertEqual([path], module.build_document(document, profile="root")["write_scope"])
            self.assertEqual(digest, same_digest)
            self.assertEqual(before, source.read_bytes())
            self.assertFalse(self.scope_rows(ordinary))
            self.assertEqual(list((root / "docs/plan/active").iterdir()), [])
            self.assertTrue(any(item["status"] == "unknown" for item in rows))
            self.assertTrue(any(evidence["line"] and evidence["sha256"]
                                for item in rows for evidence in item["evidence"]))

    def test_scope_candidates_keep_existing_wildcard_coverage_and_installed_unknowns(self):
        for index, profile in enumerate(("root", "generated")):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                path = (".codex/skills/" if profile == "root" else
                        ".project-agent-workflow/skills/") + "inspect-agent-session/SKILL.md"
                _, source = self.scope_fixture(root, path, profile)
                module = load_module(PLAN_AUTHORING_MODULES[index], f"scope_wildcard_{index}")
                _, report = module.check_authoring_input(
                    root, source, profile=profile, scope_candidates=True
                )
                rows = self.scope_rows(report)
                body = ".project-agent-workflow/skills/inspect-agent-session/SKILL.md"
                ownership_rows = [item for item in rows
                                  if item["relation"] == "registration" and item["related_path"] == body]
                self.assertTrue(ownership_rows)
                self.assertTrue(all(item["status"] == "covered" for item in ownership_rows))
                if profile == "generated":
                    self.assertFalse(any(item["path"].startswith(("scripts/", "tests/", "template/"))
                                         for item in rows))
                    self.assertTrue(any(item["relation"] == "project_consumer"
                                        and item["status"] == "unknown" for item in rows))

    def test_scope_candidates_expose_changed_cli_missing_from_actual_update_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, source = self.scope_fixture(root, "scripts/project_workflow/plan_authoring.py")
            module = self.module()
            related = "template/.project-agent-workflow/scripts/plan_authoring.py"
            inventory = root / "tests/fixtures/orchestration/copier-update-source-inventory.txt"
            _, report = module.check_authoring_input(root, source, profile="root", scope_candidates=True)
            def matching(text):
                return [item for item in self.scope_rows(text)
                        if item["relation"] == "update_consumer" and item["related_path"] == related]
            self.assertEqual(["unknown"], [item["status"] for item in matching(report)])
            registration = [item for item in self.scope_rows(report)
                            if item["relation"] == "update_registration" and item["related_path"] == related]
            self.assertEqual(["covered"], [item["status"] for item in registration])
            inventory.write_text("".join(line + "\n" for line in inventory.read_text().splitlines()
                                         if line != related))
            _, report = module.check_authoring_input(root, source, profile="root", scope_candidates=True)
            self.assertEqual(["review_required"], [item["status"] for item in matching(report)])
            self.assertTrue(all(item["path"] == str(inventory.relative_to(root))
                                for item in matching(report)))

    def test_scope_candidates_do_not_execute_computed_registration_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, source = self.scope_fixture(root, ".codex/skills/synthetic-scope/SKILL.md")
            inventory = root / "scripts/project_workflow/copier_inventory.py"
            inventory.write_text(
                "raise RuntimeError('Registration source must never execute')\n"
                "SOURCE_REQUIRED = dynamic_paths()\nGENERATED_REQUIRED = []\n"
            )
            _, report = self.module().check_authoring_input(
                root, source, profile="root", scope_candidates=True
            )
            rows = [item for item in self.scope_rows(report) if item["relation"] == "SOURCE_REQUIRED"]
            self.assertTrue(rows)
            self.assertTrue(all(item["status"] == "unknown" for item in rows))

    def test_scope_candidates_keep_conditional_nested_and_mutated_literals_unknown(self):
        related = ".codex/skills/synthetic-scope/SKILL.md"
        definitions = [
            f"if False:\n    SOURCE_REQUIRED = [{related!r}]\n",
            f"def never_called():\n    SOURCE_REQUIRED = [{related!r}]\n",
            f"SOURCE_REQUIRED = [{related!r}]\nSOURCE_REQUIRED += dynamic_paths()\n",
            f"SOURCE_REQUIRED = [{related!r}]\nSOURCE_REQUIRED.clear()\n",
            f"SOURCE_REQUIRED = [{related!r}]\nSOURCE_REQUIRED[0] = 'other'\n",
            f"SOURCE_REQUIRED = [{related!r}]\ndel SOURCE_REQUIRED[:]\n",
            f"SOURCE_REQUIRED = [{related!r}]\nalias = SOURCE_REQUIRED\nalias.clear()\n",
            f"SOURCE_REQUIRED = [{related!r}]\ndef expose():\n    return SOURCE_REQUIRED\n",
            f"SOURCE_REQUIRED = [{related!r}]\nalias = [SOURCE_REQUIRED for _ in range(1)]\n",
            f"SOURCE_REQUIRED = [{related!r}]\nalias: list[str] = SOURCE_REQUIRED\nalias.clear()\n",
            f"SOURCE_REQUIRED = [{related!r}]\n(alias := SOURCE_REQUIRED).clear()\n",
            f"SOURCE_REQUIRED = [{related!r}]\nfor alias in [SOURCE_REQUIRED]:\n    alias.clear()\n",
            f"SOURCE_REQUIRED = [{related!r}]\ndef mutate(alias=SOURCE_REQUIRED):\n    alias.clear()\nmutate()\n",
            f"SOURCE_REQUIRED = [{related!r}]\nmatch SOURCE_REQUIRED:\n    case alias:\n        alias.clear()\n",
            f"SOURCE_REQUIRED = [{related!r}]\nclass Escape:\n"
            "    def __radd__(self, values):\n        values.clear()\n        return []\n"
            "other = SOURCE_REQUIRED + Escape()\n",
            f"SOURCE_REQUIRED = [{related!r}]\ndef SOURCE_REQUIRED():\n    return []\n",
            f"SOURCE_REQUIRED = [{related!r}]\nasync def SOURCE_REQUIRED():\n    return []\n",
            f"SOURCE_REQUIRED = [{related!r}]\nclass SOURCE_REQUIRED:\n    pass\n",
            f"SOURCE_REQUIRED = [{related!r}]\ntry:\n    raise ValueError()\n"
            "except ValueError as SOURCE_REQUIRED:\n    pass\n",
            f"SOURCE_REQUIRED = [{related!r}]\nmatch []:\n    case SOURCE_REQUIRED:\n        pass\n",
            f"SOURCE_REQUIRED = [{related!r}]\nmatch {{}}:\n    case {{**SOURCE_REQUIRED}}:\n        pass\n",
            f"SOURCE_REQUIRED = [{related!r}]\nmatch []:\n    case [*SOURCE_REQUIRED]:\n        pass\n",
            f"SOURCE_REQUIRED = [{related!r}]\nfrom builtins import *\n",
            f"SOURCE_REQUIRED = [{related!r}]\nexec('SOURCE_REQUIRED = []')\n",
            f"SOURCE_REQUIRED = [{related!r}]\nglobals()['SOURCE_REQUIRED'] = []\n",
            f"SOURCE_REQUIRED = [{related!r}]\nimport __main__\n__main__.SOURCE_REQUIRED = []\n",
            f"SOURCE_REQUIRED = [{related!r}]\nimport __main__\nsetattr(__main__, 'SOURCE_REQUIRED', [])\n",
            f"SOURCE_REQUIRED = [{related!r}]\nnamespace = globals\nnamespace()['SOURCE_REQUIRED'] = []\n",
            f"SOURCE_REQUIRED = [{related!r}]\nfrom builtins import globals as namespace\n"
            "namespace()['SOURCE_REQUIRED'] = []\n",
            f"SOURCE_REQUIRED = [{related!r}]\ndef helper():\n    pass\n"
            "helper.__globals__['SOURCE_REQUIRED'] = []\n",
            f"SOURCE_REQUIRED = [{related!r}]\nimport sys\nnamespace = sys._getframe().f_globals\n"
            "namespace['SOURCE_REQUIRED'] = []\n",
            f"SOURCE_REQUIRED = [{related!r}]\nnamespace = globals\nnamespace()['SOURCE_' + 'REQUIRED'] = []\n",
            f"SOURCE_REQUIRED = [{related!r}]\nfrom builtins import globals as namespace\n"
            "namespace()['SOURCE_' + 'REQUIRED'] = []\n",
            f"SOURCE_REQUIRED = [{related!r}]\nimport builtins\nnamespace = builtins.globals\n"
            "namespace()['SOURCE_' + 'REQUIRED'] = []\n",
            f"SOURCE_REQUIRED = [{related!r}]\ndef helper():\n    pass\n"
            "helper.__globals__['SOURCE_' + 'REQUIRED'] = []\n",
            f"SOURCE_REQUIRED = [{related!r}]\nimport sys\nnamespace = sys._getframe().f_globals\n"
            "namespace['SOURCE_' + 'REQUIRED'] = []\n",
            f"SOURCE_REQUIRED = [{related!r}]\nfrom __main__ import SOURCE_REQUIRED as alias\nalias.clear()\n",
            f"SOURCE_REQUIRED = [{related!r}]\nimport builtins, operator\n"
            "namespace = operator.attrgetter('glo' + 'bals')(builtins)\n"
            "namespace()['SOURCE_' + 'REQUIRED'] = []\n",
            f"SOURCE_REQUIRED = [{related!r}]\nimport __main__\n"
            "__main__.__setattr__('SOURCE_' + 'REQUIRED', [])\n",
        ]
        escape = ("class Escape:\n    def __radd__(self, values):\n"
                  "        values.clear()\n        return []\n"
                  "    def __eq__(self, values):\n        values.clear()\n        return False\n")
        definitions.extend(f"SOURCE_REQUIRED = [{related!r}]\n" + escape + expression
                           for expression in (
                               "SOURCE_REQUIRED + Escape()\n",
                               "if SOURCE_REQUIRED + Escape():\n    pass\n",
                               "while SOURCE_REQUIRED + Escape():\n    break\n",
                               "assert not (SOURCE_REQUIRED + Escape())\n",
                               "SOURCE_REQUIRED == Escape()\n",
                               "if SOURCE_REQUIRED == Escape():\n    pass\n",
                               "match 0:\n    case 0 if SOURCE_REQUIRED + Escape():\n        pass\n",
                               "def helper(value: SOURCE_REQUIRED + Escape()):\n    pass\n",
                               'f"{SOURCE_REQUIRED + Escape()}"\n',
                           ))
        definitions.append(
            f"SOURCE_REQUIRED = [{related!r}]\n"
            "class Escape:\n    def __radd__(self, values):\n"
            "        values.clear()\n        return ValueError\n"
            "try:\n    raise ValueError()\nexcept SOURCE_REQUIRED + Escape():\n    pass\n"
        )
        for definition in definitions:
            with self.subTest(definition=definition), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                _, source = self.scope_fixture(root, related)
                (root / "scripts/project_workflow/copier_inventory.py").write_text(
                    definition + "GENERATED_REQUIRED = []\n"
                )
                _, report = self.module().check_authoring_input(
                    root, source, profile="root", scope_candidates=True
                )
                rows = [item for item in self.scope_rows(report) if item["relation"] == "SOURCE_REQUIRED"]
                self.assertTrue(rows)
                self.assertTrue(all(item["status"] == "unknown" for item in rows))

    def test_scope_candidates_keep_consumer_incompatible_ownership_unknown(self):
        for index, profile in enumerate(("root", "generated")):
            for representation in ("quoted", "commented", "flow"):
                with self.subTest(profile=profile, representation=representation), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    path = (".codex/skills/" if profile == "root" else
                            ".project-agent-workflow/skills/") + "inspect-agent-session/SKILL.md"
                    _, source = self.scope_fixture(root, path, profile)
                    inventory = root / (("template/" if profile == "root" else "") +
                                        ".project-agent-workflow/ownership.yaml")
                    original = inventory.read_text()
                    entry = "  - .project-agent-workflow/**"
                    replacement = {
                        "quoted": '  - ".project-agent-workflow/**"',
                        "commented": entry + " # not part of the validator pattern",
                        "flow": 'copier_managed: [".project-agent-workflow/**"]\nunused_paths:\n  - unused',
                    }[representation]
                    inventory.write_text(original.replace(
                        "copier_managed:\n" + entry if representation == "flow" else entry,
                        replacement, 1,
                    ))
                    module = load_module(PLAN_AUTHORING_MODULES[index], f"scope_ownership_{index}")
                    _, report = module.check_authoring_input(
                        root, source, profile=profile, scope_candidates=True
                    )
                    rows = [item for item in self.scope_rows(report)
                            if item["relation"] == "registration"
                            and item["related_path"] == ".project-agent-workflow/skills/inspect-agent-session/SKILL.md"]
                    self.assertTrue(rows)
                    self.assertTrue(all(item["status"] == "unknown" for item in rows))

    def test_scope_candidates_find_reverse_registered_counterparts_without_expanding_scope(self):
        declared = "template/.project-agent-workflow/scripts/plan_scope_candidates.py"
        counterpart = "scripts/project_workflow/plan_scope_candidates.py"
        for registered in (True, False):
            with self.subTest(registered=registered), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                document, source = self.scope_fixture(root, declared)
                if not registered:
                    inventory = root / "scripts/project_workflow/copier_inventory.py"
                    inventory.write_text(inventory.read_text().replace(
                        '    "' + counterpart + '",\n', "", 1
                    ))
                before = source.read_bytes()
                digest, ordinary = self.module().check_authoring_input(root, source, profile="root")
                same_digest, report = self.module().check_authoring_input(
                    root, source, profile="root", scope_candidates=True
                )
                matches = [item for item in self.scope_rows(report)
                           if item["relation"] == "counterpart" and item["path"] == counterpart]
                self.assertEqual(["review_required"] if registered else [],
                                 [item["status"] for item in matches])
                self.assertFalse(self.scope_rows(ordinary))
                self.assertEqual(digest, same_digest)
                self.assertEqual(before, source.read_bytes())
                self.assertEqual([declared], self.module().build_document(document, profile="root")["write_scope"])

    def test_scope_candidates_find_jinja_source_and_missing_generated_membership(self):
        declared = "docs/agent/spec-index.yaml"
        counterpart = "template/.project-agent-workflow/docs/agent/spec-index.yaml.jinja"
        output = ".project-agent-workflow/docs/agent/spec-index.yaml"
        for registered in (True, False):
            with self.subTest(registered=registered), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                document, source = self.scope_fixture(root, declared)
                inventory = root / "scripts/project_workflow/copier_inventory.py"
                inventory.write_text(
                    f"SOURCE_REQUIRED = {[declared, counterpart]!r}\n"
                    f"GENERATED_REQUIRED = {([output] if registered else [])!r}\n"
                )
                before = source.read_bytes()
                digest, _ = self.module().check_authoring_input(root, source, profile="root")
                same_digest, report = self.module().check_authoring_input(
                    root, source, profile="root", scope_candidates=True
                )
                rows = self.scope_rows(report)
                candidate = next(item for item in rows if item["relation"] == "counterpart"
                                 and item["path"] == counterpart)
                self.assertEqual("review_required", candidate["status"])
                source_registration = next(item for item in rows if item["relation"] == "update_registration"
                                           and item["related_path"] == counterpart)
                self.assertEqual("covered", source_registration["status"])
                consumer = next(item for item in rows if item["relation"] == "update_consumer"
                                and item["related_path"] == counterpart)
                self.assertEqual("unknown", consumer["status"])
                generated = next(item for item in rows if item["relation"] == "GENERATED_REQUIRED"
                                 and item["related_path"] == output)
                self.assertEqual("covered" if registered else "review_required", generated["status"])
                self.assertEqual(digest, same_digest)
                self.assertEqual(before, source.read_bytes())
                self.assertEqual([declared], self.module().build_document(document, profile="root")["write_scope"])

    def test_scope_candidates_find_project_owned_seed_counterparts_in_both_directions(self):
        root_path = "docs/agent/git-retirement.yaml"
        template_path = "template/docs/agent/git-retirement.yaml.jinja"
        for reverse in (False, True):
            with self.subTest(reverse=reverse), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                declared, counterpart = ((template_path, root_path) if reverse else
                                         (root_path, template_path))
                document, source = self.scope_fixture(root, declared)
                before = source.read_bytes()
                digest, _ = self.module().check_authoring_input(root, source, profile="root")
                same_digest, report = self.module().check_authoring_input(
                    root, source, profile="root", scope_candidates=True
                )
                rows = self.scope_rows(report)
                candidate = next(item for item in rows if item["relation"] == "counterpart"
                                 and item["path"] == counterpart)
                self.assertEqual("review_required", candidate["status"])
                generated = next(item for item in rows if item["relation"] == "GENERATED_REQUIRED"
                                 and item["related_path"] == root_path)
                self.assertEqual("unknown", generated["status"])
                registration = next(item for item in rows if item["relation"] == "update_registration"
                                    and item["related_path"] == template_path)
                self.assertEqual("covered", registration["status"])
                consumer = next(item for item in rows if item["relation"] == "update_consumer"
                                and item["related_path"] == template_path)
                self.assertEqual("unknown", consumer["status"])
                self.assertEqual(digest, same_digest)
                self.assertEqual(before, source.read_bytes())
                self.assertEqual([declared], self.module().build_document(document, profile="root")["write_scope"])

    def test_scope_candidates_respect_actual_ownership_byte_boundary(self):
        for index, profile in enumerate(("root", "generated")):
            for size in (64 * 1024, 64 * 1024 + 1):
                with self.subTest(profile=profile, size=size), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    path = (".codex/skills/" if profile == "root" else
                            ".project-agent-workflow/skills/") + "inspect-agent-session/SKILL.md"
                    _, source = self.scope_fixture(root, path, profile)
                    inventory = root / (("template/" if profile == "root" else "") +
                                        ".project-agent-workflow/ownership.yaml")
                    original = inventory.read_bytes()
                    padded = original + b"\n#" + b"x" * (size - len(original) - 2)
                    inventory.write_bytes(padded)
                    validators = (["scripts/validate-copier-update.py",
                                   "template/.project-agent-workflow/scripts/validate-copier-update.py"]
                                  if profile == "root" else
                                  [".project-agent-workflow/scripts/validate-copier-update.py"])
                    for relative in validators:
                        validator = root / relative
                        validator.write_text(validator.read_text().replace(
                            'CURRENT_OWNERSHIP_SHA256 = "' + hashlib.sha256(original).hexdigest() + '"',
                            'CURRENT_OWNERSHIP_SHA256 = "' + hashlib.sha256(padded).hexdigest() + '"', 1,
                        ))
                    module = load_module(PLAN_AUTHORING_MODULES[index], f"scope_ownership_bound_{index}")
                    _, report = module.check_authoring_input(
                        root, source, profile=profile, scope_candidates=True
                    )
                    rows = self.scope_rows(report)
                    expected = "covered" if size == 64 * 1024 else "unknown"
                    registration = next(item for item in rows if item["relation"] == "registration"
                                        and item["related_path"] == ".project-agent-workflow/skills/inspect-agent-session/SKILL.md")
                    self.assertEqual(expected, registration["status"])
                    for relative in validators:
                        fingerprint = next(item for item in rows
                                           if item["relation"] == "ownership_fingerprint"
                                           and item["path"] == relative)
                        self.assertEqual("unknown", fingerprint["status"])

    def test_scope_candidates_cover_only_data_only_python_not_executable_declarations(self):
        related = ".codex/skills/synthetic-scope/SKILL.md"
        for form in ("data_only", "opaque_call", "import_callback", "multiple_target_binding", "shadowed_set_call"):
            with self.subTest(form=form), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                _, source = self.scope_fixture(root, related)
                code = f"SOURCE_REQUIRED = [{related!r}]\nGENERATED_REQUIRED = []\n"
                if form == "opaque_call":
                    code += "rewrite()\n"
                elif form == "import_callback":
                    code = "from unobserved_callback import rewrite\n" + code + "rewrite()\n"
                elif form == "multiple_target_binding":
                    code += "SOURCE_REQUIRED = alias = []\n"
                elif form == "shadowed_set_call":
                    code += "set = 0\nmarker = set()\n"
                (root / "scripts/project_workflow/copier_inventory.py").write_text(code)
                _, report = self.module().check_authoring_input(
                    root, source, profile="root", scope_candidates=True
                )
                row = next(item for item in self.scope_rows(report)
                           if item["relation"] == "SOURCE_REQUIRED" and item["related_path"] == related)
                self.assertEqual("covered" if form == "data_only" else "unknown", row["status"])

    def test_scope_candidates_preserve_direct_generated_hook_and_tentative_root_only(self):
        for path in (".project-agent-workflow/hooks/stop_review_gate.py",
                     ".codex/skills/release-project/SKILL.md"):
            with self.subTest(path=path), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                _, source = self.scope_fixture(root, path)
                _, report = self.module().check_authoring_input(
                    root, source, profile="root", scope_candidates=True
                )
                rows = self.scope_rows(report)
                if path.startswith(".project-agent-workflow/"):
                    row = next(item for item in rows if item["relation"] == "counterpart"
                               and item["path"] == "template/" + path)
                    self.assertEqual("review_required", row["status"])
                else:
                    row = next(item for item in rows if item["relation"] == "root_only")
                    self.assertEqual("unknown", row["status"])
                    self.assertFalse(any(item["path"].startswith("template/") for item in rows))

    def test_scope_candidates_do_not_equate_update_membership_with_delivery(self):
        related = "template/.project-agent-workflow/scripts/plan_authoring.py"
        for failure in ("other_inventory", "missing", "symlink"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                _, source = self.scope_fixture(root, "scripts/project_workflow/plan_authoring.py")
                if failure == "other_inventory":
                    shell = root / "tests/copier-update.sh"
                    shell.write_text(shell.read_text().replace(
                        'done < "$copier_update_inventory"', 'done < "$unrelated_inventory"', 1
                    ))
                elif failure == "symlink":
                    target = root / related
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.symlink_to(ROOT / related)
                _, report = self.module().check_authoring_input(
                    root, source, profile="root", scope_candidates=True
                )
                rows = [item for item in self.scope_rows(report)
                        if item["relation"] == "update_consumer" and item["related_path"] == related]
                self.assertEqual(["unknown"], [item["status"] for item in rows])

    def test_scope_candidates_preserve_unknown_unsafe_and_ambiguous_sources(self):
        for failure in ("missing", "symlink", "duplicate"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                _, source = self.scope_fixture(root, ".codex/skills/inspect-agent-session/SKILL.md")
                ownership = root / "template/.project-agent-workflow/ownership.yaml"
                original = ownership.read_bytes()
                if failure == "missing":
                    ownership.unlink()
                elif failure == "symlink":
                    target = root / "untrusted.yaml"
                    target.write_bytes(original)
                    ownership.unlink()
                    ownership.symlink_to(target)
                else:
                    ownership.write_bytes(original + b"\ncopier_managed:\n  - .project-agent-workflow/**\n")
                _, report = self.module().check_authoring_input(
                    root, source, profile="root", scope_candidates=True
                )
                rows = [item for item in self.scope_rows(report)
                        if item["path"] == str(ownership.relative_to(root))
                        and item["relation"] == "registration"]
                self.assertTrue(rows)
                self.assertTrue(all(item["status"] == "unknown" for item in rows))

    def test_scope_cli_does_not_execute_a_declared_dependency_name_shadow(self):
        for profile in ("root", "generated"):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                shadow = ("scripts/yaml.py" if profile == "root" else
                          ".project-agent-workflow/scripts/yaml.py")
                _, source = self.scope_fixture(root, shadow, profile)
                accepted = (ROOT_COMMAND if profile == "root" else
                            ROOT / "template/.project-agent-workflow/scripts/plan_authoring.py")
                script = _copy_scope_cli(root, profile, accepted)
                marker = root / "must-not-execute-shadow"
                inspected = root / shadow
                inspected.write_text(
                    "from pathlib import Path\n"
                    + f"Path({str(marker)!r}).write_text('executed')\n"
                    + "raise ImportError('inspected dependency shadow')\n"
                )
                def snapshot():
                    return {str(path.relative_to(root)): path.read_bytes()
                            for path in root.rglob("*") if path.is_file()}
                before = snapshot()
                ordinary = _scope_cli(script, profile, root, source, inspect=False)
                observed = _scope_cli(script, profile, root, source)
                for result in (ordinary, observed):
                    self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual([], _python_source_rows(ordinary.stdout))
                row, = _python_source_rows(observed.stdout)
                self.assertEqual(shadow, row["path"])
                self.assertEqual("parsed", row["status"])
                self.assertEqual("sha256:" + hashlib.sha256(before[shadow]).hexdigest(), row["sha256"])
                self.assertFalse(row["grants_authority"])
                self.assertFalse(marker.exists())
                self.assertNotIn(str(marker), observed.stdout)
                self.assertEqual(before, snapshot())

    def test_scope_option_preserves_python_digest_and_refuses_shell_write(self):
        for profile, script in (
            ("root", ROOT_COMMAND),
            ("generated", ROOT / "template/.project-agent-workflow/scripts/plan_authoring.py"),
        ):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                _, source = self.scope_fixture(root, "src/observed.py", profile)
                command = [sys.executable, "-B", str(script), "--root", str(root), "check"]
                if profile == "generated":
                    command.extend(["--profile", profile])
                command.extend(["--input", str(source), "--scope-candidates", "--print-digest"])
                before = source.read_bytes()
                result = subprocess.run(command, cwd=root, capture_output=True, text=True)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual("sha256:" + hashlib.sha256(before).hexdigest() + "\n", result.stdout)
                self.assertEqual(before, source.read_bytes())
                self.assertEqual([], list((root / "docs/plan/active").iterdir()))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, source = self.scope_fixture(root, "src/observed.py", "generated")
            before = source.read_bytes()
            result = subprocess.run(
                ["sh", str(ROOT / "template/.project-agent-workflow/scripts/create-plan.sh"),
                 "--input", str(source), "--scope-candidates"],
                cwd=root, capture_output=True, text=True,
            )
            self.assertEqual(2, result.returncode)
            self.assertEqual("", result.stdout)
            self.assertEqual(before, source.read_bytes())
            self.assertEqual([], list((root / "docs/plan/active").iterdir()))

    def test_scope_budget_unknowns_and_unicode_framing_in_actual_clis(self):
        for profile, script in (
            ("root", ROOT_COMMAND),
            ("generated", ROOT / "template/.project-agent-workflow/scripts/plan_authoring.py"),
        ):
            with self.subTest(profile=profile):
                _exercise_scope_budget_and_framing_cli(script, profile)

    def test_scope_refuses_runtime_overlap_but_external_analyzer_observes_same_files(self):
        for profile, accepted in (
            ("root", ROOT_COMMAND),
            ("generated", ROOT / "template/.project-agent-workflow/scripts/plan_authoring.py"),
        ):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                helper = ("scripts/project_workflow/plan_scope_candidates.py" if profile == "root"
                          else ".project-agent-workflow/scripts/plan_scope_candidates.py")
                document, source = self.scope_fixture(root, helper, profile)
                selected = _copy_scope_cli(root, profile, accepted)
                marker = root / "inspected-bootstrap-must-not-execute"
                (root / helper).write_text(
                    "from pathlib import Path\n"
                    + f"Path({str(marker)!r}).write_text('executed')\n"
                    + "print('untrusted helper bootstrap')\n"
                )
                runtime_paths = [helper, str((selected.parent / "plan_authoring.py").relative_to(root))]
                if profile == "root":
                    runtime_paths[1] = "scripts/project_workflow/plan_authoring.py"
                    runtime_paths.append("scripts/create-root-plan.py")
                for relative in runtime_paths:
                    document["write_paths"][0]["path"] = relative
                    source = self.write_input(root, document)
                    before = {str(path.relative_to(root)): path.read_bytes()
                              for path in root.rglob("*") if path.is_file()}
                    refused = _scope_cli(selected, profile, root, source)
                    self.assertNotEqual(0, refused.returncode)
                    self.assertEqual("", refused.stdout)
                    self.assertFalse(marker.exists())
                    external = _scope_cli(accepted, profile, root, source)
                    self.assertEqual(0, external.returncode, external.stderr)
                    row, = _python_source_rows(external.stdout)
                    self.assertEqual(relative, row["path"])
                    self.assertEqual("parsed", row["status"])
                    self.assertEqual("sha256:" + hashlib.sha256(before[relative]).hexdigest(), row["sha256"])
                    self.assertFalse(marker.exists())
                    self.assertEqual(before, {str(path.relative_to(root)): path.read_bytes()
                                              for path in root.rglob("*") if path.is_file()})

    def test_scope_response_and_stderr_bounds_terminate_descendant_lock_holders(self):
        for profile, accepted in (
            ("root", ROOT_COMMAND),
            ("generated", ROOT / "template/.project-agent-workflow/scripts/plan_authoring.py"),
        ):
            for channel in (1, 2):
                with self.subTest(profile=profile, channel=channel), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    _, source = self.scope_fixture(root, "src/observed.py", profile)
                    selected = _copy_scope_cli(root, profile, accepted)
                    helper = (selected.parent / "project_workflow/plan_scope_candidates.py" if profile == "root"
                              else selected.with_name("plan_scope_candidates.py"))
                    group, lock, progress = (root / name for name in ("child-group", "child-lock", "child-progress"))
                    # A real process tree, not a mocked subprocess: the direct
                    # child can exit while its descendant retains both pipes.
                    helper.write_text(
                        "import fcntl,os,signal,sys\nfrom pathlib import Path\n"
                        + f"Path({str(group)!r}).write_text(str(os.getpid()))\n"
                        + "sys.stdin.buffer.read()\nready,write_ready=os.pipe()\n"
                        + "if os.fork()==0:\n    os.close(ready)\n"
                        + f"    held=open({str(lock)!r},'wb')\n"
                        + "    fcntl.flock(held,fcntl.LOCK_EX)\n    os.write(write_ready,b'1')\n"
                        + "    while True: signal.pause()\n"
                        + "os.close(write_ready)\nos.read(ready,1)\nos.close(ready)\n"
                        + f"progress=os.open({str(progress)!r},os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)\n"
                        + "os.write(progress,b'R')\nfor i in range(160):\n"
                        + "    pending=memoryview(b'x'*65536)\n"
                        + f"    while pending: pending=pending[os.write({channel},pending):]\n"
                        + "    os.write(progress,b'1')\n"
                    )
                    try:
                        command = [sys.executable, "-B", str(selected), "--root", str(root), "check"]
                        if profile == "generated":
                            command.extend(["--profile", profile])
                        result = subprocess.run(command + ["--input", str(source), "--scope-candidates"],
                                                cwd=root, capture_output=True, text=True, timeout=60)
                        self.assertNotEqual(0, result.returncode)
                        self.assertEqual("", result.stdout)
                        completed = progress.read_bytes()
                        self.assertTrue(completed.startswith(b"R"))
                        self.assertLess(len(completed) - 1, 160)
                        with lock.open("r+b") as held:
                            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            fcntl.flock(held, fcntl.LOCK_UN)
                    finally:
                        if group.exists():
                            try:
                                os.killpg(int(group.read_text()), 9)
                            except ProcessLookupError:
                                pass

    def test_scope_refuses_future_runtime_import_and_external_runtime_observes_it(self):
        for profile, script in (
            ("root", ROOT_COMMAND),
            ("generated", ROOT / "template/.project-agent-workflow/scripts/plan_authoring.py"),
        ):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                runtime = root / "runtime"
                venv.EnvBuilder(with_pip=False, symlinks=True).create(runtime)
                python = runtime / "bin/python"
                metadata = subprocess.run(
                    [str(python), "-I", "-B", "-c", "import sysconfig;print(sysconfig.get_path('purelib'))"],
                    capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(0, metadata.returncode, metadata.stderr)
                target = Path(metadata.stdout.strip()) / "yaml.py"
                relative = target.relative_to(root).as_posix()
                _, source = self.scope_fixture(root, relative, profile)
                marker = root / "future-runtime-source-must-not-execute"
                raw = ("from pathlib import Path\n"
                       + f"Path({str(marker)!r}).write_text('executed')\n"
                       + "raise ImportError('declared future runtime source')\n").encode()
                target.write_bytes(raw)
                command = [str(python), "-B", str(script), "--root", str(root), "check"]
                if profile == "generated":
                    command.extend(["--profile", profile])
                before = source.read_bytes()
                refused = subprocess.run(command + ["--input", str(source), "--scope-candidates"],
                                         cwd=root, capture_output=True, text=True, timeout=60)
                self.assertNotEqual(0, refused.returncode)
                self.assertEqual("", refused.stdout)
                self.assertFalse(marker.exists())
                external = _scope_cli(script, profile, root, source)
                self.assertEqual(0, external.returncode, external.stderr)
                row, = _python_source_rows(external.stdout)
                self.assertEqual((relative, "parsed"), (row["path"], row["status"]))
                self.assertEqual("sha256:" + hashlib.sha256(raw).hexdigest(), row["sha256"])
                self.assertFalse(marker.exists())
                self.assertEqual(raw, target.read_bytes())
                self.assertEqual(before, source.read_bytes())

    def test_successful_scope_helper_releases_closed_stdio_descendant_lock(self):
        for profile, script in (
            ("root", ROOT_COMMAND),
            ("generated", ROOT / "template/.project-agent-workflow/scripts/plan_authoring.py"),
        ):
            with self.subTest(profile=profile):
                _exercise_scope_success_group_cli(script, profile, closed_stdio=True)

    def test_successful_scope_helper_releases_inherited_stdio_descendant_lock(self):
        for profile, script in (
            ("root", ROOT_COMMAND),
            ("generated", ROOT / "template/.project-agent-workflow/scripts/plan_authoring.py"),
        ):
            with self.subTest(profile=profile):
                _exercise_scope_success_group_cli(script, profile, closed_stdio=False)

    def test_fixture_cases_decide_as_recorded(self):
        module = self.module()
        for fixture_name in ("cases.json", "holdout.json"):
            fixture = self.load_cases(fixture_name)
            for outcome in fixture["observed_outcomes"]:
                self.assertTrue(outcome["decision_matched"], outcome)
            for case in fixture["cases"]:
                with self.subTest(fixture=fixture_name, case=case["id"]):
                    with tempfile.TemporaryDirectory() as tmp:
                        root = self.make_repository(Path(tmp))
                        source = self.write_input(root, case["input"])
                        profile = case["input"]["profile"]
                        if case["expect"] == "accept":
                            module.check_authoring_input(root, source, profile=profile)
                            continue
                        with self.assertRaises(module.AuthoringError) as caught:
                            module.check_authoring_input(root, source, profile=profile)
                        self.assertIn(case["expect_error_contains"], str(caught.exception))

    def test_holdout_fixture_is_not_used_for_tuning(self):
        self.assertFalse(self.load_cases("holdout.json")["used_for_tuning"])
        self.assertTrue(self.load_cases("cases.json")["used_for_tuning"])

    def accepted_case(self, profile: str) -> dict:
        for case in self.load_cases("cases.json")["cases"]:
            if case["expect"] == "accept" and case["input"]["profile"] == profile:
                return case["input"]
        raise AssertionError(f"no accepted {profile} case")

    def test_check_writes_nothing_and_write_reproduces_the_checked_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repository(Path(tmp))
            source = self.write_input(root, self.accepted_case("root"))
            before = sorted(p.name for p in (root / "docs/plan/active").iterdir())
            index_before = (root / "docs/plan/plan.md").read_text(encoding="utf-8")

            checked = self.run_command(root, "check", "--input", str(source), "--print-digest")
            self.assertEqual(checked.returncode, 0, checked.stderr)
            digest = checked.stdout.strip()
            self.assertEqual(
                digest, "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
            )
            self.assertEqual(sorted(p.name for p in (root / "docs/plan/active").iterdir()), before)
            self.assertEqual((root / "docs/plan/plan.md").read_text(encoding="utf-8"), index_before)

            written = self.run_command(
                root, "write", "--input", str(source), "--expect-input-sha256", digest
            )
            self.assertEqual(written.returncode, 0, written.stderr)
            plan_path = root / written.stdout.strip()
            self.assertTrue(plan_path.is_file())
            self.assertIn(written.stdout.strip(), (root / "docs/plan/plan.md").read_text(encoding="utf-8"))

    def test_write_refuses_an_input_that_changed_after_the_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repository(Path(tmp))
            document = self.accepted_case("root")
            source = self.write_input(root, document)
            digest = self.run_command(
                root, "check", "--input", str(source), "--print-digest"
            ).stdout.strip()

            document["summary"] = "A different summary that was never checked"
            self.write_input(root, document)
            written = self.run_command(
                root, "write", "--input", str(source), "--expect-input-sha256", digest
            )

            self.assertNotEqual(written.returncode, 0)
            self.assertIn("changed since it was checked", written.stderr)
            self.assertEqual(list((root / "docs/plan/active").iterdir()), [])
            self.assertEqual(
                (root / "docs/plan/plan.md").read_text(encoding="utf-8"),
                "# Active Plan\n\nNo active development items.\n",
            )

    def test_malformed_active_index_stops_before_any_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repository(Path(tmp))
            malformed = "# Active Plan\n\nid\tpath\tstatus\n001\tdocs/plan/active/a.md\tnot_a_status\n"
            (root / "docs/plan/plan.md").write_text(malformed, encoding="utf-8")
            source = self.write_input(root, self.accepted_case("root"))

            checked = self.run_command(root, "check", "--input", str(source), "--print-digest")
            self.assertNotEqual(checked.returncode, 0)
            self.assertIn("active plan index is invalid", checked.stderr)
            self.assertEqual(list((root / "docs/plan/active").iterdir()), [])
            self.assertEqual((root / "docs/plan/plan.md").read_text(encoding="utf-8"), malformed)

    def test_backlog_rendering_leaves_the_active_index_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repository(Path(tmp))
            document = self.accepted_case("root")
            document["lifecycle"] = "backlog"
            source = self.write_input(root, document)
            digest = self.run_command(
                root, "check", "--input", str(source), "--print-digest"
            ).stdout.strip()
            written = self.run_command(
                root, "write", "--input", str(source), "--expect-input-sha256", digest
            )

            self.assertEqual(written.returncode, 0, written.stderr)
            self.assertTrue(written.stdout.strip().startswith("docs/plan/backlog/"))
            self.assertEqual(
                (root / "docs/plan/plan.md").read_text(encoding="utf-8"),
                "# Active Plan\n\nNo active development items.\n",
            )

    def test_rendered_plan_satisfies_the_admission_and_witness_contracts(self):
        planlib = load_module(PLANLIB, "planlib_for_plan_authoring")
        for profile in ("root", "generated"):
            with self.subTest(profile=profile):
                with tempfile.TemporaryDirectory() as tmp:
                    root = self.make_repository(Path(tmp))
                    source = self.write_input(root, self.accepted_case(profile))
                    module = self.module()
                    digest, _ = module.check_authoring_input(root, source, profile=profile)
                    path = module.write_authoring_input(
                        root, source, expected_digest=digest, profile=profile
                    )
                    parsed = planlib.parse_manifest_text(
                        (root / path).read_text(encoding="utf-8")
                    )
                    planlib.validate_admission_record(parsed)
                    self.assertEqual(len(planlib.validate_validation_witness_map(parsed)), 2)

    def test_claim_wording_does_not_change_the_structural_decision(self):
        """The check proves references and digests, never that a witness establishes a condition."""

        module = self.module()
        truthful = self.accepted_case("root")
        misleading = json.loads(json.dumps(truthful))
        for witness in misleading["witnesses"]:
            witness["claim"] = "Proves every property this repository will ever need."

        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repository(Path(tmp))
            first = self.write_input(root, truthful, "a.json")
            second = self.write_input(root, misleading, "b.json")
            _, truthful_report = module.check_authoring_input(root, first, profile="root")
            _, misleading_report = module.check_authoring_input(root, second, profile="root")

        def structural(report: str) -> list[str]:
            return [
                line
                for line in report.splitlines()
                if not line.strip().startswith(("claimed-witness-behavior:", "authoring-input-sha256:"))
            ]

        self.assertEqual(structural(truthful_report), structural(misleading_report))
        self.assertNotEqual(truthful_report, misleading_report)
        self.assertIn("semantic-review-required:", truthful_report)
        self.assertIn("repository-writes-performed: 0", truthful_report)

    def test_legacy_relaxations_are_not_reachable_from_the_input(self):
        """The interface is a parameter of the conversion, never a field of the input."""

        module = self.module()
        document = self.accepted_case("root")
        document["decisions"] = ["TBD"]
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repository(Path(tmp))
            source = self.write_input(root, document)
            with self.assertRaises(module.AuthoringError) as caught:
                module.check_authoring_input(root, source, profile="root")
            self.assertIn("placeholder", str(caught.exception))

            forged = dict(document)
            forged["authoring_interface"] = "legacy_arguments"
            forged_path = self.write_input(root, forged, "forged.json")
            with self.assertRaises(module.AuthoringError) as forged_error:
                module.check_authoring_input(root, forged_path, profile="root")
            self.assertIn("unknown key", str(forged_error.exception))

            with self.assertRaises(module.AuthoringError) as root_legacy:
                module.check_authoring_input(
                    root, source, profile="root", interface="legacy_arguments"
                )
            self.assertIn("generated plans only", str(root_legacy.exception))
            self.assertEqual(list((root / "docs/plan/active").iterdir()), [])

    def test_declared_paths_may_not_resolve_through_a_symlink(self):
        module = self.module()
        document = self.accepted_case("root")
        document["write_paths"] = [{"id": "wp-lib", "path": "linked/plan_authoring.py"}]
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repository(Path(tmp))
            (root / "real").mkdir()
            (root / "linked").symlink_to("real", target_is_directory=True)
            source = self.write_input(root, document)
            with self.assertRaises(module.AuthoringError) as caught:
                module.check_authoring_input(root, source, profile="root")
            self.assertIn("resolves through a symlink", str(caught.exception))

    def test_surrogate_escape_is_refused_as_an_authoring_error(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repository(Path(tmp))
            document = self.accepted_case("root")
            source = root / "surrogate.json"
            source.write_text(
                json.dumps(document, ensure_ascii=False).replace(
                    '"summary": "', '"summary": "\\ud800', 1
                ),
                encoding="utf-8",
            )
            with self.assertRaises(module.AuthoringError):
                module.check_authoring_input(root, source, profile="root")

    def test_sequential_plans_allocate_distinct_ids_and_one_index_row_each(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repository(Path(tmp))
            written = []
            for index in range(3):
                document = self.accepted_case("root")
                document["slug"] = f"sequential-plan-{index}"
                document["summary"] = f"Sequential plan {index}"
                source = self.write_input(root, document, f"input-{index}.json")
                digest, _ = module.check_authoring_input(root, source, profile="root")
                written.append(
                    module.write_authoring_input(root, source, digest, profile="root")
                )

            self.assertEqual(
                written,
                [
                    "docs/plan/active/001-sequential-plan-0.md",
                    "docs/plan/active/002-sequential-plan-1.md",
                    "docs/plan/active/003-sequential-plan-2.md",
                ],
            )
            self.assertEqual(
                (root / "docs/plan/plan.md").read_text(encoding="utf-8"),
                "# Active Plan\n\nid\tpath\tstatus\n"
                + "".join(
                    f"{path.split('/')[-1][:3]}\t{path}\tin_progress\n" for path in written
                ),
            )

    def test_root_entrypoint_is_bound_to_its_profile_and_interface(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repository(Path(tmp))
            source = self.write_input(root, self.accepted_case("root"))
            for extra in (
                ["--profile", "generated"],
                ["--authoring-interface", "legacy_arguments"],
            ):
                with self.subTest(extra=extra):
                    result = self.run_command(root, "check", "--input", str(source), *extra)
                    self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(list((root / "docs/plan/active").iterdir()), [])

    def test_both_titles_receive_the_same_legacy_treatment(self):
        module = self.module()
        for field in ("summary", "summary_ja"):
            with self.subTest(field=field):
                document = json.loads(json.dumps(self.accepted_case("generated")))
                document[field] = "  " + "a" * 260 + "  "
                with tempfile.TemporaryDirectory() as tmp:
                    root = self.make_repository(Path(tmp))
                    source = self.write_input(root, document)
                    with self.assertRaises(module.AuthoringError):
                        module.check_authoring_input(root, source, profile="generated")
                    digest, _ = module.check_authoring_input(
                        root, source, profile="generated", interface="legacy_arguments"
                    )
                    path = module.write_authoring_input(
                        root,
                        source,
                        digest,
                        profile="generated",
                        interface="legacy_arguments",
                    )
                    rendered = (root / path).read_text(encoding="utf-8")
                    for line in rendered.splitlines():
                        self.assertEqual(line, line.rstrip(), line)

    def test_standing_authorization_renders_one_line_that_the_ledger_reads(self):
        words = "4回目のレビューまで、この計画の続行を承認する。"
        ledger = load_module(ROOT / "scripts/plan-execution-state.py", "ledger_for_plan_authoring")
        planlib = load_module(PLANLIB, "planlib_for_standing_authoring")
        module = self.module()
        self.assertEqual(
            set(module.ADMISSION_PLACEHOLDER_VALUES), set(ledger.STANDING_PLACEHOLDER_VALUES)
        )
        for profile in ("root", "generated"):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as tmp:
                root = self.make_repository(Path(tmp))
                document = json.loads(json.dumps(self.accepted_case(profile)))
                document["standing_continuation_authorization"] = words
                source = self.write_input(root, document)
                if profile == "root":
                    checked = self.run_command(root, "check", "--input", str(source), "--print-digest")
                    self.assertEqual(checked.returncode, 0, checked.stderr)
                    written = self.run_command(
                        root, "write", "--input", str(source),
                        "--expect-input-sha256", checked.stdout.strip(),
                    )
                    self.assertEqual(written.returncode, 0, written.stderr)
                    path = written.stdout.strip()
                else:
                    digest, _ = module.check_authoring_input(root, source, profile=profile)
                    path = module.write_authoring_input(root, source, digest, profile=profile)
                rendered = (root / path).read_text(encoding="utf-8")
                self.assertEqual(
                    [line for line in rendered.splitlines()
                     if line.startswith("standing_continuation_authorization")],
                    [f"standing_continuation_authorization: {words}"],
                )
                self.assertEqual(ledger.plan_standing_quotation(rendered), words)
                self.assertEqual(
                    planlib.parse_manifest_text(rendered)["standing_continuation_authorization"], words
                )
                del document["standing_continuation_authorization"]
                absent = self.write_input(root, document, "absent.json")
                module.check_authoring_input(root, absent, profile=profile)
                self.assertNotIn(
                    "standing_continuation_authorization",
                    module.render_plan(
                        module.build_document(
                            module.parse_input(absent.read_bytes()), profile=profile
                        ),
                        "002",
                    ),
                )

    def test_standing_authorization_refuses_unbounded_values(self):
        module = self.module()
        for profile in ("root", "generated"):
            for value, message in (
                ("", "must not be empty"),
                ("TODO", "placeholder"),
                ("t.b.d.", "placeholder"),
                ("Pending", "placeholder"),
                ("first line\u2028second line", "one line"),
                ("first line\nsecond line", "control character"),
                ("x" * 401, "at most 400 bytes"),
                (" padded words", "leading or trailing whitespace"),
                (["list"], "must be text"),
            ):
                with self.subTest(profile=profile, value=value), tempfile.TemporaryDirectory() as tmp:
                    root = self.make_repository(Path(tmp))
                    document = json.loads(json.dumps(self.accepted_case(profile)))
                    document["standing_continuation_authorization"] = value
                    source = self.write_input(root, document)
                    with self.assertRaises(module.AuthoringError) as caught:
                        module.check_authoring_input(root, source, profile=profile)
                    self.assertIn(message, str(caught.exception))
                    self.assertEqual(list((root / "docs/plan/active").iterdir()), [])

    def test_unassigned_backlog_roundtrip_and_mixed_coverage(self):
        module = self.module()
        planlib = load_module(PLANLIB, "planlib_unassigned_authoring")
        for profile in ("root", "generated"):
            data = self.accepted_case(profile)
            data["lifecycle"] = "backlog"
            texts = [item["text"] for item in data["acceptance_items"]]
            for item in data["acceptance_items"]:
                for key in ("witness", "stage", "authoritative_only_reason"):
                    item.pop(key, None)
                item["unassigned_reason"] = "Live approval acquisition has no complete verification method yet."
            for mixed in (False, True):
                with self.subTest(profile=profile, mixed=mixed):
                    if mixed:
                        item = dict(data["acceptance_items"][0])
                        item["id"] = "another-acceptance"
                        item["text"] = "Preserve the independently assigned fixture predicate."
                        item.pop("unassigned_reason")
                        item["witness"] = data["completion_conditions"][0]["witness"]
                        item["stage"] = "focused"
                        data["acceptance_items"].append(item)
                        data["requirements"][0]["acceptance_items"].append(item["id"])
                    document = module.build_document(data, profile=profile)
                    rendered = module.render_plan(document, "991")
                    values = planlib.parse_manifest_text(rendered)
                    records = planlib.validate_validation_witness_map(values)
                    self.assertEqual(len(records), int(mixed))
                    self.assertEqual(document["acceptance"][:len(texts)], texts)
                    self.assertEqual([r["acceptance_sha256"] for r in document["validation_witness_unassigned"]],
                                     [module.text_digest(text) for text in texts])
                    data["lifecycle"] = "active"
                    with self.assertRaises(module.AuthoringError):
                        module.build_document(data, profile=profile)
                    data["lifecycle"] = "backlog"

    def test_unassigned_report_preserves_reasons_and_marks_draft_completion(self):
        module = self.module()
        for profile in ("root", "generated"):
            for mixed in (False, True):
                with self.subTest(profile=profile, mixed=mixed):
                    data = self.accepted_case(profile)
                    data["lifecycle"] = "backlog"
                    selected = data["acceptance_items"][:1] if mixed else data["acceptance_items"]
                    reasons = []
                    for index, item in enumerate(selected, 1):
                        for key in ("stage", "witness", "authoritative_only_reason"):
                            item.pop(key, None)
                        reason = f"Live target {index} lacks an assigned independent verification method."
                        item["unassigned_reason"] = reason
                        reasons.append(reason)
                    document = module.build_document(data, profile=profile)
                    report = module.render_report(document, "sha256:" + "0" * 64,
                                                  next_plan_id="991", plan_path="docs/plan/backlog/991-example.md")
                    self.assertIn("implementation-admission: blocked (unassigned verification)", report)
                    for reason in reasons:
                        self.assertIn("unassigned-reason: " + reason, report)
                    self.assertNotIn("legacy authoring placeholder", report)
                    self.assertIn("completion-witness-status: unfulfilled draft", report)
                    self.assertEqual(report.count("verification-status: unassigned"), len(reasons))
                    self.assertIn("repository-writes-performed: 0", report)
                    if mixed:
                        self.assertIn("stage: " + data["acceptance_items"][1]["stage"], report)
            assigned = module.build_document(self.accepted_case(profile), profile=profile)
            report = module.render_report(assigned, "sha256:" + "0" * 64,
                                          next_plan_id="991", plan_path="docs/plan/active/991-example.md")
            self.assertNotIn("unassigned", report)
            self.assertNotIn("unfulfilled draft", report)

    def test_plan387_partial_command_is_never_whole_acceptance_evidence(self):
        source = ROOT / "docs/plan/authoring/387-implement-issue18-limited-implementation-resume.json"
        data = json.loads(source.read_text())
        module = self.module()
        document = module.build_document(data, profile="root")
        report = module.render_report(document, "sha256:" + "0" * 64,
                                      next_plan_id="387", plan_path="docs/plan/backlog/387-implement-issue18-limited-implementation-resume.md")
        self.assertEqual(report.count("completion-witness-status: unfulfilled draft"), 5)
        self.assertEqual(report.count("verification-status: unassigned"), 5)
        self.assertIn("implementation-admission: blocked", report)
        self.assertNotIn("legacy authoring placeholder", report)
        self.assertEqual(document["validation_witness_map"], [])
        # A syntactically complete partial-test map and a success note do not
        # authorize activation of these original whole E1-E5 conditions.
        root_policy = load_module(ROOT / "scripts/check-root-agent-policy.py", "plan387_root_pending")
        rendered = module.render_plan(document, "387")
        values = root_policy.parse_plan_manifest(rendered.replace("status: backlog", "status: in_progress"))
        with self.assertRaises(SystemExit):
            root_policy.check_plan_admission("docs/plan/active/387-implement-issue18-limited-implementation-resume.md", values)
        data["lifecycle"] = "active"
        with self.assertRaises(module.AuthoringError):
            module.build_document(data, profile="root")

    def test_unassigned_authoring_rejects_missing_invalid_or_conflicting_reason(self):
        module = self.module()
        for profile in ("root", "generated"):
            for reason in (None, "", " ", "TBD", "t.b.d.", "x" * 241, "語" * 81, "\ud800",
                           *(f"reason{separator}continued" for separator in ("\n", "\r", "\r\n", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"))):
                data = self.accepted_case(profile)
                data["lifecycle"] = "backlog"
                item = data["acceptance_items"][0]
                for key in ("witness", "stage", "authoritative_only_reason"):
                    item.pop(key, None)
                if reason is not None:
                    item["unassigned_reason"] = reason
                with self.subTest(profile=profile, reason=reason):
                    with self.assertRaises(module.AuthoringError):
                        module.build_document(data, profile=profile)
            data = self.accepted_case(profile)
            data["lifecycle"] = "backlog"
            data["acceptance_items"][0]["unassigned_reason"] = "A concrete method remains unassigned."
            with self.assertRaises(module.AuthoringError):
                module.build_document(data, profile=profile)

    def test_safe_unicode_and_literal_escapes_in_reasons_roundtrip_without_loss(self):
        module = self.module()
        planlib = load_module(PLANLIB, "planlib_reason_roundtrip")
        for profile in ("root", "generated"):
            for reason in (
                'Live "approval" verification remains unassigned; \\u0085 stays literal.',
                "実環境の取得検証は未設計です。",
                "Café approval verification remains undefined.",
            ):
                with self.subTest(profile=profile, reason=reason):
                    data = self.accepted_case(profile)
                    data["lifecycle"] = "backlog"
                    for item in data["acceptance_items"]:
                        for key in ("witness", "stage", "authoritative_only_reason"):
                            item.pop(key, None)
                        item["unassigned_reason"] = reason
                    document = module.build_document(data, profile=profile)
                    rendered = module.render_plan(document, "991")
                    values = planlib.parse_manifest_text(rendered.encode("utf-8").decode("utf-8"))
                    planlib.validate_validation_witness_map(values)
                    pending = [json.loads(entry) for entry in values["validation_witness_unassigned"]]
                    self.assertEqual([entry["reason"] for entry in pending],
                                     [reason] * len(data["acceptance_items"]))
                    self.assertEqual(pending, document["validation_witness_unassigned"])

    def test_splitline_reasons_refuse_check_and_write_before_effects(self):
        module = self.module()
        for profile in ("root", "generated"):
            for separator in ("\n", "\r", "\r\n", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"):
                with self.subTest(profile=profile, separator=separator), tempfile.TemporaryDirectory() as tmp:
                    root = self.make_repository(Path(tmp))
                    data = self.accepted_case(profile)
                    data["lifecycle"] = "backlog"
                    item = data["acceptance_items"][0]
                    for key in ("witness", "stage", "authoritative_only_reason"):
                        item.pop(key, None)
                    item["unassigned_reason"] = f"Live method{separator}remains unassigned."
                    source = self.write_input(root, data)
                    before = {path.relative_to(root): path.read_bytes()
                              for path in root.rglob("*") if path.is_file()}
                    digest = "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
                    with self.assertRaises(module.AuthoringError):
                        module.check_authoring_input(root, source, profile=profile)
                    with self.assertRaises(module.AuthoringError):
                        module.write_authoring_input(root, source, digest, profile=profile)
                    self.assertEqual({path.relative_to(root): path.read_bytes()
                                      for path in root.rglob("*") if path.is_file()}, before)

    def test_plan387_complete_checked_input_regenerates_without_requirement_loss(self):
        source = ROOT / "docs/plan/authoring/387-implement-issue18-limited-implementation-resume.json"
        data = json.loads(source.read_text(encoding="utf-8"))
        document = self.module().build_document(data, profile="root")
        rendered = self.module().render_plan(document, "387")
        self.assertEqual(rendered, (ROOT / "docs/plan/backlog/387-implement-issue18-limited-implementation-resume.md").read_text(encoding="utf-8"))
        expected = ['sha256:0d7cabf5a1694a41432b61ad27875ee0c6b69fef2a86b37203c80bee57a323a2', 'sha256:2c84a36e2a222baad191de2332f4cb878a91510ec817db4737c9c521b5a41baa', 'sha256:2c30a0e1bd02f136f1741cda177f803e112048e5bdc61f37305b54b6f94ef372', 'sha256:47022777607a1553215cd75384af833bc3a754eac19a993823a82fa64e959cd2', 'sha256:edad9cbda2cc4ed9975bb1af205b31e2f7a1dd9b3f4242f7c8fb4add73b44e24']
        self.assertEqual([self.module().text_digest(item) for item in document["acceptance"]], expected)
        self.assertEqual([self.module().text_digest(document["completion_conditions"][i]["text"]) for i in document["condition_order"]], expected)
        self.assertEqual(len(document["validation_witness_unassigned"]), 5)
        self.assertEqual(document["validation_witness_map"], [])
        self.assertEqual(document["status"], "backlog")
        for field in ("decisions", "tasks", "validation_notes", "integration_gates"):
            for clause in data[field]:
                self.assertIn(clause, rendered)


class PlanAuthoringInRepositoryTest(unittest.TestCase):
    """Authoring inside a real repository, where the shared lifecycle lock applies."""

    @staticmethod
    def module():
        return load_module(PLAN_AUTHORING_MODULES[0], "plan_authoring_in_repository")

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repository"
        (self.root / "docs/plan/active").mkdir(parents=True)
        (self.root / "docs/plan/backlog").mkdir(parents=True)
        (self.root / "docs/plan/plan.md").write_text(
            "# Active Plan\n\nNo active development items.\n", encoding="utf-8"
        )
        self.git("init", "-q", "-b", "dev")
        self.git("config", "user.name", "Authoring Test")
        self.git("config", "user.email", "authoring@example.invalid")
        self.git("add", "-A")
        self.git("commit", "-qm", "baseline")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def git(self, *arguments: str) -> None:
        subprocess.run(
            ["git", "-C", str(self.root), *arguments],
            check=True,
            capture_output=True,
            text=True,
        )

    def accepted_input(self, profile: str = "root") -> dict:
        cases = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))["cases"]
        for case in cases:
            if case["expect"] == "accept" and case["input"]["profile"] == profile:
                return case["input"]
        raise AssertionError(f"no accepted {profile} case")

    def run_command(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(ROOT_COMMAND), "--root", str(self.root), *args],
            capture_output=True,
            text=True,
            timeout=120,
        )

    def test_check_and_write_complete_inside_a_repository(self) -> None:
        source = self.root / "input.json"
        source.write_text(
            json.dumps(self.accepted_input(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        checked = self.run_command("check", "--input", str(source), "--print-digest")
        self.assertEqual(checked.returncode, 0, checked.stderr)
        digest = checked.stdout.strip()
        written = self.run_command(
            "write", "--input", str(source), "--expect-input-sha256", digest
        )
        self.assertEqual(written.returncode, 0, written.stderr)
        created = sorted(path.name for path in (self.root / "docs/plan/active").iterdir())
        self.assertEqual(len(created), 1, created)
        self.assertTrue(created[0].startswith("001-"), created)

    def test_a_governed_repository_refuses_authoring_outside_a_task_worktree(self) -> None:
        """A repository a binding can name must author its plan in that worktree."""

        self.git("remote", "add", "origin", "git@github.com:example/authoring.git")
        source = self.root / "input.json"
        source.write_text(
            json.dumps(self.accepted_input(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        checked = self.run_command("check", "--input", str(source), "--print-digest")
        self.assertEqual(checked.returncode, 0, checked.stderr)
        written = self.run_command(
            "write", "--input", str(source), "--expect-input-sha256", checked.stdout.strip()
        )
        self.assertEqual(written.returncode, 1)
        self.assertIn("pre-existing checkout", written.stderr)
        self.assertEqual(list((self.root / "docs/plan/active").iterdir()), [])

    def test_rechecking_a_written_input_moves_past_the_plan_it_created(self) -> None:
        module = self.module()
        source = self.root / "input.json"
        source.write_text(
            json.dumps(self.accepted_input(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        digest, _ = module.check_authoring_input(self.root, source, profile="root")
        first = module.write_authoring_input(self.root, source, digest, profile="root")
        self.assertTrue(first.startswith("docs/plan/active/001-"), first)
        _, report = module.check_authoring_input(self.root, source, profile="root")
        self.assertIn("next-plan-id: 002", report)

    def test_a_written_identifier_stays_reserved_until_publication(self) -> None:
        module = self.module()
        guard = module.locate_worktree_guard()
        source = self.root / "input.json"
        source.write_text(
            json.dumps(self.accepted_input(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        digest, _ = module.check_authoring_input(self.root, source, profile="root")
        module.write_authoring_input(self.root, source, digest, profile="root")
        self.assertEqual(guard.reserved_plan_ids(self.root), {1})

    def test_the_reported_identifier_is_the_written_identifier(self) -> None:
        module = self.module()
        source = self.root / "input.json"
        document = self.accepted_input()
        source.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        digest, report = module.check_authoring_input(self.root, source, profile="root")
        reported = [line for line in report.splitlines() if line.startswith("next-plan-id: ")]
        relative = module.write_authoring_input(self.root, source, digest, profile="root")
        self.assertEqual(reported, [f"next-plan-id: {relative[len('docs/plan/active/'):][:3]}"])

    def test_revised_recheck_keeps_id_and_refuses_superseded_write_in_both_copies(self) -> None:
        for index, module_path in enumerate(PLAN_AUTHORING_MODULES):
            with self.subTest(module=module_path):
                module = load_module(module_path, f"revised_authoring_{index}")
                profile = "root" if index == 0 else "generated"
                document = self.accepted_input(profile)
                document["slug"] = f"revised-{index}"
                source_a = self.root / f"input-a-{index}.json"
                source_b = self.root / f"input-b-{index}.json"
                source_a.write_text(json.dumps(document), encoding="utf-8")
                document["summary"] += " after revision"
                source_b.write_text(json.dumps(document, indent=2), encoding="utf-8")
                digest_a, report_a = module.check_authoring_input(
                    self.root, source_a, profile=profile
                )
                digest_b, report_b = module.check_authoring_input(
                    self.root, source_b, profile=profile
                )
                identifier = f"{index + 1:03d}"
                self.assertIn(f"next-plan-id: {identifier}", report_a)
                self.assertIn(f"next-plan-id: {identifier}", report_b)
                guard = module.locate_worktree_guard()
                ledger = guard.reservation_ledger_path(self.root)
                ledger_before = ledger.read_bytes()
                files_before = {
                    path.relative_to(self.root): path.read_bytes()
                    for path in (self.root / "docs/plan").rglob("*.md")
                }
                with self.assertRaises(module.AuthoringError):
                    module.write_authoring_input(
                        self.root, source_a, digest_a, profile=profile
                    )
                self.assertEqual(ledger.read_bytes(), ledger_before)
                self.assertEqual(
                    {
                        path.relative_to(self.root): path.read_bytes()
                        for path in (self.root / "docs/plan").rglob("*.md")
                    },
                    files_before,
                )
                written = module.write_authoring_input(
                    self.root, source_b, digest_b, profile=profile
                )
                self.assertEqual(written, f"docs/plan/active/{identifier}-revised-{index}.md")
                self.assertIn(
                    f"{identifier}\t{written}\t",
                    (self.root / "docs/plan/plan.md").read_text(encoding="utf-8"),
                )

    def test_write_without_check_cannot_allocate_an_identifier(self) -> None:
        module = self.module()
        source = self.root / "unchecked.json"
        source.write_text(json.dumps(self.accepted_input()), encoding="utf-8")
        digest = module.byte_digest(source.read_bytes())
        with self.assertRaises(module.AuthoringError):
            module.write_authoring_input(self.root, source, digest, profile="root")
        self.assertEqual(list((self.root / "docs/plan/active").iterdir()), [])
