"""Alternate path, destination, and resolution placement tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


if __spec__ is None or not __spec__.parent:  # allow direct execution of this module
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from copier_fixture_validator.support import (
    COMPLIANT,
    ContractSupportTest,
    ROOT,
    RULE_ALTERNATE_PATH,
    RULE_DIRECT_INVOCATION,
    WITHOUT_TRANSITION,
    check,
    copier_fixture_validator,
    shell_execution,
    shell_functions,
    shell_lexical,
)



class TrailingSeparatorDestinationTest(unittest.TestCase):
    """Place the sources of a copy whose destination is written as a directory.

    A destination written with a trailing separator names a directory, so the
    command creates each source under the name that source ends with. The
    placement is read here from the words one operation records, because the
    rules above report only whether some created path reached a searched
    directory and not which names were placed.
    """

    def build(self, body: str):
        """Return the derived fixture for one written body."""

        text = "#!/bin/sh\nset -eu\n" + body
        records = shell_lexical.project(text)
        table = shell_functions.derive(records)
        graph = shell_execution.derive(records, table)
        return copier_fixture_validator._Fixture(text, records, table, graph)

    def helper_paths(self, body: str):
        """Return what the one helper-writing command of a body creates."""

        fixture = self.build(body)
        for operation in fixture.operations:
            words = copier_fixture_validator._operation_words(operation)
            literals = copier_fixture_validator._word_literals(words)
            index = copier_fixture_validator._command_index(
                literals, copier_fixture_validator.HELPER_WRITING_COMMANDS
            )
            if index >= 0:
                return copier_fixture_validator._helper_paths(fixture, operation)
        raise AssertionError("the body writes no helper-writing command")

    def inside(self, body: str) -> set:
        return set(self.helper_paths(body)[1])

    def unplaceable(self, body: str) -> bool:
        return self.helper_paths(body)[3]

    DEST = (True, ("dest",))

    def test_an_unsettled_source_is_placed_under_the_written_name(self) -> None:
        for command in ("cp", "install"):
            with self.subTest(command=command):
                self.assertEqual(
                    self.inside(f'{command} "$1/one" "/dest/"\n'),
                    {(self.DEST, "one")},
                )

    def test_every_unsettled_source_is_placed(self) -> None:
        self.assertEqual(
            self.inside('cp "$1/one" "$1/two" "/dest/"\n'),
            {(self.DEST, "one"), (self.DEST, "two")},
        )

    def test_a_settled_source_keeps_its_settled_name(self) -> None:
        self.assertEqual(
            self.inside('cp /src/one /src/two "/dest/"\n'),
            {(self.DEST, "one"), (self.DEST, "two")},
        )

    def test_a_separator_carried_by_a_name_places_the_source(self) -> None:
        self.assertEqual(
            self.inside('slash=/\ncp "$1/one" "/dest$slash"\n'),
            {(self.DEST, "one")},
        )

    def test_a_leading_terminator_places_the_source(self) -> None:
        self.assertEqual(
            self.inside('cp -- "$1/one" "/dest/"\n'), {(self.DEST, "one")}
        )

    def test_a_source_that_names_no_file_is_reported_unplaceable(self) -> None:
        for source in ('"$1/."', '"$1/.."', '"$1/$2"'):
            with self.subTest(source=source):
                body = f'cp {source} "/dest/"\n'
                self.assertEqual(self.inside(body), set())
                self.assertTrue(self.unplaceable(body))

    def test_a_destination_written_without_a_separator_places_nothing(self) -> None:
        body = 'cp "$1/one" "/dest"\n'
        self.assertEqual(self.inside(body), set())
        self.assertFalse(self.unplaceable(body))

    def test_an_option_bearing_command_places_nothing(self) -> None:
        for written in (
            'cp -T "$1/one" "/dest/"',
            'cp --no-target-directory "$1/one" "/dest/"',
            'cp --parents "$1/one" "/dest/"',
            'install -d "$1/one" "/dest/"',
            'install -D "$1/one" "/dest/"',
            'cp "$1/one" -- "/dest/"',
            'mv "$1/one" "/dest/"',
            'ln "$1/one" "/dest/"',
        ):
            with self.subTest(written=written):
                body = written + "\n"
                self.assertEqual(self.inside(body), set())
                self.assertFalse(self.unplaceable(body))

    def test_a_deferred_body_places_nothing(self) -> None:
        """No written call site says which values an unmodelled body holds.

        The separator such a body writes is read against the values every
        binding place in the fixture holds, which is a different model from
        the one this reading proves its destination against, so a deferred
        operation keeps the reading it already had.
        """

        fixture = self.build(
            "seed() {\n"
            '  cp "$1/one" "/dest/"\n'
            "}\n"
            "trap seed USR1\n"
        )
        placed = set()
        unplaceable = False
        bodies = copier_fixture_validator._deferred_bodies(fixture)
        self.assertTrue(bodies, "the fixture writes no unmodelled body")
        for declaration in bodies:
            for operation in (
                copier_fixture_validator._deferred_operations(fixture, declaration)
                or ()
            ):
                _created, inside, _words, unknown = (
                    copier_fixture_validator._helper_paths(fixture, operation)
                )
                placed |= set(inside)
                unplaceable = unplaceable or unknown
        self.assertEqual(placed, set())
        self.assertFalse(unplaceable)

    def test_a_target_directory_option_keeps_its_own_placement(self) -> None:
        self.assertEqual(
            self.inside('cp -t "/dest/" "$1/one"\n'), {(self.DEST, "one")}
        )

    def test_an_unresolved_option_word_places_nothing(self) -> None:
        body = 'cp $opt "$1/one" "/dest/"\n'
        self.assertEqual(self.inside(body), set())
        self.assertTrue(self.unplaceable(body))

    def test_an_unreadable_destination_places_nothing(self) -> None:
        for body in (
            'empty=\ncp "$1/one" "$empty/dest/"\n',
            'cp "$1/one" "$(printf %s /dest)/"\n',
        ):
            with self.subTest(body=body):
                self.assertEqual(self.inside(body), set())
                self.assertTrue(self.unplaceable(body))

    def test_a_path_reading_never_takes_the_option_empty_value(self) -> None:
        """The value option classification supplies settles no path here."""

        fixture = self.build('empty=\ncp "$1/one" "$empty/dest/"\n')
        operation = next(
            operation
            for operation in fixture.operations
            if copier_fixture_validator._command_index(
                copier_fixture_validator._word_literals(
                    copier_fixture_validator._operation_words(operation)
                ),
                copier_fixture_validator.HELPER_WRITING_COMMANDS,
            )
            >= 0
        )
        self.assertEqual(
            copier_fixture_validator._resolved_word_texts(
                fixture, operation, '"$empty/dest/"'
            ),
            ("/dest/",),
        )
        self.assertIsNone(
            copier_fixture_validator._path_forms(
                fixture, operation, '"$empty/dest/"'
            )
        )

    def test_mixed_separator_forms_place_nothing(self) -> None:
        body = (
            "seed() {\n"
            '  cp "$3/one" "/dest/$1"\n'
            "}\n"
            'seed "two/"\n'
            "seed two\n"
        )
        self.assertEqual(self.inside(body), set())

    def test_agreeing_separator_forms_place_every_destination(self) -> None:
        body = (
            "seed() {\n"
            '  cp "$3/one" "/dest/$1"\n'
            "}\n"
            'seed "two/"\n'
            'seed "three/"\n'
        )
        self.assertEqual(
            self.inside(body),
            {
                ((True, ("dest", "two")), "one"),
                ((True, ("dest", "three")), "one"),
            },
        )


class AlternatePathTest(ContractSupportTest):
    def test_second_copier_update_path_during_the_child_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                'rm -f "$release_file"\n\nrelease_waited=0',
                'rm -f "$release_file"\n'
                'run_copier update -q --defaults --vcs-ref v1.4.5 "$project"\n\n'
                'release_waited=0',
            ),
            RULE_ALTERNATE_PATH,
            "second Copier update path",
        )

    def test_second_copier_update_path_through_a_variable_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                'wait "$update_pid"\n',
                'alternate="$project/.project-agent-workflow/scripts/update-from-copier.sh"\n'
                '"$alternate" --defaults --vcs-ref v1.4.4\n'
                'wait "$update_pid"\n',
            ),
            RULE_ALTERNATE_PATH,
            "second Copier update path",
        )

    def test_an_indirect_second_update_path_is_rejected(self) -> None:
        wrapper = "$project/.project-agent-workflow/scripts/update-from-copier.sh"
        for inserted in (
            f'timeout 60 "{wrapper}" --defaults\n',
            f'sh -c "{wrapper}"\n',
            f'run_w() {{\n  "$1" --defaults\n}}\nrun_w "{wrapper}"\n',
            f'run_w() {{\n  "$@"\n}}\nrun_w "{wrapper}" --defaults\n',
        ):
            with self.subTest(inserted=inserted.splitlines()[-1]):
                self.assert_rejected(
                    self.mutate(
                        'wait "$update_pid"\n', inserted + 'wait "$update_pid"\n'
                    ),
                    RULE_ALTERNATE_PATH,
                    "second Copier update path",
                )

    def test_a_helper_running_an_unrelated_path_is_accepted(self) -> None:
        self.assert_accepted(
            COMPLIANT + 'run_w() {\n  "$1" --check\n}\nrun_w "$project/report.sh"\n'
        )

    def test_naming_the_update_wrapper_is_not_an_update_path(self) -> None:
        wrapper = "$project/.project-agent-workflow/scripts/update-from-copier.sh"
        for named in (
            f'test -x "{wrapper}"\n',
            f'wrapper="{wrapper}"\ntest -x "$wrapper"\n',
            'grep -q "update-from-copier.sh" "$project/manifest.txt"\n',
            'note="copier update finished"\necho "$note" >&2\n',
        ):
            with self.subTest(named=named.splitlines()[-1]):
                self.assert_accepted(COMPLIANT + named)

    def test_second_copier_update_path_before_the_child_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                '"$project/.project-agent-workflow/scripts/update-from-copier.sh"',
                'run_copier update -q --defaults --vcs-ref v1.4.5 "$project"\n'
                '"$project/.project-agent-workflow/scripts/update-from-copier.sh"',
            ),
            RULE_ALTERNATE_PATH,
            "second Copier update path",
        )

    def test_second_copier_update_path_after_the_reap_is_rejected(self) -> None:
        self.assert_rejected(
            COMPLIANT + 'run_copier update -q --defaults --vcs-ref v1.4.5 "$project"\n',
            RULE_ALTERNATE_PATH,
            "second Copier update path",
        )


class AlternatePathDestinationTest(ContractSupportTest):
    """Cover the destination the alternate-path prohibition is bounded to."""

    OTHER = "$tmp/other-project"
    module = copier_fixture_validator

    def fixture(self, source: str):
        records = self.module.shell_lexical.project(source)
        table = self.module.shell_functions.derive(records)
        graph = self.module.shell_execution.derive(records, table)
        return self.module._Fixture(source, records, table, graph)

    def assert_second_path_rejected(self, inserted: str) -> None:
        self.assert_rejected(
            COMPLIANT + inserted, RULE_ALTERNATE_PATH, "second Copier update path"
        )

    def test_a_renamed_wrapper_reaching_the_same_project_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            '"$project/.project-agent-workflow/scripts/run-copier-update.sh" --force\n'
        )

    def test_an_alias_directory_reaching_the_same_project_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'alias_dir="$project/.project-agent-workflow/scripts"\n'
            '"$alias_dir/update-from-copier.sh" --defaults\n'
        )

    def test_the_same_destination_written_differently_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'run_copier update -q --defaults --vcs-ref v1.4.5 "$tmp/project"\n'
        )
        self.assert_second_path_rejected(
            'run_copier update -q --defaults --vcs-ref v1.4.5 "$project/"\n'
        )

    def test_an_unproven_destination_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'run_copier update -q --defaults --vcs-ref v1.4.5 "$elsewhere"\n'
        )
        self.assert_second_path_rejected(
            'run_copier update -q --defaults --vcs-ref v1.4.5 "$tmp/$lane"\n'
        )

    def test_an_update_without_a_destination_is_rejected(self) -> None:
        self.assert_second_path_rejected("run_copier update -q --defaults\n")

    def test_a_relative_wrapper_reaching_the_same_project_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            '(cd "$project" && .project-agent-workflow/scripts/update-from-copier.sh)\n'
        )

    def test_an_update_inside_the_same_project_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'run_copier update -q --defaults --vcs-ref v1.4.5 "$project/nested"\n'
        )

    def test_an_update_of_the_enclosing_directory_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'run_copier update -q --defaults --vcs-ref v1.4.5 "$tmp"\n'
        )

    def test_an_update_behind_an_unknown_option_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'run_copier update --unknown-option value "$tmp/other-project"\n'
        )

    def test_an_expanded_subcommand_reaching_the_same_project_is_rejected(
        self,
    ) -> None:
        self.assert_second_path_rejected(
            'verb=update\nrun_copier "$verb" -q --defaults "$project"\n'
        )

    def test_the_same_destination_spelled_with_segments_is_rejected(self) -> None:
        for written in (
            "$tmp/./project",
            "$tmp//project",
            "$tmp/other/../project",
            "$project/.",
        ):
            with self.subTest(written=written):
                self.assert_second_path_rejected(
                    f'run_copier update -q --defaults "{written}"\n'
                )

    def test_a_destination_above_an_expansion_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'run_copier update -q --defaults "$tmp/../elsewhere"\n'
        )

    def test_an_assignment_in_front_of_the_command_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'dest="$project"\n'
            'dest="$tmp/other-project" run_copier update -q --defaults "$dest"\n'
        )

    def test_an_assignment_carried_across_a_continuation_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'dest="$project"\n'
            'dest="$tmp/other-project" \\\n'
            '  run_copier update -q --defaults "$dest"\n'
        )

    def test_an_assignment_in_front_of_another_command_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'dest="$project"\n'
            'dest="$tmp/other-project" /bin/true\n'
            'run_copier update -q --defaults "$dest"\n'
        )

    def test_an_unmodelled_destination_word_is_rejected(self) -> None:
        for written in ("$tmp/pro\\ject", "//$tmp/project", "$tmp/proj*"):
            with self.subTest(written=written):
                self.assert_second_path_rejected(
                    f"run_copier update -q --defaults {written}\n"
                )

    def test_a_linked_destination_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'ln -s "$project" "$tmp/project-alias"\n'
            'run_copier update -q --defaults "$tmp/project-alias"\n'
        )

    def test_a_link_that_may_hold_the_destination_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'ln -s "$tmp/elsewhere" "$tmp"\n'
            'run_copier update -q --defaults "$tmp/other-project"\n'
        )

    def test_a_copied_link_reaching_the_same_project_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'cp -s "$project" "$tmp/project-copy-alias"\n'
            'run_copier update -q --defaults "$tmp/project-copy-alias"\n'
        )

    def test_a_link_written_inside_a_destination_is_rejected(self) -> None:
        """An update walks into the directory it changes, so a link under it redirects the walk."""

        self.assert_second_path_rejected(
            'ln -s "$tmp/elsewhere" "$tmp/other-project/note"\n'
            'run_copier update -q --defaults "$tmp/other-project"\n'
        )
        self.assert_second_path_rejected(
            'ln -s "$tmp/elsewhere" "$project/note"\n'
            'run_copier update -q --defaults "$tmp/other-project"\n'
        )

    def test_a_link_that_redirects_an_installed_workflow_is_rejected(self) -> None:
        """The boundary segment the destination is derived from may itself be an alias."""

        self.assert_second_path_rejected(
            'other="$tmp/other"\n'
            'ln -s "$project/.project-agent-workflow" '
            '"$other/.project-agent-workflow"\n'
            '"$other/.project-agent-workflow/scripts/update-from-copier.sh" '
            "--defaults\n"
        )

    def test_an_escaped_quote_in_an_option_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'run_copier update --exclude "key=value\\" $tmp/other-project '
            '--vcs-ref " "$project"\n'
        )

    def test_an_assignment_behind_a_redirection_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'dest="$project"\n'
            'dest="$tmp/other-project" 3>&1 run_copier update -q --defaults "$dest"\n'
        )

    def test_a_link_command_written_as_a_path_is_rejected(self) -> None:
        for written in ('/usr/bin/ln -s', 'env ln -s'):
            with self.subTest(written=written):
                self.assert_second_path_rejected(
                    f'{written} "$project" "$tmp/other-project"\n'
                    'run_copier update -q --defaults "$tmp/other-project"\n'
                )

    def test_an_escaped_separator_is_not_a_separator(self) -> None:
        for written in (">\\&", ">\\;", ">\\|"):
            with self.subTest(written=written):
                self.assert_second_path_rejected(
                    'dest="$project"\n'
                    f'dest="$tmp/other-project" {written} '
                    'run_copier update -q --defaults "$dest"\n'
                )

    def test_a_separator_still_ends_a_prefix_assignment(self) -> None:
        self.assert_accepted(
            COMPLIANT
            + 'dest="$tmp/other-project" && '
            + 'run_copier update -q --defaults "$dest"\n'
        )

    def test_an_assignment_that_runs_in_its_own_shell_proves_no_destination(
        self,
    ) -> None:
        """A backgrounded assignment gives the writing shell no value."""

        self.assert_second_path_rejected(
            'dest="$tmp/other-project" & '
            'run_copier update -q --defaults "$dest"\n'
        )

    def test_a_quoted_link_command_is_rejected(self) -> None:
        for written in ("l''n -s", 'l""n -s', "nice -n 1 ln -s"):
            with self.subTest(written=written):
                self.assert_second_path_rejected(
                    f'{written} "$project" "$tmp/other-project"\n'
                    'run_copier update -q --defaults "$tmp/other-project"\n'
                )

    def test_a_continued_link_command_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'l\\\nn -s "$project" "$tmp/other-project"\n'
            'run_copier update -q --defaults "$tmp/other-project"\n'
        )

    def test_an_unread_link_command_is_rejected(self) -> None:
        for written in (
            "${link_command:-ln} -s",
            "$(printf %s ln) -s",
            '"$linker" --symbolic',
        ):
            with self.subTest(written=written):
                self.assert_second_path_rejected(
                    f'{written} "$project" "$tmp/other-project"\n'
                    'run_copier update -q --defaults "$tmp/other-project"\n'
                )

    def test_an_unread_command_is_not_read_as_a_link(self) -> None:
        """The run carries no alias, and its bare operands settle no name."""

        source = (
            COMPLIANT
            + '"$reporter" --defaults "$project" "$tmp/other-project"\n'
            + 'run_copier update -q --defaults "$tmp/other-project"\n'
        )
        links, unplaced = self.module._symlinked_paths(self.fixture(source))
        self.assertEqual(links, frozenset())
        self.assertFalse(unplaced)
        self.assert_second_path_rejected(
            '"$reporter" --defaults "$project" "$tmp/other-project"\n'
            'run_copier update -q --defaults "$tmp/other-project"\n'
        )

    def test_a_launched_link_command_is_rejected(self) -> None:
        for written in (
            "command ${link_command:-ln} -s",
            "env $(printf %s ln) -s",
            "command ln -s",
        ):
            with self.subTest(written=written):
                self.assert_second_path_rejected(
                    f'{written} "$project" "$tmp/project-alias"\n'
                    '"$tmp/project-alias/.project-agent-workflow/scripts'
                    '/update-from-copier.sh" --defaults\n'
                )

    def test_a_launched_ordinary_command_is_not_a_link(self) -> None:
        self.assert_accepted(
            COMPLIANT
            + 'git -C "$project" commit -s -m note\n'
            + 'run_copier update -q --defaults "$tmp/other-project"\n'
        )

    def test_an_update_of_another_project_is_accepted(self) -> None:
        self.assert_accepted(
            COMPLIANT
            + f'run_copier update -q --defaults --vcs-ref v1.4.5 "{self.OTHER}"\n'
        )

    def test_a_relative_wrapper_is_placed_by_its_subshell_directory(self) -> None:
        """The subshell writes the directory, so the wrapper reaches it."""

        self.assert_accepted(
            COMPLIANT
            + f'(cd "{self.OTHER}" && '
            ".project-agent-workflow/scripts/update-from-copier.sh)\n"
        )

    def test_a_relative_wrapper_reaching_the_child_is_rejected(self) -> None:
        """A settled subshell directory places the wrapper on the child."""

        self.assert_second_path_rejected(
            '(cd "$project" && '
            ".project-agent-workflow/scripts/update-from-copier.sh)\n"
        )

    def test_a_wrapper_held_in_a_name_is_rejected(self) -> None:
        """The command word writes no marker, so the settled path is read."""

        self.assert_second_path_rejected(
            'wrapper="$project/.project-agent-workflow/scripts'
            '/update-from-copier.sh"\n'
            '"$wrapper" --defaults\n'
        )

    def test_a_helper_that_updates_the_same_project_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            "run_copier() {\n  copier update -q \"$project\"\n}\n"
            'run_copier update -q "$tmp/other-project"\n'
        )

    def test_an_attached_option_value_keeps_the_destination_read(self) -> None:
        self.assert_second_path_rejected(
            'run_copier update --vcs-ref=v1.4.5 "$project"\n'
        )
        self.assert_accepted(
            COMPLIANT
            + f'run_copier update --vcs-ref=v1.4.5 "{self.OTHER}"\n'
        )

    def test_an_option_terminator_keeps_the_destination_read(self) -> None:
        self.assert_second_path_rejected('run_copier update -q -- "$project"\n')
        self.assert_accepted(
            COMPLIANT + f'run_copier update -q -- "{self.OTHER}"\n'
        )

    def test_an_option_cluster_this_checker_does_not_read_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            f'run_copier update -qf "{self.OTHER}"\n'
        )

    def test_an_option_held_in_a_name_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            f'flag=-q\nrun_copier update "$flag" "{self.OTHER}"\n'
        )

    def test_a_destination_a_branch_may_change_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            'dest="$project"\n'
            f'if [ -d /tmp ]; then dest="{self.OTHER}"; fi\n'
            'run_copier update -q "$dest"\n'
        )

    def test_a_destination_a_loop_binds_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            f'for dest in "$project" "{self.OTHER}"; do\n'
            '  run_copier update -q "$dest"\n'
            "done\n"
        )

    def test_an_alias_above_another_project_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            f'ln -s "$project" "$tmp"\nrun_copier update -q "{self.OTHER}"\n'
        )

    def test_an_alias_naming_another_project_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            f'ln -s "$project" "{self.OTHER}"\n'
            f'run_copier update -q "{self.OTHER}"\n'
        )

    def test_an_alias_moved_onto_another_project_is_rejected(self) -> None:
        self.assert_second_path_rejected(
            f'ln -s "$project" "$tmp/a"\nmv "$tmp/a" "{self.OTHER}"\n'
            f'run_copier update -q "{self.OTHER}"\n'
        )

    def test_a_wrapper_run_through_a_launcher_is_rejected(self) -> None:
        for written in ("sh", "env"):
            with self.subTest(written=written):
                self.assert_second_path_rejected(
                    f'{written} "$project/.project-agent-workflow/scripts'
                    '/update-from-copier.sh" --defaults\n'
                )

    def test_the_committed_runtime_keeps_passing_the_check(self) -> None:
        """Plan 227 completed the transition this rule is reached through."""

        source = (ROOT / "tests" / "copier-update.sh").read_text(encoding="utf-8")
        self.assertEqual(check(source), ())
        self.assertTrue(self.module._is_transition(self.fixture(source)))

    def test_a_copy_naming_an_update_source_is_not_an_update(self) -> None:
        self.assert_accepted(
            COMPLIANT
            + 'update_source="$tmp/source"\n'
            f'run_copier copy -q --vcs-ref v1.4.5 "$update_source" "{self.OTHER}"\n'
        )


class CopierWriteTest(ContractSupportTest):
    """Cover the Copier writes that replace the destination the child updates.

    A copy and a recopy are not updates, so the alternate-path prohibition never
    reads them. They still write a whole project, so a write proven to reach the
    sanctioned destination is rejected everywhere except the one creation the
    fixture must perform before it starts the update child.
    """

    OTHER = "$tmp/other-project"
    MESSAGE = "unmodelled Copier copy path"
    CHILD = '"$project/.project-agent-workflow/scripts/update-from-copier.sh"'

    def assert_write_rejected(self, source: str) -> None:
        self.assert_rejected(source, RULE_ALTERNATE_PATH, self.MESSAGE)

    def before_the_child(self, inserted: str) -> str:
        return self.mutate(self.CHILD, inserted + self.CHILD)

    def test_a_copy_into_the_sanctioned_destination_is_rejected(self) -> None:
        self.assert_write_rejected(
            COMPLIANT
            + 'run_copier copy -q -f --vcs-ref v1.4.5 "$update_source" "$project"\n'
        )

    def test_a_recopy_of_the_sanctioned_destination_is_rejected(self) -> None:
        self.assert_write_rejected(
            COMPLIANT + 'run_copier recopy -q -f --vcs-ref v1.4.5 "$project"\n'
        )

    def test_a_copy_written_differently_is_rejected(self) -> None:
        for written in ("$tmp/project", "$project/", "$tmp/./project", "$project/."):
            with self.subTest(written=written):
                self.assert_write_rejected(
                    COMPLIANT
                    + f'run_copier copy -q -f "$update_source" "{written}"\n'
                )

    def test_a_copy_inside_the_sanctioned_destination_is_rejected(self) -> None:
        self.assert_write_rejected(
            COMPLIANT + 'run_copier copy -q -f "$update_source" "$project/nested"\n'
        )

    def test_a_copy_of_the_enclosing_directory_is_rejected(self) -> None:
        self.assert_write_rejected(
            COMPLIANT + 'run_copier copy -q -f "$update_source" "$tmp"\n'
        )

    def test_a_copy_behind_a_launcher_is_rejected(self) -> None:
        self.assert_write_rejected(
            COMPLIANT + 'env run_copier copy -q -f "$update_source" "$project"\n'
        )

    def test_a_copy_into_a_separate_project_is_accepted(self) -> None:
        self.assert_accepted(
            COMPLIANT
            + f'run_copier copy -q -f "$update_source" "{self.OTHER}"\n'
            + f'run_copier recopy -q -f "{self.OTHER}"\n'
        )

    def test_a_destination_that_does_not_settle_is_accepted(self) -> None:
        """The committed fixture copies into a lane path no written text settles."""

        self.assert_accepted(
            COMPLIANT
            + 'for out in "$tmp/a" "$project"; do\n'
            '  run_copier copy -q -f "$update_source" "$out"\n'
            "done\n"
        )

    def test_a_destination_one_call_site_settles_is_read(self) -> None:
        """A parameter carries the destination its call site writes.

        The copy is reported because the call site names the sanctioned
        destination, which the body reaches through its first parameter.
        """

        self.assert_rejected(
            COMPLIANT
            + "write_lane() {\n"
            '  run_copier copy -q -f "$update_source" "$1"\n'
            "}\n"
            'write_lane "$project"\n',
            RULE_ALTERNATE_PATH,
            "an unmodelled Copier copy path writes the sanctioned destination",
        )

    def test_an_expansion_where_the_paths_differ_is_rejected(self) -> None:
        """An expansion written there may still name the sanctioned project."""

        self.assert_write_rejected(
            COMPLIANT + 'run_copier copy -q -f "$update_source" "$tmp/$lane"\n'
        )

    def test_an_unsettled_segment_under_the_destination_is_rejected(self) -> None:
        """The written prefix already places the copy inside the sanctioned project."""

        self.assert_write_rejected(
            COMPLIANT + 'run_copier copy -q -f "$update_source" "$project/$lane"\n'
        )

    def test_a_destination_no_written_text_anchors_is_rejected(self) -> None:
        """An unanchored path is placed by the working directory, not by the text."""

        for written in ('"$elsewhere"', '"$lane/project"', "project"):
            with self.subTest(written=written):
                self.assert_write_rejected(
                    COMPLIANT + f'run_copier copy -q -f "$update_source" {written}\n'
                )

    def test_a_child_destination_the_checker_cannot_read_reserves_every_copy(
        self,
    ) -> None:
        """An unread child destination must not switch the whole rule off."""

        unread = self.mutate(
            "$project/.project-agent-workflow",
            "$candidate_path/.project-agent-workflow",
        )
        self.assert_write_rejected(
            unread + f'run_copier copy -q -f "$update_source" "{self.OTHER}"\n'
        )

    def test_an_unread_option_leaves_the_destination_unread(self) -> None:
        self.assert_accepted(
            COMPLIANT
            + 'run_copier copy --unknown-option value "$update_source" "$project"\n'
        )

    def test_an_unread_operand_count_leaves_the_destination_unread(self) -> None:
        self.assert_accepted(COMPLIANT + 'run_copier copy -q -f "$project"\n')
        self.assert_accepted(
            COMPLIANT + 'run_copier recopy -q -f "$update_source" "$project"\n'
        )

    def test_an_unread_subcommand_is_not_a_copy(self) -> None:
        self.assert_accepted(
            COMPLIANT + 'run_copier clone -q -f "$update_source" "$project"\n'
        )

    def test_the_modelled_creation_before_the_child_is_accepted(self) -> None:
        self.assert_accepted(
            self.before_the_child(
                'run_copier copy -q -f --vcs-ref v1.4.4 "$update_source" "$project"\n'
            )
        )

    def test_a_second_creation_before_the_child_is_rejected(self) -> None:
        self.assert_write_rejected(
            self.before_the_child(
                'run_copier copy -q -f --vcs-ref v1.4.4 "$update_source" "$project"\n'
                'run_copier copy -q -f --vcs-ref v1.4.4 "$update_source" "$project"\n'
            )
        )

    def test_a_creation_before_the_child_keeps_a_later_copy_rejected(self) -> None:
        self.assert_write_rejected(
            self.before_the_child(
                'run_copier copy -q -f --vcs-ref v1.4.4 "$update_source" "$project"\n'
            )
            + 'run_copier recopy -q -f "$project"\n'
        )

    def test_a_fixture_without_a_transition_reads_no_copy(self) -> None:
        self.assert_accepted(
            WITHOUT_TRANSITION
            + 'run_copier copy -q -f "$update_source" "$project"\n'
        )

    def test_a_copy_in_a_body_written_before_the_child_is_rejected(self) -> None:
        self.assert_write_rejected(
            self.before_the_child(
                "recreate() {\n"
                '  run_copier copy -q -f "$update_source" "$project"\n'
                "}\n"
            )
            + "recreate\n"
        )

    def test_an_uncalled_body_written_before_the_child_is_accepted(self) -> None:
        self.assert_accepted(
            self.before_the_child(
                "recreate() {\n"
                '  run_copier copy -q -f "$update_source" "$project"\n'
                "}\n"
            )
        )

    def test_a_copy_in_a_loop_that_reaches_the_child_is_rejected(self) -> None:
        self.assert_write_rejected(
            self.mutate(
                self.CHILD,
                "for attempt in one two; do\n"
                '  run_copier copy -q -f "$update_source" "$project"\n'
                "  " + self.CHILD,
            )
            + "done\n"
        )

    def test_a_copy_in_a_region_that_ends_before_the_child_is_accepted(self) -> None:
        self.assert_accepted(
            self.before_the_child(
                "if [ -d /tmp ]; then\n"
                '  run_copier copy -q -f "$update_source" "$project"\n'
                "fi\n"
            )
        )


class ResolutionAuthorityTest(ContractSupportTest):
    """Cover the resolution model as the single authority on what runs an update."""

    WRAPPER = "$other/.project-agent-workflow/scripts/update-from-copier.sh"

    def assert_second_path_rejected(self, inserted: str) -> None:
        self.assert_rejected(
            COMPLIANT + 'other="$tmp/other"\n' + inserted,
            RULE_ALTERNATE_PATH,
            "second Copier update path",
        )

    def test_a_wrapper_inside_an_interpreter_string_is_rejected(self) -> None:
        """The words of the run say nothing about what the string runs."""

        self.assert_second_path_rejected(
            "sh -c '\"$1/.project-agent-workflow/scripts/update-from-copier.sh\" "
            '--defaults\' _ "$other"\n'
        )

    def test_a_wrapper_behind_a_command_prefix_is_rejected(self) -> None:
        """A prefix that is no launcher still runs the word written after it."""

        self.assert_second_path_rejected('nice "%s" --defaults\n' % self.WRAPPER)

    def test_a_wrapper_a_helper_forwards_is_rejected(self) -> None:
        """A helper that runs one of its own arguments runs what the call site writes."""

        self.assert_second_path_rejected(
            "runit() {\n"
            '  "$1" --defaults\n'
            "}\n"
            'runit "%s"\n' % self.WRAPPER
        )

    def test_a_wrapper_a_helper_interprets_is_rejected(self) -> None:
        """A helper that runs an interpreter on its arguments runs the written script."""

        self.assert_second_path_rejected(
            "runsh() {\n  sh \"$1\"\n}\n" 'runsh "%s"\n' % self.WRAPPER
        )

    def test_an_update_carried_by_an_expansion_is_rejected(self) -> None:
        """A command word this checker never reads still carries the subcommand."""

        self.assert_second_path_rejected(
            "tool=copier\n" '"$tool" update -q --defaults "$other"\n'
        )

    def test_a_copy_whose_operands_write_the_update_word_is_accepted(self) -> None:
        """A copy is proved to be no update, so the words its operands write are read only as paths."""

        self.assert_accepted(
            COMPLIANT
            + 'src="$tmp/update-source"\n'
            'out="$tmp/other-update"\n'
            'run_copier copy -q -f --vcs-ref v1.2.1 "$src" "$out"\n'
        )

    def test_an_update_of_a_separate_project_stays_accepted(self) -> None:
        self.assert_accepted(
            COMPLIANT
            + 'out="$tmp/other"\n'
            'run_copier update -q --defaults "$out"\n'
        )

    def test_a_non_update_script_of_an_installed_workflow_is_accepted(self) -> None:
        """A script of an installed workflow runs an update only when its name says so."""

        self.assert_accepted(
            COMPLIANT
            + 'other="$tmp/other"\n'
            '"$other/.project-agent-workflow/scripts/context-compress.sh" doc tag\n'
        )
        self.assert_accepted(
            COMPLIANT + ".project-agent-workflow/scripts/context-compress.sh doc tag\n"
        )

    def test_an_update_script_of_an_installed_workflow_is_still_read(self) -> None:
        """A name that writes both marks keeps its unanchored destination unproven."""

        self.assert_second_path_rejected(
            ".project-agent-workflow/scripts/run-copier-update.sh --force\n"
        )

    def test_a_script_name_written_by_an_expansion_is_unproven(self) -> None:
        """A name this checker cannot read may be the update wrapper itself."""

        self.assert_second_path_rejected(
            ".project-agent-workflow/scripts/$script --defaults\n"
        )

    def test_a_read_script_name_keeps_its_destination_read(self) -> None:
        """Reading the name settles what runs, not which project it runs against."""

        self.assert_accepted(
            COMPLIANT
            + 'other="$tmp/other"\n'
            "script=update-from-copier.sh\n"
            '"$other/.project-agent-workflow/scripts/$script" --defaults\n'
        )
        self.assert_rejected(
            COMPLIANT
            + "script=update-from-copier.sh\n"
            '"$project/.project-agent-workflow/scripts/$script" --defaults\n',
            RULE_ALTERNATE_PATH,
            "second Copier update path",
        )


class SubshellDirectoryTest(ContractSupportTest):
    """Cover the directory a subshell settles for a relative command word."""

    OTHER = "$tmp/other-project"
    WRAPPER = ".project-agent-workflow/scripts/update-from-copier.sh"

    def assert_second_path_rejected(self, inserted: str) -> None:
        self.assert_rejected(
            COMPLIANT + inserted, RULE_ALTERNATE_PATH, "second Copier update path"
        )

    def test_a_settled_subshell_directory_places_the_wrapper(self) -> None:
        """One directory change written before the word settles the project."""

        self.assert_accepted(
            COMPLIANT + f'(cd "{self.OTHER}" && {self.WRAPPER} --defaults)\n'
        )

    def test_a_settled_subshell_directory_reaching_the_child_is_rejected(
        self,
    ) -> None:
        """The settled directory is the sanctioned child, so the word reaches it."""

        self.assert_second_path_rejected(
            f'(cd "$project" && {self.WRAPPER} --defaults)\n'
        )

    def test_a_wrapper_with_no_subshell_stays_unplaced(self) -> None:
        """Nothing written says which directory the word runs in."""

        self.assert_second_path_rejected(f"{self.WRAPPER} --defaults\n")

    def test_two_directory_changes_leave_the_wrapper_unplaced(self) -> None:
        """A second change leaves no single directory the word runs in."""

        self.assert_second_path_rejected(
            f'(cd "{self.OTHER}" && cd "$tmp" && {self.WRAPPER} --defaults)\n'
        )

    def test_an_unsettled_directory_leaves_the_wrapper_unplaced(self) -> None:
        """A directory this checker cannot place proves no destination."""

        self.assert_second_path_rejected(
            f'(cd "$tmp/$lane" && {self.WRAPPER} --defaults)\n'
        )

    def test_a_relative_directory_leaves_the_wrapper_unplaced(self) -> None:
        """A directory that is not anchored is placed by nothing written."""

        self.assert_second_path_rejected(
            f'(cd other-project && {self.WRAPPER} --defaults)\n'
        )

    def test_a_directory_change_outside_the_subshell_is_unread(self) -> None:
        """A change written outside the subshell settles no directory inside it."""

        self.assert_second_path_rejected(
            f'cd "{self.OTHER}"\n(: && {self.WRAPPER} --defaults)\n'
        )

    def test_a_directory_change_written_after_the_word_is_unread(self) -> None:
        """A change the word never runs under settles no directory for it."""

        self.assert_second_path_rejected(
            f'({self.WRAPPER} --defaults && cd "{self.OTHER}")\n'
        )

    def test_a_directory_change_in_another_branch_is_unread(self) -> None:
        """A change on a separate enclosure path never runs before the word."""

        self.assert_second_path_rejected(
            f'(if [ -d "{self.OTHER}" ]; then cd "{self.OTHER}"; fi\n'
            f"{self.WRAPPER} --defaults)\n"
        )

    def test_a_change_carried_by_a_called_function_leaves_it_unplaced(
        self,
    ) -> None:
        """A called function moves the same directory the word runs in."""

        self.assert_second_path_rejected(
            "goto() {\n  cd \"$1\"\n}\n"
            f'(cd "{self.OTHER}" && goto "$project" && {self.WRAPPER} --force)\n'
        )

    def test_any_other_operation_before_the_word_leaves_it_unplaced(
        self,
    ) -> None:
        """Only a subshell that runs the change alone writes its directory."""

        self.assert_second_path_rejected(
            f'(cd "{self.OTHER}" && : && {self.WRAPPER} --defaults)\n'
        )

    def test_a_sourced_file_before_the_word_leaves_it_unplaced(self) -> None:
        """A sourced file runs in the same shell and may move the directory."""

        self.assert_second_path_rejected(
            f'(cd "{self.OTHER}" && . "$tmp/lib.sh" && {self.WRAPPER})\n'
        )

    def test_a_change_written_after_the_word_leaves_it_unplaced(self) -> None:
        """A later change still runs before the word on a second turn."""

        self.assert_second_path_rejected(
            f'(cd "{self.OTHER}" && {self.WRAPPER} && cd "$project")\n'
        )

    def test_a_change_carried_by_a_loop_leaves_the_word_unplaced(self) -> None:
        """The second turn of the loop runs the word in the changed directory."""

        self.assert_second_path_rejected(
            f'o="{self.OTHER}"\n(cd "$o"\n'
            f'for i in 1 2; do {self.WRAPPER} --force; cd "$project"; done)\n'
        )

    def test_a_repeated_word_leaves_it_unplaced(self) -> None:
        """A word one loop may run again is placed by no single directory."""

        self.assert_second_path_rejected(
            f'(cd "{self.OTHER}"\nfor i in 1 2; do {self.WRAPPER} --force; done)\n'
        )

    def test_a_word_repeated_by_a_loop_condition_is_unplaced(self) -> None:
        """A loop condition runs again under the directory the body left."""

        self.assert_second_path_rejected(
            f'o="{self.OTHER}"\n'
            f'while (cd "$o" && {self.WRAPPER} --force); do o="$project"; done\n'
        )

    def test_a_branch_condition_still_places_the_word(self) -> None:
        """A branch condition runs once, so its subshell settles a directory."""

        self.assert_accepted(
            COMPLIANT
            + f'if (cd "{self.OTHER}" && {self.WRAPPER} --force); then :; fi\n'
        )


class ShadowedAssignmentTest(ContractSupportTest):
    """A written override must not hide an operation that still runs."""

    SNAPSHOT = "$project/scripts/snapshot-validation-witness-provenance.py"
    WRAPPER = "$out/.project-agent-workflow/scripts/update-from-copier.sh"
    SHADOWS = (
        "if false; then {name}=/bin/true; fi\n",
        "false && {name}=/bin/true\n",
        "( {name}=/bin/true )\n",
        "true | {name}=/bin/true\n",
        "shadow_it() {{\n  {name}=/bin/true\n}}\n",
        'if [ -n "$override" ]; then\n  {name}="$override"\nfi\n',
        'if [ -n "$override" ]; then {name}="${name}"; fi\n',
        "for turn in 1 2; do\n  {name}=/bin/true\ndone\n",
    )

    def test_a_shadowed_snapshot_dispatch_is_rejected(self) -> None:
        for shadow in self.SHADOWS:
            with self.subTest(shadow=shadow.splitlines()[0]):
                self.assert_rejected(
                    COMPLIANT
                    + f'snap="{self.SNAPSHOT}"\n'
                    + shadow.format(name="snap")
                    + 'python3 "$snap" --stage before\n',
                    RULE_DIRECT_INVOCATION,
                    "invokes the migration snapshot script directly",
                )

    def test_a_shadowed_update_path_is_rejected(self) -> None:
        for shadow in self.SHADOWS:
            with self.subTest(shadow=shadow.splitlines()[0]):
                self.assert_rejected(
                    COMPLIANT
                    + f'alt="{self.WRAPPER}"\n'
                    + shadow.format(name="alt")
                    + '"$alt" --defaults --vcs-ref v1.4.4\n',
                    RULE_ALTERNATE_PATH,
                    "second Copier update path",
                )

    def test_an_override_written_where_it_certainly_runs_replaces_the_value(self) -> None:
        self.assert_accepted(
            COMPLIANT
            + f'snap="{self.SNAPSHOT}"\nsnap=/bin/true\npython3 "$snap" --stage before\n'
        )

    def test_a_shadowed_name_that_is_only_named_stays_accepted(self) -> None:
        self.assert_accepted(
            COMPLIANT
            + f'snap="{self.SNAPSHOT}"\n'
            + 'if false; then snap=/bin/true; fi\n'
            + 'test -f "$snap"\n'
        )

    def test_the_expansion_count_stays_bounded(self) -> None:
        names = {
            name: tuple(f"value-{name}{turn}" for turn in range(4))
            for name in ("a", "b", "c", "d")
        }
        bounded = copier_fixture_validator._expand_all("run $a $b $c $d", names)
        self.assertEqual(len(bounded.texts), 1)
        self.assertFalse(bounded.exact)
        for name, values in names.items():
            for value in values:
                self.assertIn(value, bounded.texts[0])
        product = copier_fixture_validator._expand_all(
            "run $a $b", {name: names[name] for name in ("a", "b")}
        )
        self.assertEqual(len(product.texts), 16)
        self.assertTrue(product.exact)


if __name__ == "__main__":
    unittest.main()
