"""Advisory scope correspondence from existing registrations, never write authority."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import stat
import time
from pathlib import Path, PurePosixPath
from typing import Any


MAX_SOURCE_BYTES = 512 * 1024
MAX_PYTHON_SOURCE_BYTES = 2 * 1024 * 1024
MAX_PYTHON_RECORDS = 1024
MAX_TOTAL_PYTHON_RECORDS = 4096
MAX_PYTHON_OBSERVATION_BYTES = 128 * 1024
MAX_DIAGNOSTIC_BYTES = 8 * 1024 * 1024
UPDATE_INVENTORY = "tests/fixtures/orchestration/copier-update-source-inventory.txt"


class Source:
    def __init__(self, root: Path, path: str, *, limit: int = MAX_SOURCE_BYTES):
        self.path = path
        self.text: str | None = None
        self.digest: str | None = None
        descriptor = -1
        directory = -1
        try:
            directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            for part in Path(path).parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                os.close(directory)
                directory = child
            descriptor = os.open(Path(path).name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > limit:
                return
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                raw = stream.read(limit + 1)
            after = os.fstat(descriptor)
            live = os.stat(Path(path).name, dir_fd=directory, follow_symlinks=False)
            def identity(item: os.stat_result) -> tuple[int, ...]:
                return (item.st_dev, item.st_ino, item.st_size, item.st_ctime_ns, item.st_mtime_ns)
            if len(raw) > limit or identity(before) != identity(after) or identity(after) != identity(live):
                return
            self.text = raw.decode("utf-8")
            self.digest = "sha256:" + hashlib.sha256(raw).hexdigest()
        except (OSError, UnicodeError):
            pass
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if directory >= 0:
                os.close(directory)

    def evidence(self, line: int | None = None) -> dict[str, Any]:
        return {"path": self.path, "line": line, "sha256": self.digest}

    def literal(self, name: str, *, function: str | None = None) -> tuple[Any, int | None, bool]:
        """Return a declaration; only a wholly data-only module proves its value."""
        if self.text is None:
            return None, None, False
        try:
            tree = ast.parse(self.text)
            scope: ast.Module | ast.FunctionDef = tree
            if function is not None:
                functions = [node for node in tree.body
                             if isinstance(node, ast.FunctionDef) and node.name == function]
                if len(functions) != 1:
                    return None, None, False
                scope = functions[0]
            matches = [node for node in scope.body if isinstance(node, ast.Assign)
                       and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                       and node.targets[0].id == name]
            if len(matches) != 1:
                return None, None, False
            definition = matches[0]
            value = ast.literal_eval(definition.value)
            data_only = function is None
            for statement in tree.body:
                if (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant)
                        and isinstance(statement.value.value, str)):
                    continue
                if (not isinstance(statement, ast.Assign) or len(statement.targets) != 1
                        or not isinstance(statement.targets[0], ast.Name)):
                    data_only = False
                    break
                if any(isinstance(node, ast.Call) for node in ast.walk(statement.value)):
                    data_only = False
                    break
                try:
                    ast.literal_eval(statement.value)
                except (ValueError, TypeError, RecursionError):
                    data_only = False
                    break
            return value, definition.lineno, data_only
        except (SyntaxError, ValueError, TypeError, RecursionError):
            return None, None, False

    def line_for(self, value: str) -> int | None:
        if self.text is not None:
            for number, line in enumerate(self.text.splitlines(), 1):
                if value in line:
                    return number
        return None


def _catalog_governing_paths(snapshot: Source) -> list[str] | None:
    """Project declarations only; never read assets or validate a profile."""
    if snapshot.text is None:
        return None

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate catalog key")
            result[key] = value
        return result

    def reject_constant(_value: str) -> None:
        raise ValueError("unsupported JSON constant")

    try:
        catalog = json.loads(snapshot.text, object_pairs_hook=unique_object,
                             parse_constant=reject_constant)
        if (not isinstance(catalog, dict)
                or set(catalog) != {"schema_version", "governing_sources", "supplemental_revisions"}
                or type(catalog["schema_version"]) is not int or catalog["schema_version"] != 1
                or not isinstance(catalog["supplemental_revisions"], list)):
            return None
        entries = catalog["governing_sources"]
        if not isinstance(entries, list) or len(entries) > 64:
            return None
        paths: list[str] = []
        identifiers: set[str] = set()
        seen_paths: set[str] = set()
        for entry in entries:
            if (not isinstance(entry, dict)
                    or set(entry) != {"id", "revision", "path", "content_digest", "rationale"}
                    or not all(isinstance(value, str) for value in entry.values())
                    or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", entry["id"])
                    or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", entry["revision"])
                    or not re.fullmatch(r"sha256:[0-9a-f]{64}", entry["content_digest"])
                    or not entry["rationale"].strip()):
                return None
            path = entry["path"]
            relative = PurePosixPath(path)
            if (not path or len(path) > 4096 or "\\" in path or relative.is_absolute()
                    or ".." in relative.parts or str(relative) != path or path == "."
                    or any(ord(char) < 32 or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF
                           or char in "\x85\u2028\u2029"
                           for char in path)
                    or entry["id"] in identifiers or path in seen_paths):
                return None
            identifiers.add(entry["id"])
            seen_paths.add(path)
            paths.append(path)
        return paths
    except (ValueError, TypeError, RecursionError):
        return None


def pattern_matches(path: str, pattern: str) -> bool:
    # Same path grammar as the existing Copier ownership validator, not shell globbing.
    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        return path == prefix or path.startswith(prefix + "/")
    return re.fullmatch(re.escape(pattern).replace(r"\*", "[^/]*"), path) is not None


def _describe_python_source(src: Source, *, record_budget: int = MAX_PYTHON_RECORDS) -> dict[str, Any]:
    """Describe one bounded data snapshot, never imported or executed code."""
    result: dict[str, Any] = {
        "path": src.path, "sha256": src.digest, "byte_limit": MAX_PYTHON_SOURCE_BYTES,
        "status": "unknown", "reason": "source_unavailable",
        "size_bytes": None, "line_count": None, "definitions": None,
        "imports": None, "potential_runtime_loads": None,
        "advisory_only": True, "grants_authority": False,
        "limitations": [
            "Runtime module resolution, conditional/cache selection and executed-source identity are unverified.",
            "Alias and indirect dynamic loading are not exhaustively detected; call spellings do not prove callable identity.",
            "Complete dependency graphs, cycles, agreed-boundary compliance and appropriate responsibility splits are unverified.",
        ],
    }
    if src.text is None:
        return result
    text = src.text
    result["size_bytes"] = len(text.encode("utf-8"))
    result["line_count"] = (text.count("\r") + text.count("\n") - text.count("\r\n")
                            + (1 if text and not text.endswith(("\r", "\n")) else 0))
    definitions, imports, runtime_loads = [], [], []
    runtime_names = {"__import__", "import_module", "spec_from_file_location",
                     "spec_from_loader", "module_from_spec", "exec_module",
                     "load_module", "exec", "eval"}
    records = 0
    try:
        for node in ast.walk(ast.parse(text, filename=src.path)):
            call_name = None
            if isinstance(node, ast.Call):
                function = node.func
                call_name = (function.id if isinstance(function, ast.Name) else
                             function.attr if isinstance(function, ast.Attribute) else None)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                records += 1
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                records += 1 + len(node.names)
            elif call_name in runtime_names:
                records += 1
            if records > record_budget:
                result["reason"] = "observation_record_limit"
                return result
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = ("class" if isinstance(node, ast.ClassDef) else
                        "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function")
                definitions.append({"name": node.name, "kind": kind,
                                    "line": node.lineno, "end_line": node.end_lineno})
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                imports.append({
                    "kind": "from" if isinstance(node, ast.ImportFrom) else "import",
                    "module": getattr(node, "module", None), "level": getattr(node, "level", 0),
                    "names": [{"name": alias.name, "asname": alias.asname} for alias in node.names],
                    "line": node.lineno, "end_line": node.end_lineno,
                })
            elif call_name in runtime_names:
                runtime_loads.append({"spelling": call_name, "line": node.lineno,
                                      "end_line": node.end_lineno})
    except (SyntaxError, ValueError, RecursionError):
        result["reason"] = "syntax_or_parser_limit"
        return result
    result.update(status="parsed", reason=None,
                  definitions=sorted(definitions, key=lambda row: row["line"]),
                  imports=sorted(imports, key=lambda row: row["line"]),
                  potential_runtime_loads=sorted(runtime_loads, key=lambda row: row["line"]))
    if len(json.dumps(result, ensure_ascii=True, sort_keys=True).encode("utf-8")) > MAX_PYTHON_OBSERVATION_BYTES:
        result.update(status="unknown", reason="observation_output_limit",
                      definitions=None, imports=None, potential_runtime_loads=None)
    return result


def _observed_cycle_components(adjacency: dict[str, set[str]]) -> list[list[str]]:
    """Compute self-loop or multi-node components only in the observed subgraph."""
    visited: set[str] = set()
    finished: list[str] = []
    for start in sorted(adjacency):
        stack = [(start, False)]
        while stack:
            node, expanded = stack.pop()
            if expanded:
                finished.append(node)
            elif node not in visited:
                visited.add(node)
                stack.append((node, True))
                stack.extend((child, False) for child in sorted(adjacency[node], reverse=True)
                             if child not in visited)
    reverse: dict[str, set[str]] = {node: set() for node in adjacency}
    for origin, destinations in adjacency.items():
        for destination in destinations:
            reverse[destination].add(origin)
    visited.clear()
    components = []
    for start in reversed(finished):
        if start in visited:
            continue
        members = []
        pending = [start]
        visited.add(start)
        while pending:
            node = pending.pop()
            members.append(node)
            for child in sorted(reverse[node], reverse=True):
                if child not in visited:
                    visited.add(child)
                    pending.append(child)
        if len(members) > 1 or start in adjacency[start]:
            components.append(sorted(members))
    return sorted(components)


def _describe_relative_import_relations(observations: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive static relative-import relations from existing observations, with no reads."""
    indexed = {row["path"]: row for row in observations}
    nodes = [{key: row[key] for key in ("path", "sha256", "status", "reason")}
             for _, row in sorted(indexed.items())]
    adjacency: dict[str, set[str]] = {
        path: set() for path, row in indexed.items() if row["status"] == "parsed"
    }
    relations, unresolved = [], []
    for path, row in sorted(indexed.items()):
        origin = {"path": path, "sha256": row["sha256"]}
        if row["status"] != "parsed":
            unresolved.append({"source": origin, "reason": row["reason"], "line": None})
            continue
        for written in row["imports"]:
            evidence = {"source": origin, **written, "execution_context": "unknown",
                        "imported_names_resolution": "unknown"}
            if not written["level"]:
                unresolved.append({**evidence, "reason": "absolute_import_resolution_unknown"})
                continue
            if written["module"] is None:
                unresolved.append({**evidence, "reason": "attribute_or_submodule_selection_unknown"})
                continue
            parent = PurePosixPath(path).parent
            climb = written["level"] - 1
            if climb > len(parent.parts):
                unresolved.append({**evidence, "reason": "relative_level_outside_declared_root"})
                continue
            for _ in range(climb):
                parent = parent.parent
            module = parent.joinpath(*written["module"].split("."))
            # Match strings in the explicit set only; never stat/read inferred paths.
            candidates = [candidate for candidate in (
                module.as_posix() + ".py", (module / "__init__.py").as_posix()
            ) if candidate in indexed]
            if len(candidates) != 1:
                unresolved.append({**evidence, "reason": "ambiguous_declared_module" if candidates
                                   else "module_not_in_declared_set", "declared_candidates": candidates})
                continue
            destination = indexed[candidates[0]]
            if destination["status"] != "parsed":
                unresolved.append({**evidence, "reason": "declared_target_unavailable_or_unparseable",
                                   "declared_candidates": candidates})
                continue
            target = {"path": destination["path"], "sha256": destination["sha256"],
                      "kind": "package" if PurePosixPath(destination["path"]).name == "__init__.py"
                      else "module"}
            relations.append({**evidence, "target": target})
            adjacency[path].add(destination["path"])
        for potential in row["potential_runtime_loads"]:
            unresolved.append({"source": origin, **potential, "reason": "potential_runtime_load",
                               "execution_context": "unknown"})
    reverse: dict[str, set[str]] = {path: set() for path in adjacency}
    for origin, destinations in adjacency.items():
        for destination in destinations:
            reverse[destination].add(origin)
    reverse_dependents = []
    for path, row in sorted(indexed.items()):
        direct = transitive = None
        if row["status"] == "parsed":
            seen, pending = {path}, [path]
            while pending:
                for origin in reverse[pending.pop()]:
                    if origin not in seen:
                        seen.add(origin)
                        pending.append(origin)
            seen.remove(path)
            direct = [{"path": origin, "sha256": indexed[origin]["sha256"]}
                      for origin in sorted(reverse[path]) if origin != path]
            transitive = [{"path": origin, "sha256": indexed[origin]["sha256"]}
                          for origin in sorted(seen)]
        reverse_dependents.append({
            "target": {"path": path, "sha256": row["sha256"]},
            "status": row["status"], "reason": row["reason"],
            "direct": direct, "transitive": transitive,
        })
    return {
        "scope": "observed_static_subgraph", "advisory_only": True, "grants_authority": False,
        "nodes": nodes, "relations": relations, "unresolved": unresolved,
        "reverse_dependents": reverse_dependents,
        "cycles": [{"members": [{"path": path, "sha256": indexed[path]["sha256"]}
                                  for path in members]}
                   for members in _observed_cycle_components(adjacency)],
        "limitations": [
            "Matches describe lexical relative module references only; package identity and runtime resolution are unknown.",
            "Imported attributes, wildcard exports and attribute-versus-submodule selection are unknown.",
            "All execution contexts are unknown, including conditional, nested and type-only imports.",
            "Cycles are observed static subgraph components, not executed cycles or complete-project absence proofs.",
            "Absolute, undeclared, unavailable, ambiguous, dynamic and runtime-indirect relationships remain unverified.",
            "Per-file stable observations do not prove an atomic cross-file snapshot or executed-source identity.",
            "Reverse dependents describe other parsed sources in this observed subgraph, not complete runtime consumers or required edits.",
            "Transitive dependents include direct ones; the target itself is excluded even in cycles.",
            "Unknown target observations have unknown dependent sets, not evidence of no consumers.",
        ],
    }


