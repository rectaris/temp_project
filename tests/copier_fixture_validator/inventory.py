"""Inventory region, declaration, and operand reading tests."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


if __spec__ is None or not __spec__.parent:  # allow direct execution of this module
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from copier_fixture_validator.support import (
    ContractSupportTest,
    INVENTORY_PATH,
    INVENTORY_REGION,
    RULE_INVENTORY_REGION,
    VERSION_COMMITS,
    copier_fixture_validator,
    declared_paths,
    read_inventory,
)



class InventoryRegionTest(ContractSupportTest):
    def test_missing_inventory_region_is_rejected(self) -> None:
        self.assert_rejected(
            self.remove(INVENTORY_REGION),
            RULE_INVENTORY_REGION,
            "no loop reads one inventory",
        )

    def test_duplicated_inventory_region_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(INVENTORY_REGION, INVENTORY_REGION + INVENTORY_REGION),
            RULE_INVENTORY_REGION,
            "more than one inventory copy and staging region",
        )

    def test_duplicated_copy_inside_the_region_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                '  cp "$root/$candidate_path" "$update_source/$candidate_path"\n',
                '  cp "$root/$candidate_path" "$update_source/$candidate_path"\n'
                '  cp "$root/$candidate_path" "$update_source/$candidate_path.copy"\n',
            ),
            RULE_INVENTORY_REGION,
            "copies more than once",
        )

    def test_copy_that_is_not_derived_from_the_inventory_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                'cp "$root/$candidate_path" "$update_source/$candidate_path"',
                'cp "$root/AGENTS.md" "$update_source/AGENTS.md"',
            ),
            RULE_INVENTORY_REGION,
            "not derived from `candidate_path`",
        )

    def test_a_region_that_places_files_with_another_command_is_rejected(self) -> None:
        for command in ("ln", "ln -s", "mv", "rsync"):
            with self.subTest(command=command):
                self.assert_rejected(
                    self.mutate(
                        'cp "$root/$candidate_path" "$update_source/$candidate_path"',
                        f'{command} "$root/$candidate_path" '
                        '"$update_source/$candidate_path"',
                    ),
                    RULE_INVENTORY_REGION,
                    "no loop reads one inventory",
                )

    def test_staging_before_copying_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                '  cp "$root/$candidate_path" "$update_source/$candidate_path"\n'
                '  fixture_git "$update_source" add -- "$candidate_path"\n',
                '  fixture_git "$update_source" add -- "$candidate_path"\n'
                '  cp "$root/$candidate_path" "$update_source/$candidate_path"\n',
            ),
            RULE_INVENTORY_REGION,
            "stages the path before copying it",
        )

    def test_staging_outside_the_region_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                VERSION_COMMITS,
                '\nfixture_git "$update_source" add -- "$candidate_path"\n' + VERSION_COMMITS,
            ),
            RULE_INVENTORY_REGION,
            "staging outside the inventory region",
        )


    def outside(self, addition: str) -> str:
        return self.mutate(VERSION_COMMITS, "\n" + addition + VERSION_COMMITS)

    def test_a_hard_coded_copy_into_the_update_source_is_rejected(self) -> None:
        self.assert_rejected(
            self.outside('cp "$root/AGENTS.md" "$update_source/AGENTS.md"\n'),
            RULE_INVENTORY_REGION,
            "a write into the update source stands outside",
        )

    def test_a_copy_into_the_update_source_under_another_name_is_rejected(
        self,
    ) -> None:
        self.assert_rejected(
            self.outside(
                'mirror="$update_source"\n'
                'cp "$root/AGENTS.md" "$mirror/AGENTS.md"\n'
            ),
            RULE_INVENTORY_REGION,
            "a write into the update source stands outside",
        )

    def test_a_redirection_into_the_update_source_is_rejected(self) -> None:
        self.assert_rejected(
            self.outside('printf x >"$update_source/extra.txt"\n'),
            RULE_INVENTORY_REGION,
            "a write into the update source stands outside",
        )

    def test_a_helper_written_into_the_update_source_is_rejected(self) -> None:
        self.assert_rejected(
            self.outside('touch "$update_source/extra.txt"\n'),
            RULE_INVENTORY_REGION,
            "a write into the update source stands outside",
        )

    def test_staging_a_path_nothing_writes_is_rejected(self) -> None:
        for index, form in enumerate(
            (
                'fixture_git "$update_source" add -- undeclared/path.txt\n',
                'git -C "$update_source" add -- undeclared/path.txt\n',
                'fixture_git "$update_source" add undeclared/path.txt\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "adds a path nothing writes into the update source",
                )

    def test_staging_the_whole_update_source_is_rejected(self) -> None:
        for index, form in enumerate(
            (
                'fixture_git "$update_source" add -A\n',
                'fixture_git "$update_source" add .\n',
                'fixture_git "$update_source" add -u\n',
                'fixture_git "$update_source" add -- .\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "without naming one path",
                )

    def test_staging_a_path_the_fixture_edits_in_place_is_accepted(self) -> None:
        self.assert_accepted(
            self.outside(
                'sed -i "s/a/b/" "$update_source/copier.yml"\n'
                'fixture_git "$update_source" add -- copier.yml\n'
            )
        )

    def test_staging_another_repository_outside_the_region_is_accepted(self) -> None:
        self.assert_accepted(
            self.outside(
                'other="$tmp/other"\n'
                'fixture_git "$other" add -A\n'
                'fixture_git "$other" add -- undeclared/path.txt\n'
            )
        )

    def test_a_copy_outside_the_update_source_is_accepted(self) -> None:
        self.assert_accepted(
            self.outside('cp "$root/AGENTS.md" "$tmp/other/AGENTS.md"\n')
        )

    def test_a_write_this_checker_cannot_place_is_rejected(self) -> None:
        self.assert_rejected(
            self.outside(
                'extra_destination=$(printf %s "$update_source/AGENTS.md")\n'
                'cp "$root/AGENTS.md" "$extra_destination"\n'
            ),
            RULE_INVENTORY_REGION,
            "a write this checker cannot place",
        )

    def test_a_write_a_loop_head_places_is_read_at_that_path(self) -> None:
        """A loop head says which words the name it binds may hold.

        The write is reported as reaching the update source itself rather than
        as a write this checker cannot place, because the head words settle the
        name every round binds.
        """

        self.assert_rejected(
            self.outside(
                'for extra in AGENTS.md; do\n'
                '  cp "$root/$extra" "$update_source/$extra"\n'
                'done\n'
            ),
            RULE_INVENTORY_REGION,
            "a write into the update source stands outside the inventory region",
        )

    def test_a_command_that_puts_files_in_place_is_rejected(self) -> None:
        for index, form in enumerate(
            (
                'tar -x -C "$update_source" -f "$root/extra.tar"\n',
                'rsync -a "$root/AGENTS.md" "$update_source/AGENTS.md"\n',
                'fixture_git "$update_source" apply --index "$root/extra.patch"\n',
                'fixture_git "$update_source" checkout -- AGENTS.md\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "puts files in place",
                )

    def test_a_directory_change_into_the_update_source_is_rejected(self) -> None:
        self.assert_rejected(
            self.outside(
                'cd "$update_source"\n'
                'cp "$root/AGENTS.md" AGENTS.md\n'
                'cd "$root"\n'
            ),
            RULE_INVENTORY_REGION,
            "a directory change into the update source",
        )

    def test_staging_written_as_a_synonym_is_rejected(self) -> None:
        self.assert_rejected(
            self.outside('fixture_git "$update_source" stage -- undeclared.txt\n'),
            RULE_INVENTORY_REGION,
            "adds a path nothing writes into the update source",
        )

    def test_a_git_run_this_checker_cannot_read_is_rejected(self) -> None:
        for index, form in enumerate(
            (
                'printf AGENTS.md | xargs fixture_git "$update_source" add --\n',
                'sh -c \'git -C "$update_source" add -A\'\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "a Git run this checker cannot read",
                )

    def test_staging_a_path_only_a_read_names_is_rejected(self) -> None:
        self.assert_rejected(
            self.outside(
                'grep -qF marker "$update_source/copier.yml"\n'
                'fixture_git "$update_source" add -- copier.yml\n'
            ),
            RULE_INVENTORY_REGION,
            "adds a path nothing writes into the update source",
        )

    def test_staging_an_edited_path_written_in_full_is_accepted(self) -> None:
        self.assert_accepted(
            self.outside(
                'sed -i "s/a/b/" "$update_source/copier.yml"\n'
                'fixture_git "$update_source" add -- "$update_source/copier.yml"\n'
            )
        )

    def test_a_directory_change_outside_the_update_source_is_accepted(self) -> None:
        self.assert_accepted(self.outside('cd "$tmp/other"\ncd "$root"\n'))

    def test_an_alias_bound_by_a_loop_is_placed(self) -> None:
        self.assert_rejected(
            self.outside(
                'for mirror in "$update_source"; do\n'
                '  cp "$root/AGENTS.md" "$mirror/AGENTS.md"\n'
                "done\n"
            ),
            RULE_INVENTORY_REGION,
            "a write into the update source stands outside the inventory region",
        )

    def test_an_alias_bound_by_a_loop_head_it_cannot_read_is_reported(self) -> None:
        self.assert_rejected(
            self.outside(
                'for mirror in $(printf %s "$update_source"); do\n'
                '  sed -i "s/a/b/" "$mirror/NOTICE"\n'
                "done\n"
            ),
            RULE_INVENTORY_REGION,
            "takes a destination this checker cannot place",
        )

    def test_an_alias_bound_from_a_parameter_is_placed(self) -> None:
        """A call site says which directory the parameter it writes names.

        The write is reported as reaching the update source itself rather than
        as a write this checker cannot place, because the value the call site
        writes settles the name the body binds from it.
        """

        self.assert_rejected(
            self.outside(
                "seed() {\n"
                "  mirror=$1\n"
                '  cp "$root/AGENTS.md" "$mirror/AGENTS.md"\n'
                "}\n"
                'seed "$update_source"\n'
            ),
            RULE_INVENTORY_REGION,
            "a write into the update source stands outside the inventory region",
        )

    def test_staging_written_as_an_index_update_is_rejected(self) -> None:
        self.assert_rejected(
            self.outside(
                'fixture_git "$update_source" update-index --add -- undeclared.txt\n'
            ),
            RULE_INVENTORY_REGION,
            "adds a path nothing writes into the update source",
        )

    def test_a_call_passing_another_directory_is_accepted(self) -> None:
        self.assert_accepted(
            self.outside(
                'seed() {\n'
                '  mirror=$1\n'
                '  cp "$root/AGENTS.md" "$mirror/AGENTS.md"\n'
                '}\n'
                'seed "$tmp/other"\n'
            )
        )

    def test_a_copy_into_a_directory_destination_is_rejected(self) -> None:
        for command in ("cp", "install"):
            with self.subTest(command=command):
                self.assert_rejected(
                    self.outside(f'{command} "$root/AGENTS.md" "$update_source/"\n'),
                    RULE_INVENTORY_REGION,
                    "a write into the update source stands outside",
                )

    def test_a_directory_destination_resolved_from_a_name_is_rejected(self) -> None:
        self.assert_rejected(
            self.outside('slash=/\ncp "$root/AGENTS.md" "$update_source$slash"\n'),
            RULE_INVENTORY_REGION,
            "a write into the update source stands outside",
        )

    def test_a_directory_destination_after_a_terminator_is_rejected(self) -> None:
        self.assert_rejected(
            self.outside('cp -- "$root/AGENTS.md" "$update_source/"\n'),
            RULE_INVENTORY_REGION,
            "a write into the update source stands outside",
        )

    def test_every_source_of_a_directory_destination_is_placed(self) -> None:
        self.assert_rejected(
            self.outside(
                'cp "$root/AGENTS.md" "$root/NOTICE" "$update_source/"\n'
            ),
            RULE_INVENTORY_REGION,
            "a write into the update source stands outside",
        )

    def test_a_directory_destination_reached_from_every_call_is_rejected(self) -> None:
        self.assert_rejected(
            self.outside(
                "seed() {\n"
                '  cp "$root/AGENTS.md" "$tmp/$1"\n'
                "}\n"
                'seed "update-source/"\n'
                'seed "other-source/"\n'
            ),
            RULE_INVENTORY_REGION,
            "a write into the update source stands outside",
        )

    def test_a_source_with_no_name_of_its_own_is_reported_unplaceable(self) -> None:
        for index, source in enumerate(('"$root/."', '"$root/.."', '"$root/$1"')):
            with self.subTest(source=source):
                self.assert_rejected(
                    self.outside(f'cp {source} "$update_source/"\n'),
                    RULE_INVENTORY_REGION,
                    "a write this checker cannot place is written where the "
                    "update source is named",
                )

    def test_a_directory_destination_outside_the_update_source_is_accepted(
        self,
    ) -> None:
        self.assert_accepted(
            self.outside('cp "$root/AGENTS.md" "$tmp/other/"\n')
        )

    def test_a_destination_written_without_a_separator_is_accepted(self) -> None:
        self.assert_accepted(
            self.outside('cp "$root/AGENTS.md" "$tmp/update-source"\n')
        )

    def test_a_destination_carrying_the_separator_in_one_form_is_accepted(
        self,
    ) -> None:
        """One form that writes no separator leaves the destination a file.

        The shell creates the destination word itself whenever the value it
        carries ends in a name, so a word that may carry either form proves no
        directory and keeps the reading it already had.
        """

        self.assert_accepted(
            self.outside(
                "seed() {\n"
                '  cp "$root/AGENTS.md" "$tmp/$1"\n'
                "}\n"
                'seed "update-source/"\n'
                'seed "update-source"\n'
            )
        )

    def test_an_empty_only_name_settles_no_directory_destination(self) -> None:
        """The empty value option classification supplies never places a path.

        The word reaches its command as `$update_source/`, but the binding
        model reports the name unreadable, so the destination stays one this
        checker cannot place rather than becoming a directory it reads.
        """

        self.assert_rejected(
            self.outside('empty=\ncp "$root/AGENTS.md" "$empty$update_source/"\n'),
            RULE_INVENTORY_REGION,
            "takes a destination this checker cannot place",
        )

    def test_an_alias_written_with_a_directory_destination_is_unchanged(self) -> None:
        for command in ("mv", "ln", "ln -s"):
            with self.subTest(command=command):
                self.assert_rejected(
                    self.outside(f'{command} "$root/AGENTS.md" "$update_source/"\n'),
                    RULE_INVENTORY_REGION,
                    "an alias of the update source stands outside",
                )

    def test_an_option_bearing_copy_keeps_its_reading(self) -> None:
        for written in (
            'cp -T "$root/AGENTS.md" "$update_source/"',
            'cp --no-target-directory "$root/AGENTS.md" "$update_source/"',
            'cp --parents "$root/AGENTS.md" "$update_source/"',
            'cp -R "$root/AGENTS.md" "$update_source/"',
            'install -d "$update_source/"',
            'install -d "$root/AGENTS.md" "$update_source/"',
            'install -D "$root/AGENTS.md" "$update_source/"',
            'cp "$root/AGENTS.md" -- "$update_source/"',
        ):
            with self.subTest(written=written):
                self.assert_accepted(self.outside(written + "\n"))

    def test_a_deferred_copy_with_a_directory_destination_is_unchanged(self) -> None:
        self.assert_accepted(
            self.outside(
                "seed() {\n"
                '  cp "$root/AGENTS.md" "$update_source/"\n'
                "}\n"
                "trap seed USR1\n"
            )
        )


class InventoryDeclarationTest(ContractSupportTest):
    """Bind the editing carve-out to the paths the inventory declares."""

    def outside(self, addition: str) -> str:
        return self.mutate(VERSION_COMMITS, "\n" + addition + VERSION_COMMITS)

    def test_an_edit_reading_an_undeclared_source_buys_no_staging(self) -> None:
        self.assert_rejected(
            self.outside(
                'sed -i "1r $root/AGENTS.md" "$update_source/NOTICE"\n'
                'fixture_git "$update_source" add -- NOTICE\n'
            ),
            RULE_INVENTORY_REGION,
            "adds a path no inventory line declares",
        )

    def test_an_in_place_edit_of_an_undeclared_path_is_rejected(self) -> None:
        for index, form in enumerate(
            (
                'sed -i "s/a/b/" "$update_source/NOTICE"\n'
                'fixture_git "$update_source" add -- NOTICE\n',
                'sed -i "s/a/b/" "$update_source/template/README.md.jinja"\n'
                'fixture_git "$update_source" add -- template/README.md.jinja\n',
                'python3 - "$update_source/NOTICE" <<\'PY\'\nPY\n'
                'fixture_git "$update_source" add -- "$update_source/NOTICE"\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "adds a path no inventory line declares",
                )

    def test_editing_and_staging_a_declared_path_stays_accepted(self) -> None:
        for index, form in enumerate(
            (
                'sed -i "s/a/b/" "$update_source/copier.yml"\n'
                'fixture_git "$update_source" add -- copier.yml\n',
                'sed -i "s/a/b/"'
                ' "$update_source/template/.project-agent-workflow/README.md"\n'
                'fixture_git "$update_source" add --'
                ' template/.project-agent-workflow/README.md\n',
                'policy="$update_source/copier.yml"\n'
                'sed -i "s/a/b/" "$policy"\n'
                'fixture_git "$update_source" add -- "$policy"\n',
            )
        ):
            with self.subTest(accepted=index):
                self.assert_accepted(self.outside(form))

    def test_a_staged_path_written_with_an_expansion_is_rejected(self) -> None:
        self.assert_rejected(
            self.outside(
                'staged=$(printf %s copier.yml)\n'
                'sed -i "s/a/b/" "$update_source/$staged"\n'
                'fixture_git "$update_source" add -- "$staged"\n'
            ),
            RULE_INVENTORY_REGION,
            "adds a path no inventory line declares",
        )

    def test_an_inventory_declaring_nothing_rejects_every_staging(self) -> None:
        self.declared = ()
        self.assert_rejected(
            self.outside(
                'sed -i "s/a/b/" "$update_source/copier.yml"\n'
                'fixture_git "$update_source" add -- copier.yml\n'
            ),
            RULE_INVENTORY_REGION,
            "adds a path no inventory line declares",
        )

    def test_declared_paths_reads_one_written_path_per_line(self) -> None:
        self.assertEqual(
            declared_paths(["copier.yml", "", "  a/b.md  ", "c//d.md"]),
            frozenset({("copier.yml",), ("a", "b.md"), ("c", "d.md")}),
        )

    def test_an_edit_of_an_undeclared_path_is_rejected_without_any_staging(self) -> None:
        for index, form in enumerate(
            (
                'sed -i "s/a/b/" "$update_source/NOTICE"\n',
                'sed -i "1r $root/AGENTS.md" "$update_source/README.md"\n'
                'fixture_git "$update_source" commit -a -qm "sneak"\n',
                'sed -i "s/a/b/" "$update_source/NOTICE"\n'
                'fixture_git "$update_source" commit -qm "sneak" -- NOTICE\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "an edit outside the inventory region writes a path no "
                    "inventory line declares",
                )

    def test_a_staging_written_inside_a_called_body_is_read(self) -> None:
        for index, form in enumerate(
            (
                "sneak_stage() {\n"
                '  fixture_git "$update_source" add -- "$1"\n'
                "}\n"
                "sneak_stage NOTICE\n",
                "sneak_stage() {\n"
                '  fixture_git "$update_source" add -- NOTICE\n'
                "}\n"
                "sneak_stage\n",
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "staging outside the inventory region adds a path",
                )

    def test_a_commit_that_stages_on_its_own_is_read_as_a_staging(self) -> None:
        for index, form in enumerate(
            (
                'dd if="$root/AGENTS.md" of="$update_source/README.md"\n'
                'fixture_git "$update_source" commit -a -qm x\n',
                'weirdtool "$update_source/README.md"\n'
                'fixture_git "$update_source" commit -a -qm x\n',
                'weirdtool "$update_source/README.md"\n'
                'fixture_git "$update_source" commit -m x README.md\n',
                'weirdtool "$update_source/README.md"\n'
                'fixture_git "$update_source" commit -qm x -- README.md\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "staging outside the inventory region adds",
                )

    def test_a_commit_that_stages_nothing_of_its_own_stays_accepted(self) -> None:
        for index, form in enumerate(
            (
                'fixture_git "$update_source" commit --allow-empty -qm "plain"\n',
                'sed -i "s/a/b/" "$update_source/copier.yml"\n'
                'fixture_git "$update_source" add -- copier.yml\n'
                'fixture_git "$update_source" commit -m "declared"\n',
                'sed -i "s/a/b/" "$update_source/copier.yml"\n'
                'fixture_git "$update_source" commit -qm x -- copier.yml\n',
            )
        ):
            with self.subTest(accepted=index):
                self.assert_accepted(self.outside(form))

    def test_committed_operands_reads_the_forms_that_stage(self) -> None:
        for text, expected in (
            ("commit -m x", ((), False)),
            ("commit --allow-empty -qm x", ((), False)),
            ("commit -a -qm x", ((), True)),
            ("commit -qm x -- a.md", (("a.md",), False)),
            ("commit -m x a.md", (("a.md",), False)),
            ("commit --message=x a.md", (("a.md",), False)),
            ("commit --unknown-option -m x", ((), True)),
        ):
            with self.subTest(written=text):
                words = tuple(SimpleNamespace(text=part) for part in text.split())
                operands, everything = copier_fixture_validator._committed_operands(words)
                self.assertEqual(
                    (tuple(token.text for token in operands), everything), expected
                )

    def test_an_unreadable_inventory_declares_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(read_inventory(Path(directory) / "absent.txt"), frozenset())

    def test_the_shipped_inventory_declares_the_committed_paths(self) -> None:
        declared = read_inventory()
        self.assertIn(("copier.yml",), declared)
        self.assertEqual(declared, read_inventory(INVENTORY_PATH))


class PositionalParameterTest(ContractSupportTest):
    """A word reaches the update source through the parameters a call writes."""

    def outside(self, addition: str) -> str:
        return self.mutate(VERSION_COMMITS, "\n" + addition + VERSION_COMMITS)

    def test_an_update_source_reached_through_a_parameter_is_read(self) -> None:
        for index, form in enumerate(
            (
                "sneak() {\n"
                '  sed -i "s/a/b/" "$1/NOTICE"\n'
                '  fixture_git "$1" add -- NOTICE\n'
                "}\n"
                'sneak "$update_source"\n',
                "sneak() {\n"
                "  where=$1\n"
                '  sed -i "s/a/b/" "$where/NOTICE"\n'
                '  fixture_git "$where" add -- NOTICE\n'
                "}\n"
                'sneak "$update_source"\n',
                "sneak() {\n"
                "  shift\n"
                "  where=$1\n"
                '  sed -i "s/a/b/" "$where/NOTICE"\n'
                '  fixture_git "$where" add -- NOTICE\n'
                "}\n"
                'sneak filler "$update_source"\n',
                "sneak() {\n"
                "  lane=$1\n"
                '  dir="$tmp/$lane"\n'
                '  sed -i "s/a/b/" "$dir/NOTICE"\n'
                '  fixture_git "$dir" add -- NOTICE\n'
                "}\n"
                "sneak update-source\n",
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "no inventory line declares",
                )

    def test_a_parameter_naming_a_declared_path_stays_accepted(self) -> None:
        self.assert_accepted(
            self.outside(
                "edit_declared() {\n"
                '  sed -i "s/a/b/" "$1/copier.yml"\n'
                '  fixture_git "$1" add -- copier.yml\n'
                "}\n"
                'edit_declared "$update_source"\n'
            )
        )

    def test_a_lane_no_call_site_points_at_the_update_source_is_accepted(self) -> None:
        self.assert_accepted(
            self.outside(
                "make_lane() {\n"
                "  lane=$1\n"
                '  out="$tmp/$lane"\n'
                '  mkdir -p "$out"\n'
                '  sed -i "s/a/b/" "$out/NOTICE"\n'
                '  fixture_git "$out" add -- NOTICE\n'
                "}\n"
                "make_lane one\n"
                "make_lane two\n"
            )
        )

    def test_a_parameter_no_call_site_binds_names_no_path(self) -> None:
        for word in ('"$1"', '"$1/x"', '"$0"', '"$9/y"'):
            with self.subTest(word=word):
                self.assertEqual(
                    copier_fixture_validator._settle_word(word, {}, frozenset()),
                    frozenset(),
                )

    def test_an_update_source_passed_down_a_call_chain_is_read(self) -> None:
        self.assert_rejected(
            self.outside(
                "sneak_inner() {\n"
                '  sed -i "s/a/b/" "$1/NOTICE"\n'
                '  fixture_git "$1" add -- NOTICE\n'
                "}\n"
                'sneak_outer() { sneak_inner "$1"; }\n'
                'sneak_outer "$update_source"\n'
            ),
            RULE_INVENTORY_REGION,
            "no inventory line declares",
        )

    def test_a_call_this_checker_cannot_read_hides_no_sibling(self) -> None:
        self.assert_rejected(
            self.outside(
                "sneak() {\n"
                '  sed -i "s/a/b/" "$1/NOTICE"\n'
                '  fixture_git "$1" add -- NOTICE\n'
                "}\n"
                'sneak "$update_source"\n'
                'sneak "${9-x}"\n'
            ),
            RULE_INVENTORY_REGION,
            "no inventory line declares",
        )

    def test_a_shift_the_shell_may_skip_reads_both_distances(self) -> None:
        for index, form in enumerate(
            (
                "sneak() {\n"
                '  if [ -n "${NOPE-}" ]; then\n'
                "    shift\n"
                "  fi\n"
                '  sed -i "s/a/b/" "$1/NOTICE"\n'
                '  fixture_git "$1" add -- NOTICE\n'
                "}\n"
                'sneak "$update_source"\n',
                "sneak() {\n"
                '  [ -z "${NOPE-}" ] || shift\n'
                '  sed -i "s/a/b/" "$1/NOTICE"\n'
                '  fixture_git "$1" add -- NOTICE\n'
                "}\n"
                'sneak "$update_source"\n',
                "sneak() {\n"
                '  [ -n "${NOPE-}" ] && shift\n'
                '  sed -i "s/a/b/" "$1/NOTICE"\n'
                '  fixture_git "$1" add -- NOTICE\n'
                "}\n"
                'sneak "$update_source"\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "no inventory line declares",
                )

    def test_a_shift_a_loop_repeats_reads_every_turn(self) -> None:
        for index, form in enumerate(
            (
                "sneak() {\n"
                "  for held in a b; do shift; done\n"
                '  sed -i "s/a/b/" "$1/NOTICE"\n'
                '  fixture_git "$1" add -- NOTICE\n'
                "}\n"
                'sneak one two "$update_source"\n',
                "sneak() {\n"
                '  while [ "$#" -gt 0 ]; do\n'
                '    sed -i "s/a/b/" "$1/NOTICE"\n'
                '    fixture_git "$1" add -- NOTICE\n'
                "    shift\n"
                "  done\n"
                "}\n"
                'sneak one two "$update_source"\n',
                "sneak() {\n"
                '  until [ "$#" -le 1 ]; do shift; done\n'
                '  sed -i "s/a/b/" "$1/NOTICE"\n'
                '  fixture_git "$1" add -- NOTICE\n'
                "}\n"
                'sneak one two "$update_source"\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "no inventory line declares",
                )

    def test_a_parameter_this_checker_cannot_place_is_reported(self) -> None:
        for index, form in enumerate(
            (
                "sneak() {\n"
                "  steps=0\n"
                '  shift "$steps"\n'
                '  sed -i "s/a/b/" "$1/NOTICE"\n'
                "}\n"
                'sneak "$update_source"\n',
                "reader() { sed -i \"s/a/b/\" \"$1/NOTICE\"; }\n"
                'relay() { reader "$@"; }\n'
                'relay "$update_source"\n',
                "sneak() {\n"
                '  sed -i "s/a/b/" "${1-x}/NOTICE"\n'
                "}\n"
                'sneak "$update_source"\n',
                "sneak() {\n"
                '  sed -i "s/a/b/" "$@"\n'
                "}\n"
                'sneak "$update_source/NOTICE"\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "takes a destination this checker cannot place",
                )

    def test_a_staging_from_a_parameter_it_cannot_place_is_reported(self) -> None:
        for index, form in enumerate(
            (
                'sneak() { fixture_git "$1" add -- NOTICE; }\n'
                'sneak "${9-x}"\n',
                'sneak() { fixture_git "$update_source" add -- "$@"; }\n'
                "sneak NOTICE\n",
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "names a repository or a path this checker cannot place",
                )

    def test_an_interpreter_handed_the_parameter_list_stays_accepted(self) -> None:
        self.assert_accepted(
            self.outside(
                "run_helper() {\n"
                "  where=$1\n"
                "  shift\n"
                '  python3 "$root/scripts/adopt-to-namespaced-layout.py" \\\n'
                '    --destination "$where" "$@"\n'
                "}\n"
                'run_helper "$tmp/lane" --dry-run\n'
            )
        )

    def test_a_parameter_that_names_no_path_stays_accepted(self) -> None:
        for index, form in enumerate(
            (
                "bump() {\n"
                '  sed -i "s/^version: .*/version: $1/" "$update_source/copier.yml"\n'
                '  fixture_git "$update_source" add -- copier.yml\n'
                "}\n"
                "label=x1.2.3\n"
                'bump "${label#x}"\n',
                "tag_it() {\n"
                '  sed -i "s/a/b/" "$update_source/copier.yml"\n'
                '  fixture_git "$update_source" commit -qm "$1" -- copier.yml\n'
                "}\n"
                "label=xrelease\n"
                'tag_it "${label#x}"\n',
            )
        ):
            with self.subTest(accepted=index):
                self.assert_accepted(self.outside(form))

    def test_a_guarded_shift_over_a_declared_path_stays_accepted(self) -> None:
        self.assert_accepted(
            self.outside(
                "edit_declared() {\n"
                '  [ -n "${NOPE-}" ] && shift\n'
                '  sed -i "s/a/b/" "$1/copier.yml"\n'
                '  fixture_git "$1" add -- copier.yml\n'
                "}\n"
                'edit_declared "$update_source"\n'
            )
        )

    def test_a_body_that_calls_itself_places_no_parameter(self) -> None:
        for index, form in enumerate(
            (
                "sneak() {\n"
                '  if [ -n "${NOPE-}" ]; then sneak "$1"; fi\n'
                '  sed -i "s/a/b/" "$1/NOTICE"\n'
                "}\n"
                "sneak one\n",
                "sneak() {\n"
                '  if [ -n "${NOPE-}" ]; then relay "$1"; fi\n'
                '  sed -i "s/a/b/" "$1/NOTICE"\n'
                "}\n"
                'relay() { sneak "$1"; }\n'
                "sneak one\n",
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.outside(form),
                    "structure",
                    "has no bounded graph",
                )


class OperandReadingTest(ContractSupportTest):
    """A rule reads the words a command writes at, not every word it takes."""

    def outside(self, addition: str) -> str:
        return self.mutate(VERSION_COMMITS, "\n" + addition + VERSION_COMMITS)

    UNPLACEABLE = 'seed=xupdate-source\nlane="${seed#x}"\nwhere="$tmp/$lane"\n'

    def test_a_flag_is_not_read_as_an_option_value_that_hides_the_destination(
        self,
    ) -> None:
        for index, form in enumerate(
            (
                'sed -i -r "1r $root/AGENTS.md" "$where/NOTICE"\n',
                'sed -i -s "1r $root/AGENTS.md" "$where/NOTICE"\n',
                'ed -s "$where/NOTICE" </dev/null\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.outside(self.UNPLACEABLE + form),
                    RULE_INVENTORY_REGION,
                    "takes a destination this checker cannot place",
                )

    def test_a_destination_written_as_an_option_value_is_read(self) -> None:
        for command in ("cp", "install", "ln", "mv"):
            for option in ("-t", "--target-directory"):
                with self.subTest(command=command, option=option):
                    self.assert_rejected(
                        self.outside(
                            self.UNPLACEABLE + f'{command} {option} "$where" copier.yml\n'
                        ),
                        RULE_INVENTORY_REGION,
                        "takes a destination this checker cannot place",
                    )

    def test_a_target_directory_option_is_resolved_before_operand_reading(self) -> None:
        for form in (
            'topt=--target-directory=\nlane=update-source\n'
            'install "$topt$tmp/$lane" AGENTS.md\n',
            'topt=-t\nlane=update-source\n'
            'install "$topt$tmp/$lane" AGENTS.md\n',
            'topt=--target-directory\n'
            'install "$topt" "$tmp/update-source" AGENTS.md\n',
        ):
            with self.subTest(form=form):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "a write into the update source stands outside the "
                    "inventory region",
                )

    def test_an_option_split_across_resolved_parts_is_read_as_one_option(
        self,
    ) -> None:
        """The option name is read after resolution, not per written part.

        Each form below reaches its command as the same target-directory
        option as a word written with one literal dash run, so each writes
        into the update source and must be reported the same way.
        """

        for form in (
            # A name holding every character after the first dash.
            'opt=-target-directory=\nlane=update-source\n'
            'install "-$opt$tmp/$lane" AGENTS.md\n',
            # A name holding only the short option letter.
            'o=t\nlane=update-source\n'
            'install "-$o$tmp/$lane" AGENTS.md\n',
            # A name holding the first half of the long option name.
            'pre=--target\nlane=update-source\n'
            'install "$pre-directory=$tmp/$lane" AGENTS.md\n',
            # An option name that runs into an unread value with no equals
            # sign: undecided, so the directory it would name is still read.
            'topt=--target-directory\nlane=update-source\n'
            'install "$topt$tmp/$lane" AGENTS.md\n',
        ):
            with self.subTest(form=form):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "a write into the update source stands outside the "
                    "inventory region",
                )

    def test_an_empty_assignment_does_not_erase_the_words_that_carry_it(
        self,
    ) -> None:
        """`name=` binds the empty string rather than an unreadable value.

        Writing an empty name in front of an option used to leave the whole
        word unreadable, which placed no destination and reported nothing.
        """

        for form in (
            'e=\nlane=update-source\n'
            'install "${e}--target-directory=$tmp/$lane" AGENTS.md\n',
            'e=""\nlane=update-source\n'
            'install "${e}--target-directory=$tmp/$lane" AGENTS.md\n',
            "e=''\nlane=update-source\n"
            'install "${e}-t$tmp/$lane" AGENTS.md\n',
            'e=\ninstall "${e}--target-directory" "$tmp/update-source" AGENTS.md\n',
        ):
            with self.subTest(form=form):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "a write into the update source stands outside the "
                    "inventory region",
                )

    def test_an_assembled_word_naming_no_option_keeps_its_reading(self) -> None:
        """Joining resolved parts never removes a destination already read.

        The first word below reaches `t` only after letters this checker does
        not model, and the second names no option at all. Reading either as
        the target-directory option would take the next word as a directory
        and stop the written destination from being read, so both keep the
        reading they already had.
        """

        for form, expected in (
            (
                'own=oroot\ninstall "-$own" AGENTS.md "$tmp/update-source"\n',
                "a write into the update source stands outside the inventory "
                "region",
            ),
            (
                'b=-target-directory=\n'
                'install "-$b" AGENTS.md "$tmp/update-source"\n',
                "a write this checker cannot place",
            ),
        ):
            with self.subTest(form=form):
                self.assert_rejected(
                    self.outside(form), RULE_INVENTORY_REGION, expected
                )

    def test_an_empty_assignment_does_not_widen_a_path_reading(self) -> None:
        """Only option classification supplies the empty value.

        A path word carrying an empty name stays a word this checker refuses
        to read, so the operation keeps its fail-closed disposition instead of
        settling to a destination the general path model never proved.
        """

        self.assert_rejected(
            self.outside('e=\ncp "$root/AGENTS.md" "${e}$update_source/AGENTS.md"\n'),
            RULE_INVENTORY_REGION,
            "a write this checker cannot place is written where the update "
            "source is named",
        )

    def test_an_empty_assignment_keeps_an_ordinary_path_accepted(self) -> None:
        self.assert_accepted(
            self.outside('e=\ncat "${e}$root/pyproject.toml" >/dev/null\n')
        )

    def test_an_ambiguous_target_directory_option_stays_unplaceable(self) -> None:
        for form, expected in (
            (
                'topt=-t\n'
                'if [ -n "${NOPE-}" ]; then topt=--target-directory; fi\n'
                'install "$topt" "$tmp/update-source" AGENTS.md\n',
                "a write this checker cannot place",
            ),
            (
                'install_helper() { install "$1" "$tmp/update-source" AGENTS.md; }\n'
                'install_helper -t\n'
                'install_helper --target-directory\n',
                "a write this checker cannot place",
            ),
            # A cluster reaching `t` only after unmodelled letters keeps the
            # reading it already had, so the real destination is still read.
            (
                'own=oroot\ninstall "-$own" AGENTS.md "$tmp/update-source"\n',
                "a write into the update source stands outside the inventory "
                "region",
            ),
        ):
            with self.subTest(form=form):
                self.assert_rejected(
                    self.outside(form), RULE_INVENTORY_REGION, expected
                )

    def test_a_repository_written_as_an_option_value_is_read(self) -> None:
        for form in (
            'git --git-dir="$where/.git" add -- NOTICE\n',
            'git --work-tree="$where" add -- NOTICE\n',
            'git -C "$where" add -- NOTICE\n',
        ):
            with self.subTest(form=form):
                self.assert_rejected(
                    self.outside(self.UNPLACEABLE + form),
                    RULE_INVENTORY_REGION,
                    "names a repository or a path this checker cannot place",
                )

    def test_an_expression_and_a_message_stay_unread_as_paths(self) -> None:
        self.assert_accepted(
            self.outside(
                "bump() {\n"
                '  sed -i -r "s/^version: .*/version: $1/" "$update_source/copier.yml"\n'
                '  fixture_git "$update_source" commit -qm "$1" -- copier.yml\n'
                "}\n"
                "bump 9.9.9\n"
            )
        )

    def test_a_copy_source_stays_unread_as_a_destination(self) -> None:
        self.assert_accepted(
            self.outside(self.UNPLACEABLE + 'cp "$where/copier.yml" "$tmp/held.yml"\n')
        )

    def test_a_quoted_option_is_read_as_the_option_it_spells(self) -> None:
        for form in (
            'install "-t" "$where" AGENTS.md\n',
            "install '-t' \"$where\" AGENTS.md\n",
            'install -"t" "$where" AGENTS.md\n',
            'install \\-t "$where" AGENTS.md\n',
            'cp "--target-directory=$where" AGENTS.md\n',
        ):
            with self.subTest(form=form):
                self.assert_rejected(
                    self.outside(self.UNPLACEABLE + form),
                    RULE_INVENTORY_REGION,
                    "takes a destination this checker cannot place",
                )

    def test_a_quoted_git_repository_option_is_read(self) -> None:
        self.assert_rejected(
            self.outside(self.UNPLACEABLE + 'git "-C" "$where" add -- AGENTS.md\n'),
            RULE_INVENTORY_REGION,
            "names a repository or a path this checker cannot place",
        )

    def test_a_staging_that_names_no_repository_is_reported(self) -> None:
        for form in (
            'git add -- AGENTS.md\n',
            '( cd "$where" && git add -- AGENTS.md )\n',
            'git commit -qm x -- AGENTS.md\n',
        ):
            with self.subTest(form=form):
                self.assert_rejected(
                    self.outside(self.UNPLACEABLE + form),
                    RULE_INVENTORY_REGION,
                    "names no repository outside the directory it stands in",
                )

    def test_a_staging_that_names_a_relative_repository_is_reported(self) -> None:
        for form in (
            '( cd "$where" && git -C . add -- AGENTS.md )\n',
            '( cd "$where" && git -C ./ add -- AGENTS.md )\n',
            '( cd "$where" && git --git-dir=.git add -- AGENTS.md )\n',
            '( cd "$where" && git -C held add -- AGENTS.md )\n',
        ):
            with self.subTest(form=form):
                self.assert_rejected(
                    self.outside(self.UNPLACEABLE + form),
                    RULE_INVENTORY_REGION,
                    "names no repository outside the directory it stands in",
                )

    def test_an_option_this_checker_cannot_name_keeps_every_operand_read(self) -> None:
        for form in (
            'install "-t$empty" "$where" AGENTS.md\n',
            'install "-t${empty}" "$where" AGENTS.md\n',
            'cp "-t$empty" "$where" AGENTS.md\n',
            'mv "-t$empty" "$where" AGENTS.md\n',
        ):
            with self.subTest(form=form):
                self.assert_rejected(
                    self.outside("empty=\n" + self.UNPLACEABLE + form),
                    RULE_INVENTORY_REGION,
                    "takes a destination this checker cannot place",
                )

    def test_an_option_an_expansion_opens_keeps_every_operand_read(self) -> None:
        for form in (
            'install "${empty}-t" "$where" AGENTS.md\n',
            'install "$empty-t" "$where" AGENTS.md\n',
            'install "$opt" "$where" AGENTS.md\n',
            'install "$opt=$where" AGENTS.md\n',
            'cp "${empty}-t" "$where" AGENTS.md\n',
        ):
            with self.subTest(form=form):
                self.assert_rejected(
                    self.outside("empty=\nopt=-t\n" + self.UNPLACEABLE + form),
                    RULE_INVENTORY_REGION,
                    "takes a destination this checker cannot place",
                )

    def test_a_written_path_segment_keeps_a_copy_source_out_of_the_reading(
        self,
    ) -> None:
        self.assert_accepted(
            self.outside(
                self.UNPLACEABLE + 'cp "$where/copier.yml" "$tmp/held.yml"\n'
            )
        )

    def test_an_alias_of_the_update_source_is_rejected(self) -> None:
        for form in (
            'ln -s "$update_source" "$tmp/held"\n',
            'ln "$update_source/copier.yml" "$tmp/held.yml"\n',
            'mv "$update_source" "$tmp/held"\n',
            'ln -s -t "$tmp" "$update_source"\n',
        ):
            with self.subTest(form=form):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "an alias of the update source stands outside the "
                    "inventory region",
                )

    def test_an_inline_interpreter_program_carrying_update_source_is_rejected(
        self,
    ) -> None:
        for form in (
            "python3 -c \"import os; os.symlink('$update_source', '$tmp/held')\"\n",
            "sh -c \"ln -s '$update_source' '$tmp/held'\"\n",
        ):
            with self.subTest(form=form):
                self.assert_rejected(
                    self.outside(form),
                    RULE_INVENTORY_REGION,
                    "inline interpreter program carries a name",
                )

    def test_interpreter_file_and_standard_input_forms_remain_accepted(self) -> None:
        self.assert_accepted(
            self.outside(
                'python3 "$root/scripts/tool.py" "$update_source"\n'
                'python3 - "$update_source/copier.yml"\n'
            )
        )


class IndirectDispatchTest(ContractSupportTest):
    """A call this checker cannot read settles no name across it."""

    def outside(self, addition: str) -> str:
        return self.mutate(VERSION_COMMITS, "\n" + addition + VERSION_COMMITS)

    RELAY = (
        "mutate() { held=update-source; }\n"
        "relay() { runner=mutate; $runner; }\n"
        "run() {\n"
        "  held=other\n"
        "  relay\n"
        '  sed -i "s/a/b/" "$tmp/$held/NOTICE"\n'
        "}\n"
        "run\n"
    )

    def test_a_call_dispatched_from_a_name_this_checker_cannot_read_unsettles_it(
        self,
    ) -> None:
        self.assert_rejected(
            self.outside(self.RELAY),
            RULE_INVENTORY_REGION,
            "takes a destination this checker cannot place",
        )

    def test_a_call_written_out_keeps_the_names_it_never_assigns_settled(self) -> None:
        self.assert_accepted(
            self.outside(
                "keep() { spare=held; }\n"
                "run() {\n"
                "  held=other\n"
                "  keep\n"
                '  sed -i "s/a/b/" "$tmp/$held/NOTICE"\n'
                "}\n"
                "run\n"
            )
        )


if __name__ == "__main__":
    unittest.main()
