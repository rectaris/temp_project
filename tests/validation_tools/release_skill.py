"""Structural tests for the root-only release-project skill."""

from __future__ import annotations

import re
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from .support import ROOT


SKILL_DIR = ROOT / ".codex/skills/release-project"
SKILL_FILE = SKILL_DIR / "SKILL.md"
METADATA_FILE = SKILL_DIR / "agents/openai.yaml"
RUNBOOK = SKILL_DIR / "references/workflow.md"
ROUTING_FILES = (ROOT / "README.md", ROOT / "references/template-development.md")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def frontmatter(text: str) -> dict[str, str]:
    """Read the flat ``key: value`` frontmatter of a SKILL.md body."""
    match = FRONTMATTER_RE.match(text)
    if match is None:
        raise AssertionError("skill body carries no frontmatter")
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, separator, value = line.partition(":")
        if not separator:
            raise AssertionError(f"frontmatter line is not a field: {line}")
        fields[key.strip()] = value.strip()
    return fields


def local_link_targets(path: Path) -> list[str]:
    """Return the repository-local link targets of one Markdown file."""
    targets = []
    for target in LINK_RE.findall(path.read_text(encoding="utf-8")):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        targets.append(target.split("#", 1)[0])
    return targets


class ReleaseSkillStructureTest(unittest.TestCase):
    """The skill must stay discoverable, resolvable, and root-only."""

    def test_the_skill_carries_a_body_and_ui_metadata(self) -> None:
        self.assertTrue(SKILL_FILE.is_file(), SKILL_FILE)
        self.assertTrue(METADATA_FILE.is_file(), METADATA_FILE)
        self.assertTrue(RUNBOOK.is_file(), RUNBOOK)

    def test_the_frontmatter_names_the_folder_and_states_its_triggers(self) -> None:
        fields = frontmatter(SKILL_FILE.read_text(encoding="utf-8"))
        self.assertEqual(set(fields), {"name", "description"})
        self.assertEqual(fields["name"], SKILL_DIR.name)
        self.assertTrue(fields["description"].strip())

    def test_the_metadata_supplies_every_ui_field(self) -> None:
        text = METADATA_FILE.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("interface:\n"), text[:40])
        for field in ("display_name", "short_description", "default_prompt"):
            self.assertIsNotNone(
                re.search(rf'^  {field}: ".+"$', text, re.M), field
            )

    def test_every_local_link_resolves(self) -> None:
        for source in (SKILL_FILE, RUNBOOK, *ROUTING_FILES):
            for target in local_link_targets(source):
                resolved = (source.parent / target).resolve()
                self.assertTrue(
                    resolved.exists(), f"{source} links to a missing path: {target}"
                )

    def test_the_skill_body_links_its_runbook(self) -> None:
        targets = local_link_targets(SKILL_FILE)
        self.assertIn("references/workflow.md", targets)

    def test_both_routing_documents_reach_the_runbook(self) -> None:
        for source in ROUTING_FILES:
            resolved = {
                (source.parent / target).resolve()
                for target in local_link_targets(source)
            }
            self.assertIn(RUNBOOK.resolve(), resolved, source)

    def test_the_skill_is_not_placed_in_generated_output(self) -> None:
        for generated in (
            ROOT / "template/.agents/skills" / SKILL_DIR.name,
            ROOT / "template/.project-agent-workflow/skills" / SKILL_DIR.name,
        ):
            self.assertFalse(generated.exists(), generated)