def render_candidates(root: Path, paths: list[str], profile: str) -> str:
    """Return diagnostic rows without changing input, reservations, files or scope."""
    started = time.monotonic()
    sources: dict[tuple[str, int], Source] = {}
    rows: list[dict[str, Any]] = []
    declared = set(paths)

    def source(path: str, *, limit: int = MAX_SOURCE_BYTES) -> Source:
        key = (path, limit)
        if key not in sources:
            sources[key] = Source(root, path, limit=limit)
        return sources[key]

    def add(path: str, related: str, relation: str, status: str, reason: str,
            evidence: list[dict[str, Any]]) -> None:
        row = {"path": path, "related_path": related, "relation": relation,
               "status": status, "declared": path in declared, "reason": reason,
               "evidence": evidence}
        if row not in rows:
            rows.append(row)

    def candidate(path: str, related: str, reason: str, evidence: list[dict[str, Any]]) -> None:
        add(path, related, "counterpart", "review_required", reason, evidence)

    def membership(values: set[str] | None, related: str, proven: bool) -> str:
        if values is None or not proven:
            return "unknown"
        if related not in values:
            return "review_required"
        return "covered"

    is_root = profile == "root"
    inventory = source("scripts/project_workflow/copier_inventory.py") if is_root else None
    source_paths, source_line, source_proven = inventory.literal("SOURCE_REQUIRED") if inventory else (None, None, False)
    generated_paths, generated_line, generated_proven = inventory.literal("GENERATED_REQUIRED") if inventory else (None, None, False)
    registered_sources = set(source_paths) if isinstance(source_paths, (list, tuple)) and all(isinstance(p, str) for p in source_paths) else None
    registered_generated = set(generated_paths) if isinstance(generated_paths, (list, tuple)) and all(isinstance(p, str) for p in generated_paths) else None
    policy = source("scripts/check-root-agent-policy.py") if is_root else None
    reusable, reusable_line, reusable_proven = policy.literal("REUSABLE_SKILLS") if policy else (None, None, False)
    reusable = set(reusable) if isinstance(reusable, (list, tuple)) and all(isinstance(p, str) for p in reusable) else None
    # Same 64 KiB ownership admission boundary as the real update validator.
    ownership = source("template/.project-agent-workflow/ownership.yaml" if is_root else
                       ".project-agent-workflow/ownership.yaml", limit=64 * 1024)
    copier = source("copier.yml") if is_root else None
    def patterns(src: Source, key: str) -> list[str] | None:
        if src.text is None:
            return None
        try:
            import yaml
        except ImportError:
            return None
        try:
            node = yaml.compose(src.text, Loader=yaml.SafeLoader)
        except (yaml.YAMLError, ValueError, RecursionError):
            return None
        if not isinstance(node, yaml.MappingNode) or node.tag != "tag:yaml.org,2002:map":
            return None
        fields = {}
        for field, value in node.value:
            if (not isinstance(field, yaml.ScalarNode) or field.tag != "tag:yaml.org,2002:str"
                    or field.value in fields):
                return None
            fields[field.value] = value
        if src is ownership:
            version = fields.get("version")
            if not isinstance(version, yaml.ScalarNode) or version.tag != "tag:yaml.org,2002:int" or version.value != "1":
                return None
            # The update validator consumes a restricted line grammar, not
            # normalized YAML. Unsupported representations must stay unknown.
            if not re.search(r"^version:\s*1\s*$", src.text, re.MULTILINE):
                return None
            consumed: dict[str, list[str]] = {
                field: [] for field in ("copier_managed", "seeded_project_owned", "metadata", "migration_backup")
            }
            current = None
            for line in src.text.splitlines():
                heading = re.fullmatch(r"([a-z_]+):(?:\s.*)?", line)
                if heading is not None:
                    current = heading.group(1) if heading.group(1) in consumed else None
                elif current is not None and (item := re.fullmatch(r"  - (\S.*)", line)) is not None:
                    consumed[current].append(item.group(1))
            if not consumed["copier_managed"] or not consumed["seeded_project_owned"]:
                return None
            for field, entries in consumed.items():
                normalized = fields.get(field)
                if normalized is None:
                    if entries:
                        return None
                elif (not isinstance(normalized, yaml.SequenceNode)
                      or any(not isinstance(item, yaml.ScalarNode) or item.tag != "tag:yaml.org,2002:str"
                             for item in normalized.value)
                      or entries != [item.value for item in normalized.value]):
                    return None
        value = fields.get(key)
        if not isinstance(value, yaml.SequenceNode) or value.tag != "tag:yaml.org,2002:seq":
            return None
        if not all(isinstance(item, yaml.ScalarNode) and item.tag == "tag:yaml.org,2002:str"
                   and "[%" not in item.value for item in value.value):
            return None
        return [item.value for item in value.value]

    managed_patterns = patterns(ownership, "copier_managed")
    skip_patterns = patterns(copier, "_skip_if_exists") if copier else None

    def coverage(path: str, related: str, src: Source, values: list[str] | None,
                 reason: str, *, leading_slash: bool = False) -> str:
        if values is None:
            status, matching = "unknown", None
        else:
            matching = next((item for item in values if pattern_matches(related, item.lstrip("/") if leading_slash else item)), None)
            status = "covered" if matching else "review_required"
        add(path, related, "registration", status,
            reason + (f" Existing pattern: {matching}." if matching else " No proven matching registration."),
            [src.evidence(src.line_for(matching) if matching else None)])
        return status

    update_shell = source("tests/copier-update.sh") if is_root else None
    update_entries: list[str] | None = None
    update_source = source(UPDATE_INVENTORY) if is_root else None
    if update_shell is not None and update_shell.text is not None:
        declarations = re.findall(r'^copier_update_inventory="\$root/([^"\n]+)"$', update_shell.text, re.MULTILINE)
        if declarations == [UPDATE_INVENTORY] and update_source is not None and update_source.text is not None:
            entries = update_source.text.splitlines()
            if entries and len(entries) == len(set(entries)) and all(
                re.fullmatch(r"[A-Za-z0-9_.@/-]+", p) and not p.startswith("/")
                and all(part not in {"", ".", ".."} for part in p.split("/")) for p in entries
            ):
                update_entries = entries

    source_roots: dict[str, tuple[str, ...]] = {}
    if is_root:
        for registered in sorted(registered_sources or ()):
            if not registered.startswith("template/"):
                continue
            output = registered.removeprefix("template/").removesuffix(".jinja")
            if output.startswith(".project-agent-workflow/scripts/"):
                tail = output.removeprefix(".project-agent-workflow/scripts/")
                roots = ("scripts/project_workflow/" + tail, "scripts/" + tail)
            elif output.startswith(".project-agent-workflow/skills/"):
                roots = (".codex/skills/" + output.removeprefix(".project-agent-workflow/skills/"),)
            else:
                roots = (output.removeprefix(".project-agent-workflow/"),)
            source_roots[registered] = tuple(dict.fromkeys((output, *roots)))

    expanded = set(paths)
    skills: dict[str, set[str]] = {}
    prefixes = ((".codex/skills/", "template/.project-agent-workflow/skills/", "template/.agents/skills/")
                if is_root else (".project-agent-workflow/skills/", ".agents/skills/"))
    for path in paths:
        for prefix in prefixes:
            if path.startswith(prefix):
                tail = path[len(prefix):].split("/", 1)
                if len(tail) == 2 and re.fullmatch(r"[a-z0-9][a-z0-9-]*", tail[0]):
                    skills.setdefault(tail[0], set()).add(tail[1])
                break
        for registered, roots in source_roots.items():
            if path in roots:
                expanded.add(registered)
                candidate(registered, path, "Literal source declarations suggest this possible normalized counterpart; effective Python registration and semantic necessity remain unverified.", [inventory.evidence(inventory.line_for(registered))])
            if path == registered:
                for related in roots:
                    if related in registered_sources:
                        expanded.add(related)
                        candidate(related, path, "Both paths have literal source declarations; review this possible reverse counterpart without assuming execution effects or an editing obligation.", [inventory.evidence(inventory.line_for(related)), inventory.evidence(inventory.line_for(path))])

    for skill, relatives in sorted(skills.items()):
        if is_root:
            root_only_source = source("scripts/check-copier-template.py")
            root_only, root_only_line, root_only_proven = root_only_source.literal("root_only_skills", function="require_decision_reuse_alignment")
            if isinstance(root_only, set) and skill in root_only:
                add("scripts/check-copier-template.py", skill, "root_only", "covered" if root_only_proven else "unknown", "An explicit literal root-only declaration keeps these suggestions root-only; checker execution effects remain unverified.", [root_only_source.evidence(root_only_line)])
                continue
            status = membership(reusable, skill, reusable_proven)
            add(policy.path, skill, "reusable_skill", status, "Literal reusable-skill declaration only; executable Python remains unknown and a missing declaration asks review, not a mandatory edit.", [policy.evidence(reusable_line)])
        for relative in sorted(relatives | {"SKILL.md", "agents/openai.yaml"}):
            counterpart_paths = ([f".codex/skills/{skill}/{relative}", f"template/.project-agent-workflow/skills/{skill}/{relative}"]
                                 if is_root else [f".project-agent-workflow/skills/{skill}/{relative}"])
            for path in counterpart_paths:
                expanded.add(path)
                candidate(path, skill, "Review the existing reusable skill body/metadata or the declared resource counterpart; optional resources and dynamic callers remain unknown.", [policy.evidence(reusable_line)] if policy else [ownership.evidence()])
        bridge = ("template/" if is_root else "") + f".agents/skills/{skill}/SKILL.md"
        expanded.add(bridge)
        candidate(bridge, skill, "Review the discovery bridge and its intended collision/ownership behavior; this suggestion grants no write permission.", [ownership.evidence()])
        bridge_output = bridge.removeprefix("template/")
        bridge_status = coverage(ownership.path, bridge_output, ownership, managed_patterns, "Review discovery bridge ownership.")
        if copier is not None:
            coverage(copier.path, bridge_output, copier, skip_patterns, "Review project-owned discovery bridge preservation where that behavior is intended.", leading_slash=True)
        for path in sorted(p for p in expanded if p.startswith(("template/.project-agent-workflow/skills/" if is_root else ".project-agent-workflow/skills/") + skill + "/")):
            coverage(ownership.path, path.removeprefix("template/"), ownership, managed_patterns, "Existing broad ownership coverage needs no additional literal path entry.")
        for validator_path in (["scripts/validate-copier-update.py", "template/.project-agent-workflow/scripts/validate-copier-update.py"] if is_root else [".project-agent-workflow/scripts/validate-copier-update.py"]):
            validator = source(validator_path)
            fingerprint, line, fingerprint_proven = validator.literal("CURRENT_OWNERSHIP_SHA256")
            matches = ownership.digest is not None and fingerprint == ownership.digest.removeprefix("sha256:")
            status = "unknown" if not fingerprint_proven or not isinstance(fingerprint, str) or ownership.digest is None else "covered" if matches and bridge_status == "covered" else "review_required"
            add(validator_path, ownership.path, "ownership_fingerprint", status, "Literal fingerprint reference only; executable validator effects remain unknown. Review both counterparts for any necessary ownership change.", [validator.evidence(line), ownership.evidence()])

    for path in sorted(expanded):
        if not is_root:
            add(path, path, "project_consumer", "unknown", "Installed projects have no template-development inventory or proven dynamic-caller graph; retain project-specific scope review.", [])
            continue
        registrations = [(registered_sources, source_line, source_proven, path, "SOURCE_REQUIRED")]
        if path.startswith("template/"):
            registrations.append((registered_generated, generated_line, generated_proven,
                                  path.removeprefix("template/").removesuffix(".jinja"), "GENERATED_REQUIRED"))
        for values, line, proven, related, label in registrations:
            status = membership(values, related, proven)
            add(inventory.path, related, label, status, "Literal Python declaration only; executable sources remain unknown. An omitted literal asks review without asserting effective absence or an editing obligation.", [inventory.evidence(line)])
        if path.startswith("template/"):
            status = "unknown" if update_entries is None else "covered" if path in update_entries else "review_required"
            evidence = [update_shell.evidence(update_shell.line_for("copier_update_inventory=")),
                        update_source.evidence(update_source.line_for(path) if update_entries and path in update_entries else None)]
            add(UPDATE_INVENTORY, path, "update_registration", status,
                "Declared inventory membership only, not proof of the active loop, file admission or installed delivery.", evidence)
            add(UPDATE_INVENTORY, path, "update_consumer", "review_required" if status == "review_required" else "unknown",
                "An omitted registration can leave an old consumer. Membership alone cannot prove the actual loop input, missing/symlink source admission or delivery; verify the actual updated consumer.", evidence)
    catalogs = [("docs/agent/harness-instructions.json", ""),
                ("template/.project-agent-workflow/docs/agent/harness-instructions.json", "template/")] if is_root else [
                    (".project-agent-workflow/docs/agent/harness-instructions.json", "")]
    for catalog_path, prefix in catalogs:
        snapshot = source(catalog_path)
        references = _catalog_governing_paths(snapshot)
        covered = any(pattern_matches(catalog_path, pattern) for pattern in declared)
        if references is None:
            add(catalog_path if covered else "", "", "registration", "unknown",
                "Canonical governing-source declarations are unavailable, unsafe, ambiguous or unsupported; no catalog coverage is proved.",
                [snapshot.evidence()])
            continue
        for reference in references:
            related = prefix + reference
            if not any(pattern_matches(related, pattern) for pattern in declared):
                continue
            add(catalog_path, related, "registration", "covered" if covered else "review_required",
                "Catalog path/digest declaration only. Covered means catalog scope correspondence, not digest agreement or a required edit. Referenced assets are not read; profile validity and execution authority remain unproved.",
                [snapshot.evidence()])
    add("", "", "dynamic_consumers", "unknown", "Static candidates cannot prove arbitrary runtime callers, complete change scope, semantic necessity, Tier, acceptance or authority; parent review remains required.", [])
    lines = []
    response_bytes = 0

    def append_line(line: str) -> None:
        nonlocal response_bytes
        response_bytes += len(line.encode("utf-8")) + 1
        if response_bytes > MAX_DIAGNOSTIC_BYTES:
            raise ValueError("scope diagnostic exceeded its response byte budget")
        lines.append(line)

    append_line("scope-candidates-purpose: advisory only; no scope expansion, required edit, Tier decision or acceptance")
    for row in rows:
        append_line("scope-candidate: " + json.dumps(row, ensure_ascii=True, sort_keys=True))
    observations = []
    remaining_records = MAX_TOTAL_PYTHON_RECORDS
    for path in sorted(declared):
        if path.endswith(".py"):
            observed = _describe_python_source(
                source(path, limit=MAX_PYTHON_SOURCE_BYTES),
                record_budget=min(MAX_PYTHON_RECORDS, remaining_records),
            )
            if observed["status"] == "parsed":
                remaining_records -= (
                    len(observed["definitions"]) + len(observed["potential_runtime_loads"])
                    + sum(1 + len(row["names"]) for row in observed["imports"])
                )
            observations.append(observed)
            append_line("python-source-observation: " + json.dumps(observed, ensure_ascii=True, sort_keys=True))
    if observations:
        # python-relative-import-relations is an advisory aggregate, never runtime dependency proof.
        append_line("python-relative-import-relations: " + json.dumps(
            _describe_relative_import_relations(observations), ensure_ascii=True, sort_keys=True))
    append_line(f"scope-diagnostic-elapsed-seconds: {time.monotonic() - started:.6f}")
    return "\n".join(lines) + "\n"


def main() -> int:
    import sys
    import sysconfig

    request = json.load(sys.stdin)
    root = Path(request["root"])
    runtime_directories = {
        Path(sysconfig.get_path(name)).resolve()
        for name in ("stdlib", "platstdlib", "purelib", "platlib")
    }
    for relative in request["paths"]:
        if relative.endswith(".py") and any(
            (root / relative).resolve().is_relative_to(directory)
            for directory in runtime_directories
        ):
            raise ValueError("scope diagnostic runtime overlaps inspected data; select an independent runtime")
    sys.stdout.write(render_candidates(
        Path(request["root"]), request["paths"], request["profile"]
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