class ReleaseSkillDetectionTest(unittest.TestCase):
    """The structural checks must fail on the defects they claim to catch."""

    def temporary_skill(self) -> Path:
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, ignore_errors=True)
        copy = directory / SKILL_DIR.name
        shutil.copytree(SKILL_DIR, copy)
        return copy

    def test_missing_frontmatter_is_rejected(self) -> None:
        copy = self.temporary_skill()
        body = copy / "SKILL.md"
        body.write_text("# Release Project\n", encoding="utf-8")
        with self.assertRaises(AssertionError):
            frontmatter(body.read_text(encoding="utf-8"))

    def test_a_broken_local_link_is_detected(self) -> None:
        copy = self.temporary_skill()
        body = copy / "SKILL.md"
        body.write_text(
            body.read_text(encoding="utf-8").replace(
                "references/workflow.md", "references/missing.md"
            ),
            encoding="utf-8",
        )
        targets = local_link_targets(body)
        self.assertIn("references/missing.md", targets)
        self.assertFalse((body.parent / "references/missing.md").exists())

    def test_an_extra_frontmatter_field_is_visible(self) -> None:
        copy = self.temporary_skill()
        body = copy / "SKILL.md"
        text = body.read_text(encoding="utf-8")
        body.write_text(text.replace("---\n\n", "version: 2\n---\n\n", 1), encoding="utf-8")
        self.assertEqual(
            set(frontmatter(body.read_text(encoding="utf-8"))),
            {"name", "description", "version"},
        )


class ReleaseRunbookExampleTest(unittest.TestCase):
    """The runbook's Git examples must be exact-ref shaped and runnable."""

    PUSH_RE = re.compile(r"^\s*git push origin (\S+)\s*$", re.M)
    TAG_RE = re.compile(r"^\s*git tag -a \S+ -m \"[^\"]*\" \S+\s*$", re.M)
    REV_PARSE_RE = re.compile(r"^\s*git rev-parse \S+\^\{commit\}\s*$", re.M)

    def runbook_text(self) -> str:
        return RUNBOOK.read_text(encoding="utf-8")

    def test_every_push_example_names_one_exact_ref(self) -> None:
        pushes = self.PUSH_RE.findall(self.runbook_text())
        self.assertTrue(pushes)
        for ref in pushes:
            self.assertRegex(ref, r"^refs/(heads|tags)/\S+$")

    def test_no_example_pushes_or_removes_refs_in_bulk(self) -> None:
        """Read-only inspection may list refs; a write must never fan out."""
        writes = [
            line.strip()
            for line in self.runbook_text().splitlines()
            if line.strip().startswith(("git push", "git tag"))
        ]
        self.assertTrue(writes)
        for line in writes:
            for forbidden in ("--tags", "--all", "--force", "--delete", "-f ", "-d "):
                self.assertNotIn(forbidden, line, line)

    def test_the_annotated_tag_example_runs_against_an_isolated_repository(self) -> None:
        text = self.runbook_text()
        tag_lines = self.TAG_RE.findall(text)
        rev_parse_lines = self.REV_PARSE_RE.findall(text)
        self.assertTrue(tag_lines, "the runbook must show an annotated tag example")
        self.assertTrue(
            rev_parse_lines, "the runbook must dereference the tag it creates"
        )

        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, ignore_errors=True)

        def git(*args: str) -> str:
            return subprocess.run(
                ["git", *args],
                cwd=directory,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=True,
            ).stdout.strip()

        git("init", "-q", "-b", "main")
        git("config", "user.email", "test@example.invalid")
        git("config", "user.name", "Test")
        (directory / "seed").write_text("seed\n", encoding="utf-8")
        git("add", "seed")
        git("commit", "-qm", "seed")
        head = git("rev-parse", "HEAD")

        def resolve(line: str) -> list[str]:
            concrete = line.strip().replace("<tag>", "v0.0.1")
            concrete = concrete.replace("<publication-oid>", head)
            self.assertNotIn("<", concrete, line)
            return shlex.split(concrete)[1:]

        for line in tag_lines:
            git(*resolve(line))
        for line in rev_parse_lines:
            self.assertEqual(git(*resolve(line)), head)

    def test_the_release_version_anchors_are_unchanged_by_this_skill(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertRegex(readme, r"copier copy --trust --vcs-ref v\d+\.\d+\.\d+ ")
        self.assertIn(
            "https://github.com/rectaris/temp_project.git", readme
        )
        self.assertIn(
            "https://copier.readthedocs.io/en/stable/generating/#templates-versions",
            readme,
        )
