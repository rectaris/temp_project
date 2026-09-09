"""Shell word, name binding, alias, and command shadowing tests."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


if __spec__ is None or not __spec__.parent:  # allow direct execution of this module
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from copier_fixture_validator.support import (
    COMPLIANT,
    ContractSupportTest,
    ROOT,
    RULE_COMMAND_SHADOWING,
    RULE_STRUCTURE,
    check,
    copier_fixture_validator,
    shell_execution,
    shell_functions,
    shell_lexical,
)



class CommandShadowingTest(ContractSupportTest):
    """The commands a bound observation runs may not be rebound.

    Every other rule reads the written text of an operation, so a fixture that
    keeps that text and gives the command name another meaning makes the
    observation vacuous. A shell rebinds a command name through a function
    declaration, an alias, a `hash` entry, or a file a search-path lookup
    reaches first, and each of them is covered here for every protected name.
    """

    # A persistent search-path assignment is what makes a written file the
    # command a bare name resolves to, so the helper cases carry one.
    SEARCHED = (
        '\nmkdir -p "$tmp/bin"\n'
        'PATH="$tmp/bin:$PATH"\n'
        "export PATH\n"
    )

    def observed(self) -> list[str]:
        return sorted(copier_fixture_validator.OBSERVED_COMMANDS)

    def declarable(self) -> list[str]:
        return [name for name in self.observed() if name.isidentifier()]

    def helpers(self) -> list[str]:
        return sorted(copier_fixture_validator.SHADOWED_HELPER_COMMANDS)

    def searched(self, addition: str) -> str:
        return COMPLIANT + self.SEARCHED + addition

    def test_the_release_commands_are_protected(self) -> None:
        self.assertLessEqual(
            copier_fixture_validator.RELEASE_COMMANDS,
            copier_fixture_validator.OBSERVED_COMMANDS,
        )

    def test_only_the_builtin_names_are_exempt_from_the_helper_reading(self) -> None:
        """A name the shell resolves before it searches is not shadowed by a file."""

        self.assertEqual(
            copier_fixture_validator.OBSERVED_COMMANDS
            - copier_fixture_validator.SHADOWED_HELPER_COMMANDS,
            copier_fixture_validator.OBSERVED_BUILTINS,
        )
        self.assertLessEqual(
            copier_fixture_validator.OBSERVED_BUILTINS,
            copier_fixture_validator.OBSERVED_COMMANDS,
        )

    def test_the_reproduced_admission_is_rejected(self) -> None:
        mutated = COMPLIANT + "\ngrep() { :; }\ntest() { :; }\ntouch() { :; }\n"
        rejected = [
            finding.message
            for finding in check(mutated)
            if finding.rule == RULE_COMMAND_SHADOWING
        ]
        self.assertEqual(len(rejected), 3, self.messages(mutated))

    def test_declaring_each_observed_command_is_rejected(self) -> None:
        for name in self.declarable():
            with self.subTest(command=name):
                self.assert_rejected(
                    COMPLIANT + f"\n{name}() {{\n  :\n}}\n",
                    RULE_COMMAND_SHADOWING,
                    f"declares `{name}` as a function",
                )

    def test_the_names_the_bound_control_flow_runs_are_declarable(self) -> None:
        """The poll bound, the release, and the inventory loop are all rebindable.

        A shell resolves these names before it searches a path, so a helper
        file never reaches them and only the declaration case protects them.
        """

        for name in ("read", "exit", "trap", "cd", "wait", "kill"):
            with self.subTest(command=name):
                self.assertIn(name, self.declarable())
                self.assert_rejected(
                    COMPLIANT + f"\n{name}() {{\n  :\n}}\n",
                    RULE_COMMAND_SHADOWING,
                    f"declares `{name}` as a function",
                )

    def test_a_declaration_that_wraps_the_real_command_is_rejected(self) -> None:
        self.assert_rejected(
            COMPLIANT + '\ngrep() {\n  command grep "$@" || true\n}\n',
            RULE_COMMAND_SHADOWING,
            "declares `grep` as a function",
        )

    def test_aliasing_each_observed_command_is_rejected(self) -> None:
        for name in self.observed():
            with self.subTest(command=name):
                self.assert_rejected(
                    COMPLIANT + f"\nalias {name}='true'\n",
                    RULE_STRUCTURE,
                    "`alias`",
                )

    def test_a_helper_named_for_each_observed_command_is_rejected(self) -> None:
        forms = (
            'cat >"$tmp/bin/{name}" <<\'EOF_SHIM\'\n'
            "#!/bin/sh\n"
            "exit 0\n"
            "EOF_SHIM\n",
            'cp "$root/tests/fixtures/helper" "$tmp/bin/{name}"\n',
            'touch "$tmp/bin/{name}"\n',
            'ln -s "$root/tests/fixtures/helper" "$tmp/bin/{name}"\n',
        )
        for name in self.helpers():
            for index, form in enumerate(forms):
                with self.subTest(command=name, form=index):
                    self.assert_rejected(
                        self.searched(form.format(name=name)),
                        RULE_COMMAND_SHADOWING,
                        f"writes a `{name}` helper",
                    )

    def test_a_helper_moved_into_a_searched_directory_is_rejected(self) -> None:
        """A move names its destination directory rather than the written file."""

        self.assert_rejected(
            self.searched('mv "$tmp/staging/grep" "$tmp/bin"\n'),
            RULE_COMMAND_SHADOWING,
            "writes a `grep` helper",
        )

    def test_a_helper_named_through_a_variable_is_rejected(self) -> None:
        self.assert_rejected(
            self.searched('shim_dir="$tmp/bin"\ntouch "$shim_dir/sed"\n'),
            RULE_COMMAND_SHADOWING,
            "writes a `sed` helper",
        )

    def test_a_helper_named_under_an_unplaceable_search_path_is_rejected(self) -> None:
        """A search path this checker cannot place reaches whatever it reaches.

        Exporting a value in one command leaves this checker unable to settle
        the directories the shell will search, so a written file that carries
        an observed name is read as reachable from the name it is written with.
        """

        self.assert_rejected(
            COMPLIANT
            + '\nexport PATH="$tmp/shim:$PATH"\n'
            + 'cp "$root/tests/fixtures/helper" "$tmp/shim/sed"\n',
            RULE_COMMAND_SHADOWING,
            "writes a `sed` helper",
        )

    def test_a_search_path_written_in_front_of_an_observation_is_rejected(self) -> None:
        """A prefixed search path decides what the observation itself runs."""

        self.assert_rejected(
            self.mutate(
                'grep -q \'"state": "consumed"\' "$attempt_state"\n',
                'PATH="$tmp/shim:$PATH" grep -q \'"state": "consumed"\''
                ' "$attempt_state"\n',
            ),
            RULE_COMMAND_SHADOWING,
            "writes a search path in front of `grep`",
        )

    def test_binding_a_command_name_through_hash_is_rejected(self) -> None:
        """A hashed entry is read before the search path the fixture writes."""

        self.assert_rejected(
            COMPLIANT + '\nhash -p "$tmp/true" grep\n',
            RULE_COMMAND_SHADOWING,
            "binds a command name through `hash`",
        )

    def test_the_bracket_test_cannot_be_rebound_at_all(self) -> None:
        """The checked projections close the two remaining vectors for `[`.

        The checked function table admits a declaration only for a name it
        reads as an exact literal word, so `[` is rejected as structure before
        this rule reads it, and the shell resolves `[` before it searches a
        path, so a written file of that name shadows nothing.
        """

        self.assertIn("[", copier_fixture_validator.OBSERVED_COMMANDS)
        self.assertNotIn("[", self.declarable())
        self.assertNotIn("[", self.helpers())
        self.assert_rejected(COMPLIANT + "\n[() {\n  :\n}\n", RULE_STRUCTURE, "")

    def test_a_helper_the_inspection_lane_reaches_by_prefix_is_accepted(self) -> None:
        """A directory reached only in front of one command shadows nothing.

        The fixture writes a deliberately failing `git` helper and reaches it
        by writing the search path in front of the single command that must
        see it, so the shell's own search path never holds that directory.
        """

        self.assert_accepted(
            self.searched(
                'mkdir -p "$tmp/failing-git"\n'
                'cat >"$tmp/failing-git/git" <<\'EOF_FAILING_GIT\'\n'
                "#!/bin/sh\n"
                "exit 7\n"
                "EOF_FAILING_GIT\n"
                'PATH="$tmp/failing-git:$PATH" python3 -c "pass"\n'
            )
        )

    def test_a_git_helper_a_searched_directory_holds_is_rejected(self) -> None:
        """The same helper written where the shell searches is a rebinding."""

        self.assert_rejected(
            self.searched(
                'cat >"$tmp/bin/git" <<\'EOF_GIT\'\n'
                "#!/bin/sh\n"
                "exit 0\n"
                "EOF_GIT\n"
            ),
            RULE_COMMAND_SHADOWING,
            "writes a `git` helper",
        )

    def test_a_helper_written_inside_an_expansion_is_rejected(self) -> None:
        """A command written inside an expansion writes the same file.

        Reading operands from the written command runs alone would leave a
        command the shell runs inside a substitution writing nothing at all.
        """

        for index, form in enumerate(
            (
                'written=$(touch "$tmp/bin/grep")\n',
                'written=$(cat "$root/helper" >"$tmp/bin/grep")\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched(form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )

    def test_a_search_path_written_inside_an_expansion_is_rejected(self) -> None:
        self.assert_rejected(
            self.searched('found=$(PATH="$tmp/shim:$PATH" cat "$tmp/guardian.pid")\n'),
            RULE_COMMAND_SHADOWING,
            "in front of `cat`",
        )

    def test_a_search_path_written_in_front_of_a_launcher_is_rejected(self) -> None:
        """A launcher runs one of its own words, so the first word proves nothing."""

        for index, form in enumerate(
            (
                'PATH="$tmp/shim:$PATH" command grep -q x "$attempt_state"\n',
                'PATH="$tmp/shim:$PATH" env grep -q x "$attempt_state"\n',
                'env PATH="$tmp/shim:$PATH" grep -q x "$attempt_state"\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    COMPLIANT + "\n" + form,
                    RULE_COMMAND_SHADOWING,
                    "in front of `grep`",
                )

    def test_a_search_path_written_in_front_of_a_wrapper_is_rejected(self) -> None:
        """A declared wrapper forwards to the command its body writes."""

        self.assert_rejected(
            COMPLIANT
            + '\nPATH="$tmp/shim:$PATH" fixture_git "$update_source" tag v9\n',
            RULE_COMMAND_SHADOWING,
            "in front of the declared `fixture_git` wrapper",
        )

    def test_a_helper_placed_by_a_target_directory_option_is_rejected(self) -> None:
        """The directory is read from the option word, however it is written."""

        for index, form in enumerate(
            (
                'cp -t "$tmp/bin" "$tmp/staging/grep"\n',
                'cp -t"$tmp/bin" "$tmp/staging/grep"\n',
                'cp --target-directory="$tmp/bin" "$tmp/staging/grep"\n',
                'install --target-directory="$tmp/bin" "$tmp/staging/grep"\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched(form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )

    def test_a_helper_written_through_the_working_directory_is_rejected(self) -> None:
        """A relative path names the directory the shell is in, which may be searched."""

        self.assert_rejected(
            self.searched('cd "$tmp/bin"\ncp "$root/tests/fixtures/helper" grep\n'),
            RULE_COMMAND_SHADOWING,
            "writes a `grep` helper",
        )

    def test_a_relative_search_path_element_is_read_as_unplaceable(self) -> None:
        self.assert_rejected(
            COMPLIANT
            + '\nPATH="bin:$PATH"\nexport PATH\n'
            + 'cp "$root/tests/fixtures/helper" "$tmp/elsewhere/grep"\n',
            RULE_COMMAND_SHADOWING,
            "writes a `grep` helper",
        )

    def test_a_search_path_bound_without_an_assignment_is_read_as_unplaceable(
        self,
    ) -> None:
        """A shell also binds the search path through `read` and through a loop."""

        for index, form in enumerate(
            ('read PATH <"$tmp/new-path"\n', "for PATH in a b; do\n  :\ndone\n")
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched(
                        'cp "$root/tests/fixtures/helper" "$tmp/elsewhere/grep"\n'
                        + form
                    ),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )

    def test_binding_a_command_name_behind_a_launcher_is_rejected(self) -> None:
        for index, form in enumerate(
            (
                'hash -p "$tmp/true" grep\n',
                'command hash -p "$tmp/true" grep\n',
                'builtin hash -p "$tmp/true" git\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    COMPLIANT + "\n" + form,
                    RULE_COMMAND_SHADOWING,
                    "binds a command name through `hash`",
                )

    def test_a_search_path_written_in_front_of_a_forwarder_is_rejected(self) -> None:
        """A program that runs its own argument forwards the search path too.

        No bounded list of such programs exists, so every word of the run is
        read rather than only the command word and a known launcher list.
        """

        for name in ("nice", "ionice", "timeout 5", "stdbuf -oL"):
            with self.subTest(command=name):
                self.assert_rejected(
                    COMPLIANT
                    + f'\nPATH="$tmp/shim:$PATH" {name} grep -q x "$attempt_state"\n',
                    RULE_COMMAND_SHADOWING,
                    "in front of `grep`",
                )

    def test_a_hash_option_this_checker_cannot_read_is_rejected(self) -> None:
        """A word that carries an expansion may be the option that rebinds."""

        self.assert_rejected(
            COMPLIANT + '\nhash_option=-p\nhash "$hash_option" "$tmp/true" grep\n',
            RULE_COMMAND_SHADOWING,
            "binds a command name through `hash`",
        )

    def test_a_target_directory_option_this_checker_cannot_read_is_rejected(
        self,
    ) -> None:
        """An unreadable word that could be the option leaves the destination unknown."""

        for index, form in enumerate(
            (
                'placement=-t\ncp "$placement" "$tmp/bin" "$tmp/staging/grep"\n',
                'placement=--target-directory\n'
                'install "$placement" "$tmp/bin" "$tmp/staging/grep"\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched(form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )

    def test_unsetting_the_search_path_is_read_as_unplaceable(self) -> None:
        self.assert_rejected(
            self.searched(
                'cp "$root/tests/fixtures/helper" "$tmp/elsewhere/grep"\nunset PATH\n'
            ),
            RULE_COMMAND_SHADOWING,
            "writes a `grep` helper",
        )

    def test_a_destination_this_checker_cannot_place_is_rejected(self) -> None:
        """A path this checker cannot settle is not a path proved to lie outside.

        A parent segment and a command substitution both leave the destination
        unsettled, and the file still lands in the searched directory.
        """

        for index, form in enumerate(
            (
                'printf "x" >"$tmp/bin/../bin/grep"\n',
                'cp "$root/helper" "$tmp/bin/x/../grep"\n',
                'touch "$tmp/bin/x/../grep"\n',
                'printf x | tee "$tmp/bin/x/../grep"\n',
                'ln -s "$root/helper" "$tmp/bin/x/../grep"\n',
                'cp "$root/helper" "$(printf %s "$tmp/bin")/grep"\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched(form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )

    def test_a_redirection_written_on_a_compound_is_rejected(self) -> None:
        """A group and a subshell carry a redirection no single command holds."""

        for index, form in enumerate(
            (
                '{ printf "x"; } >"$tmp/bin/grep"\n',
                '( printf "x" ) >"$tmp/bin/grep"\n',
                'for name in one; do printf "x"; done >"$tmp/bin/grep"\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched(form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )

    def test_a_search_path_written_in_front_of_a_carried_program_is_rejected(
        self,
    ) -> None:
        """An interpreter runs the commands written inside the word it is given."""

        for index, form in enumerate(
            (
                'PATH="$tmp/shim:$PATH" sh -c \'grep -q x "$1"\' _ "$attempt_state"\n',
                'PATH="$tmp/shim:$PATH" bash -c "grep -q x $attempt_state"\n',
                'PATH="$tmp/shim:$PATH" awk \'BEGIN { system("git status") }\'\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched(form),
                    RULE_COMMAND_SHADOWING,
                    "writes a search path in front of",
                )

    def test_a_launcher_that_only_carries_the_search_path_name_is_accepted(
        self,
    ) -> None:
        """A launcher binds no name, so the name it carries stays data."""

        for index, form in enumerate(
            (
                'command grep PATH "$attempt_state" || true\n',
                'env grep PATH "$attempt_state" || true\n',
                'timeout 5 grep PATH "$attempt_state" || true\n',
                'command printf "%s" PATH\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_accepted(
                    self.searched(form + 'touch "$tmp/archive/git"\n')
                )

    def test_a_compound_redirection_is_read_at_every_binding_it_may_use(
        self,
    ) -> None:
        """The shell expands the word before the body the word is written after.

        A value bound inside the body is therefore not the only value the
        redirection may use, and a word repeated under a different value names
        a different file each time it is written.
        """

        for index, form in enumerate(
            (
                'place="$tmp/bin"\n'
                '{ place="$tmp/archive"; printf x; } >"$place/grep"\n',
                'place="$tmp/archive"\n'
                'printf x >"$place/grep"\n'
                'place="$tmp/bin"\n'
                '{ printf y; } >"$place/grep"\n',
                'place="$tmp/archive"\n'
                'printf x >"$place/grep"\n'
                'place="$tmp/bin"\n'
                '( printf y ) >"$place/grep"\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched('mkdir -p "$tmp/archive"\n' + form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )

    def test_a_compound_redirection_outside_the_search_path_is_accepted(self) -> None:
        self.assert_accepted(
            self.searched(
                'mkdir -p "$tmp/archive"\n{ printf x; } >"$tmp/archive/git"\n'
            )
        )

    def test_a_carried_program_this_checker_cannot_unquote_is_rejected(self) -> None:
        """A word that could be a program text is refused, not searched.

        The shell removes an escape and expands a name before it reads a
        command name, so a written text that spells no observed name may still
        run one.
        """

        for index, form in enumerate(
            (
                'PATH="$tmp/shim:$PATH" sh -c \'\\grep -q x "$attempt_state"\'\n',
                'PATH="$tmp/shim:$PATH" sh -c \'reader=grep; $reader -q x f\'\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched(form),
                    RULE_COMMAND_SHADOWING,
                    "writes a search path in front of",
                )

    def test_a_name_bound_behind_a_launcher_option_is_read(self) -> None:
        """An option written after a launcher belongs to the launcher."""

        self.assert_rejected(
            self.searched(
                'command -p read PATH <"$tmp/new-path"\n'
                'cp "$root/tests/fixtures/helper" "$tmp/elsewhere/grep"\n'
            ),
            RULE_COMMAND_SHADOWING,
            "writes a `grep` helper",
        )

    def test_a_compound_redirection_reads_the_value_its_compound_starts_with(
        self,
    ) -> None:
        """A name rebound before the compound names one file, not every file."""

        self.assert_accepted(
            self.searched(
                'mkdir -p "$tmp/archive"\n'
                'place="$tmp/bin"\n'
                'touch "$place/keep"\n'
                'place="$tmp/archive"\n'
                '{ printf x; } >"$place/grep"\n'
            )
        )

    def test_a_loop_redirection_reads_the_value_its_body_binds(self) -> None:
        """A loop expands its redirection word once for each pass it makes."""

        self.assert_rejected(
            self.searched(
                'mkdir -p "$tmp/archive"\n'
                'place="$tmp/archive"\n'
                'for step in one two; do place="$tmp/bin"; printf x; done '
                '>"$place/grep"\n'
            ),
            RULE_COMMAND_SHADOWING,
            "writes a `grep` helper",
        )

    def test_an_escape_written_before_a_carried_name_is_read(self) -> None:
        """A shell removes the escape before it reads the command name."""

        self.assert_rejected(
            self.searched('PATH="$tmp/shim:$PATH" sh -c \'\\grep\'\n'),
            RULE_COMMAND_SHADOWING,
            "writes a search path in front of `grep`",
        )

    def test_an_escape_written_in_data_is_accepted(self) -> None:
        """An escape a format string carries never reaches a command name."""

        self.assert_accepted(
            self.searched(
                'PATH="$tmp/failing-git:$PATH" printf %s\\n checked\n'
            )
        )

    def test_a_reserved_word_written_as_data_leaves_the_compound_read(
        self,
    ) -> None:
        """A compound is opened by a reserved word only where a command starts.

        The same text written as an operand is data, so it must not be read as
        opening a compound that never closes.
        """

        for index, operand in enumerate(("for", "if", "case", "while", "until")):
            with self.subTest(operand=operand):
                self.assert_rejected(
                    self.searched(
                        'mkdir -p "$tmp/archive"\n'
                        'place="$tmp/archive"\n'
                        '{ :; } >"$tmp/archive/first"\n'
                        'place="$tmp/bin"\n'
                        f'{{ printf %s {operand}; printf x; }} >"$place/grep"\n'
                    ),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )

    def test_a_reserved_word_written_as_data_keeps_a_safe_compound_accepted(
        self,
    ) -> None:
        """The same reading must not reject a path written outside the search path."""

        self.assert_accepted(
            self.searched(
                'mkdir -p "$tmp/archive"\n'
                'place="$tmp/bin"\n'
                'touch "$place/keep"\n'
                'place="$tmp/archive"\n'
                '{ printf %s for; printf x; } >"$place/grep"\n'
            )
        )

    def test_a_case_pattern_leaves_the_compound_read(self) -> None:
        """A pattern closes no subshell, so it must not unbalance the reading.

        The value is rebound before the compound, so the accepted reading
        holds only while the pattern leaves the enclosing compound readable.
        """

        self.assert_accepted(
            self.searched(
                'mkdir -p "$tmp/archive"\n'
                'place="$tmp/bin"\n'
                'touch "$place/keep"\n'
                'place="$tmp/archive"\n'
                'case one in one) : ;; esac\n'
                '{ printf x; } >"$place/grep"\n'
            )
        )

    def test_a_compound_redirection_in_a_body_is_read_at_its_call(self) -> None:
        """A body runs where it is called, not where it is written."""

        for index, form in enumerate(
            (
                'helper() { { printf x; } >"$place/grep"; }\n',
                'helper() { ( printf x ) >"$place/grep"; }\n',
                'helper() { for step in one; do printf x; done >"$place/grep"; }\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched(
                        'mkdir -p "$tmp/archive"\n'
                        'place="$tmp/archive"\n'
                        + form
                        + 'place="$tmp/bin"\n'
                        'helper\n'
                    ),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )

    def test_a_compound_redirection_in_a_body_reads_only_its_calls(self) -> None:
        """A value no call of the body holds names no file the body creates.

        Every dispatch this fixture cannot read is written with a path, so it
        runs a file rather than a declared body, and the body is read against
        the values its written calls hold.
        """

        for index, form in enumerate(
            (
                'helper() { { printf x; } >"$place/grep"; }\n'
                'place="$tmp/archive"\n'
                'helper\n'
                'place="$tmp/bin"\n'
                'touch "$place/keep"\n',
                'place="$tmp/bin"\n'
                'touch "$place/keep"\n'
                'place="$tmp/archive"\n'
                'helper() { { printf x; } >"$place/grep"; }\n'
                'helper\n',
                'place="$tmp/archive"\n'
                'helper() { { printf x; } >"$place/git"; }\n'
                'helper\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_accepted(
                    self.searched('mkdir -p "$tmp/archive"\n' + form)
                )

    def test_a_hash_entry_written_in_a_deferred_body_is_rejected(self) -> None:
        """A `hash` entry a deferred body writes rebinds the whole shell."""

        for index, form in enumerate(
            (
                'helper() { hash -p "$tmp/archive/g" grep; }\n'
                'name=helper\n'
                '$name\n',
                'helper() { hash -p "$tmp/archive/g" grep; }\ntrap helper EXIT\n',
                'inner() { hash -p "$tmp/archive/g" grep; }\n'
                'outer() { inner; }\n'
                'trap outer EXIT\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched('mkdir -p "$tmp/archive"\n' + form),
                    RULE_COMMAND_SHADOWING,
                    "binds a command name through `hash`",
                )

    def test_a_body_a_deferred_body_calls_is_read(self) -> None:
        """A call written inside a deferred body reaches another body.

        The deferred names are closed over the calls the collected bodies
        make, so a chain of calls behind one trap action is read, and a
        dispatch such a body cannot resolve reaches every declaration. An
        action such a body registers and a file it includes reach a body the
        same way, so both are followed as well.
        """

        for index, form in enumerate(
            (
                'inner() { touch "$tmp/bin/grep"; }\n'
                'outer() { inner; }\n'
                'trap outer EXIT\n',
                'inner() { touch "$tmp/bin/grep"; }\n'
                'middle() { inner; }\n'
                'outer() { middle; }\n'
                'trap outer EXIT\n',
                'inner() { touch "$tmp/bin/grep"; }\n'
                'outer() { chosen=inner; $chosen; }\n'
                'trap outer EXIT\n',
                'inner() { touch "$tmp/bin/grep"; }\n'
                'outer() { trap inner USR1; }\n'
                'trap outer TERM\n',
                'inner() { touch "$tmp/bin/grep"; }\n'
                'outer() { . "$tmp/library.sh"; }\n'
                'trap outer TERM\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched(form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )
        for index, form in enumerate(
            (
                'inner() { touch "$tmp/bin/keep"; }\n'
                'outer() { inner; }\n'
                'trap outer EXIT\n',
                'inner() { touch "$tmp/bin/keep"; }\n'
                'outer() { trap inner USR1; }\n'
                'trap outer TERM\n',
            )
        ):
            with self.subTest(accepted=index):
                self.assert_accepted(self.searched(form))

    def test_a_dispatch_written_with_a_path_calls_no_body(self) -> None:
        """A command word holding a slash is never looked up as a function.

        Such a dispatch runs a file, so it arms no reading of a declared body,
        while a dispatch that may still name one does.
        """

        body = (
            'mkdir -p "$tmp/archive"\n'
            'place="$tmp/bin"\n'
            'touch "$place/keep"\n'
            'place="$tmp/archive"\n'
            'capture() { printf x >"$place/git"; }\n'
            'capture\n'
        )
        self.assert_accepted(self.searched(body))
        self.assert_rejected(
            self.searched(body + 'called=capture\n$called\n'),
            RULE_COMMAND_SHADOWING,
            "writes a `git` helper",
        )

    def test_a_body_a_call_the_graph_cannot_resolve_reaches_is_read(
        self,
    ) -> None:
        """A trap action and a dispatch the graph cannot read still run a body.

        The graph folds a body into the calls it resolves, so an unresolved
        call leaves the body holding no command node. The files such a body
        writes are created all the same, so they are read from the records.
        """

        for index, form in enumerate(
            (
                'helper() { touch "$tmp/bin/grep"; }\ntrap helper EXIT\n',
                "helper() { touch \"$tmp/bin/grep\"; }\ntrap 'helper' EXIT\n",
                'place="$tmp/bin"\n'
                'helper() { { printf x; } >"$place/grep"; }\n'
                'trap helper EXIT\n',
                'helper() { touch "$tmp/bin/grep"; }\nname=helper\n$name\n',
                'helper() { touch "$tmp/bin/grep"; }\nset -- helper\n"$1"\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched(form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )

    def test_a_body_a_call_cannot_resolve_writes_no_observed_name(self) -> None:
        """A deferred body naming no observed command writes no shim.

        The destination a deferred body writes is settled and compared with
        the search path, so a file it creates elsewhere, a name it only reads,
        and a file it moves out of the search path all stay accepted.
        """

        for index, form in enumerate(
            (
                'helper() { touch "$tmp/bin/keep"; }\ntrap helper EXIT\n',
                'helper() { printf grep; }\ntrap helper EXIT\n',
                'helper() { touch "$tmp/archive/grep"; }\ntrap helper EXIT\n',
                'helper() { mv "$tmp/bin/sleep" "$tmp/archive"; }\n'
                'trap helper EXIT\n',
                'helper() { cp "$tmp/archive/grep" "$tmp/archive/copy"; }\n'
                'trap helper EXIT\n',
                'place="$tmp/archive"\n'
                'helper() { { printf x; } >"$place/git"; }\n'
                'helper\n',
                'place="$tmp/archive"\n'
                'helper() { { printf x; } >"$place/grep"; }\n'
                'helper\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_accepted(
                    self.searched('mkdir -p "$tmp/archive"\n' + form)
                )

    def test_a_deferred_body_writing_into_the_path_is_rejected(self) -> None:
        """Every way a deferred body puts a file in the search path is read.

        A dead call leaves the body unmodelled just as no call does, a
        substitution encloses a redirection the body still runs, and a copying
        command creates a file named after what it reads when its destination
        names a searched directory. A call the graph resolves does not exhaust
        the calls a body gets, so a deferred call that runs it again with a
        later value is read as well, and the destination of a copying command
        is read through the same option-aware settling the modelled commands
        use.
        """

        for index, form in enumerate(
            (
                'helper() { touch "$tmp/bin/grep"; }\n'
                'trap helper EXIT\n'
                'exit 0\n'
                'helper\n',
                'helper() { out=$(printf x >"$tmp/bin/grep"); }\n'
                'trap helper EXIT\n',
                'helper() { mv "$tmp/archive/grep" "$tmp/bin"; }\n'
                'trap helper EXIT\n',
                'helper() { cp "$tmp/archive/x" "$tmp/bin/grep"; }\n'
                'trap helper EXIT\n',
                'place="$tmp/archive"\n'
                'helper() { touch "$place/grep"; }\n'
                'helper\n'
                'trap helper EXIT\n'
                'place="$tmp/bin"\n',
                'place="$tmp/archive"\n'
                'helper() { touch "$place/grep"; }\n'
                'helper\n'
                'name=helper\n'
                'place="$tmp/bin"\n'
                '$name\n',
                'part=grep\n'
                'helper() { mv "$tmp/archive/$part" "$tmp/bin"; }\n'
                'trap helper EXIT\n',
                'helper() { cp -t "$tmp/bin" "$tmp/archive/grep"; }\n'
                'trap helper EXIT\n',
                'helper() { mv "$tmp/archive/grep" "$elsewhere"; }\n'
                'trap helper EXIT\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched('mkdir -p "$tmp/archive"\n' + form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )

    def test_a_redirection_written_alone_reads_its_own_place(self) -> None:
        """A command that is only a redirection belongs to no compound.

        The word is expanded where it is written, so the value the preceding
        group bound is the value the shell uses, and a value bound after that
        group names the file it really creates.
        """

        for index, form in enumerate(
            (
                '{ place="$tmp/bin"; :; }\n>"$place/grep"\n',
                '{ place="$tmp/bin"; :; }\n2>"$place/grep"\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched(
                        'mkdir -p "$tmp/archive"\nplace="$tmp/archive"\n' + form
                    ),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )
        self.assert_accepted(
            self.searched(
                'mkdir -p "$tmp/archive"\n'
                'place="$tmp/bin"\n'
                'touch "$place/keep"\n'
                'place="$tmp/archive"\n'
                '>"$place/grep"\n'
            )
        )

    def test_a_working_directory_root_may_name_a_searched_directory(self) -> None:
        """A substitution that reads the working directory names no fixed place.

        `cd` decides what such a substitution reports, so a path written below
        one root is never proved to lie outside a directory written below
        another. The paths written apart by a name both spell as text stay
        apart, and so does a directory written below a searched one, because a
        search-path lookup never descends.
        """

        for index, form in enumerate(
            (
                'cd "$tmp/bin"\nplace=$(pwd)\ntouch "$place/grep"\n',
                'cd "$tmp/bin"\nplace=$(pwd -P)\ntouch "$place/grep"\n',
                'cd "$tmp/bin"\nplace=$(command pwd)\nprintf x >"$place/grep"\n',
                'place=$(cd "$tmp/bin" && pwd)\ntouch "$place/grep"\n',
                'cd "$tmp/bin"\nplace=$(pwd)\ncp "$root/helper" "$place/grep"\n',
                'cd "$tmp/bin"\nplace=$(pwd)\ncp -t "$place" "$tmp/staging/grep"\n',
                'helper() { place=$(pwd); touch "$place/grep"; }\ntrap helper EXIT\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_rejected(
                    self.searched(form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )
        for index, form in enumerate(
            (
                'cd "$tmp/bin"\nplace=$(pwd)\ntouch "$place/keep"\n',
                'mkdir -p "$tmp/archive"\n'
                'cd "$tmp"\n'
                "place=$(pwd)\n"
                'touch "$place/archive/grep"\n',
                'mkdir -p "$tmp/bin/sub"\ntouch "$tmp/bin/sub/grep"\n',
            )
        ):
            with self.subTest(accepted=index):
                self.assert_accepted(self.searched(form))

    def test_a_directory_is_placed_by_the_segments_two_paths_write_alike(
        self,
    ) -> None:
        """A path written from the root a searched directory is written from.

        The segments the two write the same way name the same directories, so
        what they write apart places them: a directory the search path names
        is not reached from the directory above it, from a directory beside
        it, or from a directory of the same name written under another one.
        """

        for index, form in enumerate(
            (
                'touch "$tmp/grep"\n',
                'place="$tmp"\ntouch "$place/grep"\n',
                'printf x >"$tmp/grep"\n',
                'mkdir -p "$tmp/archive"\ncp "$tmp/archive/grep" "$tmp"\n',
                'mkdir -p "$tmp/archive"\ncp -t "$tmp" "$tmp/archive/grep"\n',
                'mkdir -p "$tmp/archive/bin"\ntouch "$tmp/archive/bin/grep"\n',
                'mkdir -p "$tmp/sub/bin"\ncp "$root/helper" "$tmp/sub/bin/grep"\n',
                'mkdir -p "$tmp/sub/archive"\ntouch "$tmp/sub/archive/grep"\n',
            )
        ):
            with self.subTest(accepted=index):
                self.assert_accepted(self.searched(form))
        for index, form in enumerate(
            (
                'touch "$tmp/bin/grep"\n',
                'mkdir -p "$tmp/bin/../bin"\ntouch "$tmp/bin/grep"\n',
                # The searched directory is written from a substitution that
                # may stand for the root itself, so a path written wholly as
                # text under the same name is not proved to be another one.
                'touch "/bin/grep"\n',
                'touch "/x/bin/grep"\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.searched(form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )
        self.assert_rejected(
            COMPLIANT
            + '\nmkdir -p "/opt/x/bin"\n'
            + 'PATH="/opt/x/bin:$PATH"\n'
            + "export PATH\n"
            + 'touch "/opt/x/bin/grep"\n',
            RULE_COMMAND_SHADOWING,
            "writes a `grep` helper",
        )

    def test_a_word_this_checker_cannot_read_is_read_for_the_helper_it_writes(
        self,
    ) -> None:
        """An interpreter given a program text writes the files that text writes.

        The shell unquoting such a text needs is not performed here, so the
        word is refused rather than settled and the path endings it writes are
        read from its text. A destination refused that way is not placed, so a
        text that writes a helper outside the searched directories is refused
        as well. A word that only mentions a name writes no path with it.
        """

        for index, form in enumerate(
            (
                'sh -c "touch $tmp/bin/grep"\n',
                'sh -c "cp $tmp/archive/x $tmp/bin/grep"\n',
                'awk "BEGIN { system(\\"touch $tmp/bin/grep\\") }" </dev/null\n',
                'dd if=/dev/null of="$tmp/bin/grep" 2>/dev/null\n',
                "python3 -c \"open('$tmp/bin/grep','w').close()\"\n",
                'sh -c "touch $tmp/archive/grep"\n',
                'helper() { sh -c "touch $tmp/bin/grep"; }\ntrap helper EXIT\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.searched('mkdir -p "$tmp/archive"\n' + form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )
        for index, form in enumerate(
            (
                'sh -c "touch $tmp/bin/keep"\n',
                'printf "%s\\n" "adoption did not install the helper" >&2\n',
                "grep -q 'a\\|git push\\|b' \"$attempt_state\" || true\n",
                'sh -c "printf %s x" >/dev/null\n',
            )
        ):
            with self.subTest(accepted=index):
                self.assert_accepted(self.searched(form))

    def test_a_run_this_checker_models_writes_no_helper_its_words_mention(
        self,
    ) -> None:
        """A message, a pattern and a script are data rather than a program.

        A run written as a command this checker models either reads its
        operands as data or is settled as the write it is written as, so a
        path a word of such a run spells names no file the run creates. The
        refusal is kept for every other run, which may be an interpreter given
        a program text.
        """

        for index, form in enumerate(
            (
                'printf "%s\\n" "see tools/git for details"\n',
                'printf "%s\\n" "restored docs/plan and tools/cat"\n',
                'grep -q "a b/sed" "$tmp/archive/f" || true\n',
                'sed -i "s/old docs\\/git/new/" "$tmp/archive/f"\n',
                'echo "kept tools/rm and tools/install" >/dev/null\n',
                'test -f "$tmp/archive/f" || printf "%s\\n" "no tools/mv"\n',
            )
        ):
            with self.subTest(accepted=index):
                self.assert_accepted(
                    self.searched(
                        'mkdir -p "$tmp/archive"\n'
                        'touch "$tmp/archive/f"\n' + form
                    )
                )
        for index, form in enumerate(
            (
                'sh -c "touch $tmp/bin/grep"\n',
                'env sh -c "touch $tmp/bin/grep"\n',
                'PATH="$PATH" sh -c "touch $tmp/bin/grep"\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.searched(form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )

    def test_a_command_written_as_a_path_is_not_read_as_the_utility_it_names(
        self,
    ) -> None:
        """A file the fixture supplies may write whatever it likes.

        The exemption a message-writing command carries belongs to the utility
        a bare name reaches, not to a file the fixture puts at that name, so a
        command written as a path is read for the helper paths its words
        carry.
        """

        for index, form in enumerate(
            (
                './printf "touch $tmp/bin/grep"\n',
                '/bin/echo "touch $tmp/bin/grep"\n',
                '"$tmp/archive/printf" "touch $tmp/bin/grep"\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.searched('mkdir -p "$tmp/archive"\n' + form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )
        self.assert_accepted(self.searched('printf "%s\\n" "tools/grep"\n'))

    def test_a_sed_script_that_runs_a_command_is_read_as_a_shell_text(
        self,
    ) -> None:
        """`sed` runs a command with `e`, which writes what no `w` names."""

        for index, form in enumerate(
            (
                'sed "s/.*/touch $tmp\\/bin\\/grep/e" "$attempt_state" >/dev/null\n',
                'sed "s|.*|touch $tmp/bin/grep|e" "$attempt_state" >/dev/null\n',
                'sed "s/.*/touch $tmp\\/bin\\/grep/ge" "$attempt_state" >/dev/null\n',
                'sed "s/.*/touch $tmp\\/bin\\/grep/g e" "$attempt_state" >/dev/null\n',
                'sed "1e touch $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/x/y/;1e touch $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s|.*|cp $tmp/archive/f $tmp/bin/grep|e" "$attempt_state"'
                ' >/dev/null\n',
                'sed "1e touch $tmp/bin/grep\n2w $tmp/archive/log"'
                ' "$attempt_state" >/dev/null\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.searched(
                        'mkdir -p "$tmp/archive"\n'
                        'touch "$tmp/archive/f"\n' + form
                    ),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )

    def test_a_sed_script_is_data_until_it_writes_the_file_it_names(
        self,
    ) -> None:
        """`sed` names a file to write with `w`, and nothing else it reads does.

        A script that spells no write carries its paths as data, so a fixture
        that rewrites a message mentioning a helper name is accepted. A script
        that spells the write command or the substitution flag names the file
        it creates, so the paths it carries are read as helpers.
        """

        for index, form in enumerate(
            (
                'sed "s/x/y/w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -n "/x/w $tmp/bin/grep" "$attempt_state"\n',
                'sed -n "1w $tmp/bin/grep" "$attempt_state"\n',
                'sed -n "\\$w $tmp/bin/grep" "$attempt_state"\n',
                'sed -n "2,3w $tmp/bin/grep" "$attempt_state"\n',
                'sed -n "1W $tmp/bin/grep" "$attempt_state"\n',
                'sed -n "1w$tmp/bin/grep" "$attempt_state"\n',
                'sed "s|a|b|w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s,a,b,w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'x=1 sed "s|a|b|w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -n "p;w $tmp/bin/grep" "$attempt_state"\n',
                'env sed -e "1w $tmp/bin/grep" "$attempt_state"\n',
                'sed -e "s/a/b/gw $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "s/x/y/pw $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "s/x/y/Iw $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "s/a/b/pgw $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'env sed -e "s/a/b/gw $tmp/bin/grep" "$attempt_state"\n',
                'sed -e "s/a/b/2w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "s/a/b/g3w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "s/a/b/gw$tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "1wbin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "s/a/b/gwbin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "1w./bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e1wbin/grep "$attempt_state" >/dev/null\n',
                'sed -e "\\$w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "1!w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "1 w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "\\,foo,w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "\\,foo,wbin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "\\%foo%w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "\\%foo%,\\%bar%w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "/foo/,\\%bar%w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed -e "\\,foo,!w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed --expression=1w"$tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed --expression=w"$tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed --expression=1w$tmp/bin/grep "$attempt_state" >/dev/null\n',
                'sed --expression=\\,foo,wbin/grep "$attempt_state" >/dev/null\n',
                'sed "1a hello\n2w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "1w $tmp/bin/grep\n2a hello" "$attempt_state" >/dev/null\n',
                "sed '1a\\\\\n1wbin/grep' \"$attempt_state\" >/dev/null\n",
                'sed "s;a;b;w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s;i;b;w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s{a{b{w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s;a;b;gw $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s;a;b;\n1w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "y;a;b;\n1w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/x/y/;s;a;b;w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/x/y/;s{a{b{w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "y/x/y/;s;a;b;w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/x/y/;s/p/q/;s;i;b;w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s;a;b\\\\\nc;w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s;when;tools/x;w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/a/b/;w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s;a;b;;w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/a/b/ w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s|a|b| w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s;a;b; w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s{a{b{ w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/a/b/g w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/a/b/ 1w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/a/b/ w$tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/x/y/;s;a;b; w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "y;a;x;w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/a/b/ gw $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/a/b/ p w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/a/b/ Iw $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/a/b/ g2w $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/a/b/g pw $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s;a;b; gw $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed "s/x/x/ pw $tmp/bin/grep" "$attempt_state" >/dev/null\n',
                'sed 1w$tmp/bin/grep "$attempt_state" >/dev/null\n',
                'sed -es/a/b/gw$tmp/bin/grep "$attempt_state" >/dev/null\n',
                'sed -e1w\\ $tmp/bin/grep "$attempt_state" >/dev/null\n',
                'sed --expression=1w\\ $tmp/bin/grep "$attempt_state" >/dev/null\n',
                'sed -e1e\\ touch\\ $tmp/bin/grep "$attempt_state" >/dev/null\n',
                'sed --expression=1e\\ touch\\ $tmp/bin/grep "$attempt_state"\n',
                'sed -es,.*,touch\\ $tmp/bin/grep,e "$attempt_state" >/dev/null\n',
                'sed -nes,.*,touch\\ $tmp/bin/grep,e "$attempt_state" >/dev/null\n',
                'sed -e"1e touch $tmp/bin/grep" "$attempt_state" >/dev/null\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.searched(form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )
        for index, form in enumerate(
            (
                'sed -i "s/old docs\\/git/new/" "$tmp/archive/f"\n',
                'sed -i "s/a/b/" "$tmp/archive/f"\n',
                'sed "s/tools\\/grep/x/" "$attempt_state" >/dev/null\n',
                'printf "%s\\n" "restored new file and tools/git"\n',
                'env sed -e "1w $tmp/archive/log" "$attempt_state"\n',
                'env LC_ALL=C sed -n "/warning/p" "$attempt_state"\n',
                'command sed -e "1w $tmp/archive/log" "$attempt_state"\n',
                'sed -n "/warning/p" "$tmp/bin/git"\n',
                'val=$(sed -n "s/^ *when: *//p" "$tmp/bin/git")\n',
                'sed -n "1w $tmp/archive/log" "$tmp/bin/grep"\n',
                'sed "s|a/grep|b|w $tmp/archive/out" "$attempt_state" >/dev/null\n',
                'sed "s|a|/grep|w $tmp/archive/out" "$attempt_state" >/dev/null\n',
                'sed "s|a/grep|b|" "$attempt_state" >/dev/null\n',
                'sed "s|workflow/git|x|" "$attempt_state" >/dev/null\n',
                'sed -n "/warning\\/grep/p" "$attempt_state"\n',
                'sed "s|old|new-workflow/git|" "$attempt_state" >"$tmp/archive/o"\n',
                'sed -i "s|workflow/git|new|" "$tmp/archive/f"\n',
                'sed "s|bigwig/grep|x|" "$attempt_state" >/dev/null\n',
                'sed "s|show|workflow/git|g" "$attempt_state" >/dev/null\n',
                'sed -n "/wait\\/grep/!p" "$attempt_state"\n',
                'sed "/rework\\/grep/d" "$attempt_state" >/dev/null\n',
                'sed "s/msg/see workflow\\/git docs/" "$attempt_state" >/dev/null\n',
                'sed "s/x/y warning\\/git/" "$attempt_state" >/dev/null\n',
                'sed -n "/a!warning\\/grep/p" "$attempt_state"\n',
                'sed -n "\\,warning/grep,p" "$attempt_state"\n',
                'sed --expression=/warning\\/grep/p "$attempt_state" >/dev/null\n',
                'sed --in-place "s|workflow/git|new|" "$tmp/archive/f"\n',
                'sed -i.bak "s|workflow/git|new|" "$tmp/archive/f"\n',
                'sed -ne "/warning/p" "$attempt_state"\n',
                'sed -n -e "/warning/p" "$attempt_state"\n',
                'sed -es/where/x/ "$attempt_state" >/dev/null\n',
                'sed 1w$tmp/archive/log "$attempt_state" >/dev/null\n',
                'sed "$a\\\\\nwhen done see tools/git" "$attempt_state" >/dev/null\n',
                'sed "1a\\\\\nfirst\\\\\nworkflow/git ref" "$attempt_state" >/dev/null\n',
                'sed "1i\\\\\nwill call tools/grep" "$attempt_state" >/dev/null\n',
                'sed "1c\\\\\nwarning tools/git" "$attempt_state" >/dev/null\n',
                'sed "1a warning tools/git" "$attempt_state" >/dev/null\n',
                'sed "1a hello;2w tools/grep" "$attempt_state" >/dev/null\n',
                "sed '1a\\\nwarning tools/git' \"$attempt_state\" >/dev/null\n",
                'sed "s;a/grep;b;" "$attempt_state" >/dev/null\n',
                'sed "s;q;r;;1a hello workflow/git" "$attempt_state" >/dev/null\n',
                'sed "1a\\\\\nworkflow/git and s;x;y; notes" "$attempt_state" >/dev/null\n',
                'sed "s/x/y/;1a hello workflow/git" "$attempt_state" >/dev/null\n',
                'sed "s/x/y/;s;a/grep;b;" "$attempt_state" >/dev/null\n',
                'sed "s;when;tools/git;" "$attempt_state" >/dev/null\n',
                'sed "s{when{tools/git{" "$attempt_state" >/dev/null\n',
                'sed "s;x;we tools/git;" "$attempt_state" >/dev/null\n',
                'sed "s;warn/old;warn/git;" "$attempt_state" >/dev/null\n',
                'sed "y/a/b/ w tools/git" "$attempt_state" >/dev/null\n',
                'sed "s/w/x/ p" "$attempt_state" >/dev/null\n',
                'sed "s/a/b/ meow" "$attempt_state" >/dev/null\n',
                'sed "s/a/b/ mow tools/git" "$attempt_state" >/dev/null\n',
                'sed "s;x;e touch tools/git;" "$attempt_state" >/dev/null\n',
                'sed -n -e "/warning/p" "$attempt_state" >/dev/null\n',
            )
        ):
            with self.subTest(accepted=index):
                self.assert_accepted(
                    self.searched(
                        'mkdir -p "$tmp/archive"\n'
                        'touch "$tmp/archive/f"\n' + form
                    )
                )

    def test_a_loop_head_names_the_file_a_word_under_it_creates(
        self,
    ) -> None:
        """A `for` head writes its list in full where the head is written.

        This checker settles no name a loop head binds, so a destination
        written as that name carries no name of its own. The file such a write
        creates is one of the paths the list names, so the list is read for the
        helpers it puts in place. A list naming no helper is accepted.
        """

        for index, form in enumerate(
            (
                'for p in "$tmp/bin/grep"; do touch "$p"; done\n',
                'for p in "$tmp/archive/h" "$tmp/bin/grep"; do touch "$p"; done\n',
                'for p in "$tmp/bin/grep"; do printf x >"$p"; done\n',
            )
        ):
            with self.subTest(rejected=index):
                self.assert_rejected(
                    self.searched('mkdir -p "$tmp/archive"\n' + form),
                    RULE_COMMAND_SHADOWING,
                    "writes a `grep` helper",
                )
        for index, form in enumerate(
            (
                'for p in "$tmp/bin/keep"; do touch "$p"; done\n',
                'for p in "$tmp/archive/grep"; do touch "$p"; done\n',
                'for p in "$tmp/archive/h"; do cat "$p" >/dev/null; done\n',
            )
        ):
            with self.subTest(accepted=index):
                self.assert_accepted(
                    self.searched('mkdir -p "$tmp/archive"\n' + form)
                )

    def test_a_write_no_word_names_makes_every_written_helper_reachable(
        self,
    ) -> None:
        """A command that takes its destination from what it reads names no file.

        `xargs` supplies the operands from its input, so nothing written says
        what file the run creates, and every helper name the fixture writes
        anywhere may be the name it takes. The word the launcher chain runs is
        a command name rather than a path, so it is not read as one.
        """

        self.assert_rejected(
            self.searched('printf %s "$tmp/bin/grep" | xargs touch\n'),
            RULE_COMMAND_SHADOWING,
            "writes a `grep` helper",
        )
        for index, form in enumerate(
            (
                'printf %s "$tmp/bin/keep" | xargs touch\n',
                'printf %s "$tmp/bin/keep" | xargs touch\n'
                'command grep PATH "$attempt_state" || true\n',
                'printf %s "$tmp/bin/grep" | cat >/dev/null\n',
                'command -v touch >/dev/null\ntouch "$tmp/archive/grep"\n',
                'printf "%s\\n" touch\ntouch "$tmp/archive/grep"\n',
                'printf x | tee\ntouch "$tmp/archive/grep"\n',
                'printf %s "$attempt_state" | xargs grep -q touch\n'
                'touch "$tmp/archive/grep"\n',
                'grep -q cp "$attempt_state" || true\n'
                'touch "$tmp/archive/grep"\n',
            )
        ):
            with self.subTest(accepted=index):
                self.assert_accepted(
                    self.searched('mkdir -p "$tmp/archive"\n' + form)
                )

    def test_a_helper_finding_is_reported_where_the_operation_is_written(
        self,
    ) -> None:
        """The position names the command that writes the file, not the rule."""
        written = 'touch "$tmp/bin/grep"\n'
        source = self.searched(written)
        findings = [
            finding
            for finding in check(source)
            if finding.rule == RULE_COMMAND_SHADOWING
        ]
        self.assertEqual(len(findings), 1, self.messages(source))
        self.assertIsNotNone(findings[0].position)
        self.assertEqual(findings[0].position.offset, source.index(written))

    def test_every_redirection_a_compound_carries_is_read_at_its_compound(
        self,
    ) -> None:
        """The second redirection belongs to the same compound as the first."""

        for index, form in enumerate(
            (
                '{ printf x; } >"$place/grep" 2>"$place/sed"\n',
                '{ printf x; } >"$place/grep" >>"$place/sed"\n',
                '( printf x ) >"$place/grep" 2>"$place/sed"\n',
                'for step in one; do printf x; done >"$place/grep" 2>"$place/sed"\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_accepted(
                    self.searched(
                        'mkdir -p "$tmp/archive"\n'
                        'place="$tmp/bin"\n'
                        'touch "$place/keep"\n'
                        'place="$tmp/archive"\n' + form
                    )
                )
                self.assert_rejected(
                    self.searched(
                        'mkdir -p "$tmp/archive"\nplace="$tmp/bin"\n' + form
                    ),
                    RULE_COMMAND_SHADOWING,
                    "writes a `sed` helper",
                )

    def test_a_declaration_that_rebinds_nothing_is_accepted(self) -> None:
        self.assert_accepted(COMPLIANT + "\nassert_state() {\n  :\n}\n")

    def test_a_helper_named_for_another_command_is_accepted(self) -> None:
        self.assert_accepted(
            self.searched(
                'cat >"$tmp/bin/copier-shim" <<\'EOF_SHIM\'\n'
                "#!/bin/sh\n"
                "exit 0\n"
                "EOF_SHIM\n"
            )
        )

    def test_a_helper_written_outside_every_searched_directory_is_accepted(self) -> None:
        self.assert_accepted(self.searched('touch "$tmp/archive/sed"\n'))

    def test_moving_an_observed_name_out_of_the_search_path_is_accepted(self) -> None:
        """A source operand is read as what is moved, not as what is created."""

        self.assert_accepted(self.searched('mv "$tmp/bin/sleep" "$tmp/archive"\n'))

    def test_moving_an_observed_name_out_with_an_option_is_accepted(self) -> None:
        """A target-directory option outside the search path creates nothing there."""

        self.assert_accepted(
            self.searched('mv -t "$tmp/archive" "$tmp/bin/sleep"\n')
        )

    def test_a_command_that_only_reads_the_search_path_name_is_accepted(self) -> None:
        """A word spelled like the search path is data unless a command binds it."""

        for index, form in enumerate(
            (
                'grep PATH "$attempt_state" || true\n',
                'grep PATH=x "$attempt_state" || true\n',
                "printf '%s\\n' PATH\n",
                'checked=$(read PATH </dev/null; echo done)\n',
            )
        ):
            with self.subTest(form=index):
                self.assert_accepted(
                    self.searched(form + 'touch "$tmp/archive/git"\n')
                )

    def test_a_written_path_that_only_reads_an_observed_name_is_accepted(self) -> None:
        self.assert_accepted(self.searched('cat "$tmp/bin/grep" >/dev/null\n'))


class SourcedLibraryTest(ContractSupportTest):
    """A file the fixture sources is read under the same shadowing rule.

    A sourced file runs with the authority of the shell that sources it, so a
    declaration written there rebinds a command name for every bound
    observation while the fixture keeps exactly its committed text. The bound
    libraries are supplied here, so nothing in this class reads a file the
    repository ships.
    """

    LIBRARY = "tests/lib-fixture.sh"

    LIBRARY_TEXT = (
        "fixture_available() {\n"
        "  command -v fixture >/dev/null 2>&1\n"
        "}\n"
        "\n"
        "run_fixture() {\n"
        '  fixture "$@"\n'
        "}\n"
    )

    SOURCING = '\n. "$root/tests/lib-fixture.sh"\n'

    # A Copier operation written through the wrapper. Only a name the fixture
    # runs this way carries a bound Copier observation, so this is what makes
    # the wrapper rule ask for a dispatch rather than for a name.
    OPERATION = (
        'run_copier copy -q --trust --defaults --vcs-ref v1.4.5 '
        '"$update_source" "$tmp/wrapper-out" >/dev/null\n'
    )

    sourced: dict[str, str] = {LIBRARY: LIBRARY_TEXT}

    def library(self, addition: str = "") -> dict[str, str]:
        return {self.LIBRARY: self.LIBRARY_TEXT + addition}

    def with_library(self, addition: str = "") -> str:
        return COMPLIANT + self.SOURCING + addition

    def shadowing(self, source: str) -> list[str]:
        """Return the shadowing findings alone.

        A fixture that writes a Copier operation of its own draws findings
        from the rules that read where Copier writes, and those say nothing
        about which names the shell holds.
        """

        return [
            str(finding)
            for finding in check(source, self.declared, self.sourced)
            if finding.rule == RULE_COMMAND_SHADOWING
        ]

    def assert_wrapper_rejected(self, text: str, expected: str) -> None:
        self.sourced = {self.LIBRARY: text}
        try:
            reported = "\n".join(self.shadowing(self.with_library(self.OPERATION)))
            self.assertIn(expected, reported)
            self.assertIn(f"the sourced library `{self.LIBRARY}`", reported)
        finally:
            self.sourced = self.library()

    def assert_wrapper_accepted(self, text: str) -> None:
        self.sourced = {self.LIBRARY: text}
        try:
            self.assertEqual(
                self.shadowing(self.with_library(self.OPERATION)), []
            )
        finally:
            self.sourced = self.library()

    def assert_library_rejected(self, addition: str, expected: str) -> None:
        self.sourced = self.library(addition)
        try:
            self.assert_rejected(
                self.with_library(), RULE_COMMAND_SHADOWING, expected
            )
            self.assertIn(f"the sourced library `{self.LIBRARY}`", self.messages(
                self.with_library()
            ))
        finally:
            self.sourced = self.library()

    def test_a_bound_library_the_fixture_sources_is_accepted(self) -> None:
        self.assert_accepted(self.with_library())

    def test_a_fixture_that_sources_nothing_is_accepted(self) -> None:
        self.assert_accepted(COMPLIANT)

    def test_an_observed_command_declared_in_the_library_is_rejected(self) -> None:
        for name in sorted(copier_fixture_validator.OBSERVED_COMMANDS):
            if not name.isidentifier():
                continue
            with self.subTest(command=name):
                self.assert_library_rejected(
                    f"\n{name}() {{\n  :\n}}\n", f"declares `{name}` as a function"
                )

    def test_the_reproduced_library_admission_is_rejected(self) -> None:
        self.assert_library_rejected(
            "\ngrep() { :; }\n", "declares `grep` as a function"
        )

    def test_a_helper_the_library_writes_on_the_search_path_is_rejected(self) -> None:
        self.assert_library_rejected(
            '\nmkdir -p "$tmp/bin"\nPATH="$tmp/bin:$PATH"\nexport PATH\n'
            'cp "$tmp/fake-grep" "$tmp/bin/grep"\n',
            "search path",
        )

    def test_a_hash_entry_written_in_the_library_is_rejected(self) -> None:
        self.assert_library_rejected(
            '\nhash -p "$tmp/fake-grep" grep\n', "binds a command name through `hash`"
        )

    def test_a_search_path_the_library_writes_for_one_command_is_rejected(self) -> None:
        self.assert_library_rejected(
            '\nPATH="$tmp/bin" grep -q x "$attempt_state"\n',
            "writes a search path in front of",
        )

    def test_the_copier_wrapper_declared_in_the_fixture_is_rejected(self) -> None:
        """The reproduced admission: a no-op wrapper keeps every needle intact."""

        self.assert_rejected(
            self.with_library("run_copier() { return 0; }\n"),
            RULE_COMMAND_SHADOWING,
            "declares the Copier wrapper `run_copier`",
        )

    def test_every_copier_named_declaration_in_the_fixture_is_rejected(self) -> None:
        for name in ("run_copier", "copier_available", "COPIER_run"):
            with self.subTest(name=name):
                self.assert_rejected(
                    self.with_library(f"{name}() {{\n  :\n}}\n"),
                    RULE_COMMAND_SHADOWING,
                    f"declares the Copier wrapper `{name}`",
                )

    def test_a_declaration_the_library_already_makes_is_rejected(self) -> None:
        self.assert_rejected(
            self.with_library("run_fixture() {\n  :\n}\n"),
            RULE_COMMAND_SHADOWING,
            "declares `run_fixture`, which the sourced library "
            f"`{self.LIBRARY}` declares as well",
        )

    def test_a_declaration_the_library_does_not_make_is_accepted(self) -> None:
        self.assert_accepted(self.with_library("report_state() {\n  :\n}\n"))

    def test_an_unbound_sourced_path_is_rejected(self) -> None:
        self.assert_rejected(
            COMPLIANT + '\n. "$root/tests/lib-other.sh"\n',
            RULE_COMMAND_SHADOWING,
            "sources a path this checker was not given",
        )

    def test_a_library_written_behind_another_directory_is_unbound(self) -> None:
        """Only the one anchor the sourcing file is given places the library."""

        self.assert_rejected(
            COMPLIANT + '\n. "$tmp/vendor/tests/lib-fixture.sh"\n',
            RULE_COMMAND_SHADOWING,
            "sources a path this checker was not given",
        )

    def test_a_library_the_fixture_could_write_itself_is_unbound(self) -> None:
        """Only the anchor the invocation decides places a bound library.

        A scratch directory the fixture fills is decided inside these bytes, so
        a file written there is not the file this checker was given, however
        the tail of the path is spelled.
        """

        self.assert_rejected(
            COMPLIANT
            + '\nmkdir -p "$tmp/tests"\n'
            + 'printf \'grep() { :; }\\n\' > "$tmp/tests/lib-fixture.sh"\n'
            + '. "$tmp/tests/lib-fixture.sh"\n',
            RULE_COMMAND_SHADOWING,
            "sources a path this checker was not given",
        )

    def test_a_source_written_relative_to_no_anchor_is_rejected(self) -> None:
        for operand in ("tests/lib-fixture.sh", "./tests/lib-fixture.sh"):
            with self.subTest(operand=operand):
                self.assert_rejected(
                    COMPLIANT + f"\n. {operand}\n",
                    RULE_COMMAND_SHADOWING,
                    "sources a path this checker was not given",
                )

    def test_a_second_value_written_for_the_anchor_unbinds_it(self) -> None:
        self.assert_rejected(
            COMPLIANT + '\nroot="$tmp"\n' + self.SOURCING,
            RULE_COMMAND_SHADOWING,
            "sources a path this checker was not given",
        )

    def test_an_anchor_the_fixture_decides_is_unbound(self) -> None:
        self.assert_rejected(
            self.with_library().replace('root=$1\n', 'root="$tmp/vendor"\n', 1),
            RULE_COMMAND_SHADOWING,
            "sources a path this checker was not given",
        )

    def test_a_copier_wrapper_the_library_empties_is_rejected(self) -> None:
        """The library holds the same authority the fixture does."""

        self.assert_wrapper_rejected(
            "run_copier() {\n  return 0\n}\n", "runs no Copier command"
        )

    def test_a_copier_wrapper_that_only_reports_is_rejected(self) -> None:
        self.assert_wrapper_rejected(
            'run_copier() {\n  echo copier "$@"\n}\n', "runs no Copier command"
        )

    def test_a_copier_wrapper_reduced_to_a_query_is_rejected(self) -> None:
        """Asking where Copier is performs no Copier operation."""

        self.assert_wrapper_rejected(
            "run_copier() {\n  command -v copier >/dev/null 2>&1\n}\n",
            "runs no Copier command",
        )

    def test_a_copier_wrapper_that_delegates_to_a_query_is_rejected(self) -> None:
        self.assert_wrapper_rejected(
            "copier_available() {\n  command -v copier >/dev/null 2>&1\n}\n"
            '\nrun_copier() {\n  copier_available "$@"\n}\n',
            "declares the Copier wrapper `run_copier` with a body that runs "
            "no Copier command",
        )

    def test_a_copier_wrapper_that_runs_copier_is_accepted(self) -> None:
        self.assert_wrapper_accepted(
            "copier_available() {\n"
            "  command -v copier >/dev/null 2>&1\n"
            "}\n"
            '\nrun_copier() {\n  copier "$@"\n}\n'
        )

    def test_a_copier_wrapper_that_runs_a_copier_path_is_accepted(self) -> None:
        self.assert_wrapper_accepted(
            "copier_bin=$(command -v copier)\n"
            '\nrun_copier() {\n  "$copier_bin" "$@"\n}\n'
        )

    def test_a_copier_wrapper_that_delegates_to_a_dispatcher_is_accepted(self) -> None:
        self.assert_wrapper_accepted(
            'copier_dispatch() {\n  copier "$@"\n}\n'
            '\nrun_copier() {\n  copier_dispatch "$@"\n}\n'
        )

    def test_a_copier_predicate_that_asks_where_copier_is_is_accepted(self) -> None:
        """A predicate the fixture never runs as an operation may ask."""

        self.sourced = {
            self.LIBRARY: "copier_available() {\n"
            "  command -v copier >/dev/null 2>&1\n"
            "}\n"
        }
        try:
            self.assert_accepted(self.with_library())
        finally:
            self.sourced = self.library()

    def test_a_copier_predicate_that_names_no_copier_is_rejected(self) -> None:
        self.sourced = {self.LIBRARY: "copier_available() {\n  return 0\n}\n"}
        try:
            self.assert_rejected(
                self.with_library(),
                RULE_COMMAND_SHADOWING,
                "declares the Copier wrapper `copier_available` with a body "
                "that names no Copier command",
            )
        finally:
            self.sourced = self.library()

    def test_an_anchor_value_this_checker_was_not_given_is_unbound(self) -> None:
        """A value that mentions the invocation may still expand elsewhere.

        The anchor is read as written, so a value that names a positional
        parameter in a branch it never takes binds no library.
        """

        self.assert_rejected(
            self.with_library().replace(
                "root=$1\n",
                "root=$(CDPATH= cd -- \"$tmp\" && pwd -P || printf '%s' \"$0\")\n",
                1,
            ),
            RULE_COMMAND_SHADOWING,
            "sources a path this checker was not given",
        )

    def test_a_source_whose_operand_is_not_written_is_rejected(self) -> None:
        self.assert_rejected(
            COMPLIANT + '\n. "$library"\n',
            RULE_COMMAND_SHADOWING,
            "sources a path this checker was not given",
        )

    def test_the_source_keyword_is_read_as_a_source(self) -> None:
        self.assert_rejected(
            COMPLIANT + '\nsource "$root/tests/lib-other.sh"\n',
            RULE_COMMAND_SHADOWING,
            "sources a path this checker was not given",
        )

    def test_a_source_written_inside_a_body_is_read(self) -> None:
        """A body the shell runs includes its file into the whole shell."""

        self.sourced = self.library("\ngrep() { :; }\n")
        try:
            self.assert_rejected(
                COMPLIANT
                + '\nload_helpers() {\n  . "$root/tests/lib-fixture.sh"\n}\n'
                + "load_helpers\n",
                RULE_COMMAND_SHADOWING,
                "declares `grep` as a function",
            )
        finally:
            self.sourced = self.library()

    def test_a_body_the_graph_resolves_no_call_for_is_read(self) -> None:
        """A body a trap action reaches includes its file just as a call does."""

        self.sourced = self.library("\ngrep() { :; }\n")
        try:
            self.assert_rejected(
                COMPLIANT
                + '\nload_helpers() {\n  . "$root/tests/lib-fixture.sh"\n}\n'
                + "trap load_helpers USR1\n",
                RULE_COMMAND_SHADOWING,
                "declares `grep` as a function",
            )
        finally:
            self.sourced = self.library()

    def test_a_case_pattern_is_not_read_as_a_source(self) -> None:
        """A `.` written as a `case` pattern is no command word at all."""

        self.assert_accepted(
            COMPLIANT
            + '\ncase "$candidate" in\n  .|..|./*) exit 1 ;;\n  *) : ;;\nesac\n'
        )

    def test_a_library_the_checked_projections_reject_is_reported(self) -> None:
        self.sourced = {self.LIBRARY: "cat <<<here\n"}
        try:
            self.assert_rejected(
                self.with_library(),
                RULE_STRUCTURE,
                "the checked projections rejected the sourced bytes",
            )
        finally:
            self.sourced = self.library()

    def test_a_library_is_read_once_however_often_it_is_sourced(self) -> None:
        self.sourced = self.library("\ngrep() { :; }\n")
        try:
            reported = [
                finding
                for finding in check(
                    COMPLIANT + self.SOURCING + self.SOURCING,
                    self.declared,
                    self.sourced,
                )
                if finding.rule == RULE_COMMAND_SHADOWING
            ]
            self.assertEqual(len(reported), 1, self.messages(COMPLIANT))
        finally:
            self.sourced = self.library()

    def test_the_bound_set_is_the_one_this_checker_ships_beside(self) -> None:
        libraries = copier_fixture_validator.read_libraries()
        self.assertEqual(
            tuple(libraries), copier_fixture_validator.SOURCED_LIBRARY_PATHS
        )
        for text in libraries.values():
            self.assertTrue(text.strip())

    def test_a_root_without_the_bound_library_binds_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(
                copier_fixture_validator.read_libraries(Path(directory)), {}
            )

    def test_supplied_library_bytes_are_decoded(self) -> None:
        self.sourced = {self.LIBRARY: self.LIBRARY_TEXT.encode("utf-8")}
        try:
            self.assert_accepted(self.with_library())
        finally:
            self.sourced = self.library()


class NameBindingTest(unittest.TestCase):
    """The surfaces that decide which names a fixture may bind.

    Every case here is a spelling one of the stopped review rounds reported. A
    name a fixture may bind through any surface must be reported unsettled, and
    a surface written in a form the checker does not enumerate must leave the
    name unsettled rather than settled.
    """

    def build(self, body: str):
        """Return the derived fixture for one written body."""

        text = "#!/bin/sh\nset -eu\n" + body
        records = shell_lexical.project(text)
        table = shell_functions.derive(records)
        graph = shell_execution.derive(records, table)
        return copier_fixture_validator._Fixture(text, records, table, graph)

    def unsettled(self, body: str) -> frozenset:
        """Return every name the checker cannot settle in one written body."""

        return self.build(body).unsettled_names()

    def test_a_standalone_assignment_settles_its_name(self):
        self.assertNotIn("dest", self.unsettled('dest=/tmp/one\nprintf %s "$dest"\n'))

    def test_a_second_assignment_written_as_one_command_unsettles_its_name(self):
        self.assertIn("other", self.unsettled('dest=/tmp/one other=/tmp/two\n'))

    def test_a_prefix_assignment_unsettles_its_name(self):
        self.assertIn("dest", self.unsettled('dest=/tmp/one printf %s x\n'))

    def test_a_prefix_assignment_written_with_a_redirection_unsettles_its_name(self):
        self.assertIn("dest", self.unsettled('dest=>/dev/null printf %s x\n'))

    def test_a_prefix_assignment_written_with_a_substitution_unsettles_its_name(self):
        self.assertIn(
            "dest",
            self.unsettled('dest=/tmp/one other=$(printf x) printf %s y\n'),
        )

    def test_a_prefix_assignment_written_with_a_quoted_value_unsettles_its_name(self):
        self.assertIn("dest", self.unsettled('dest="/tmp/one; two" printf %s x\n'))

    def test_a_quoted_name_opens_an_assignment(self):
        self.assertIn("dest", self.unsettled('de"st"=/tmp/one printf %s x\n'))

    def test_a_quoted_equals_opens_no_assignment(self):
        self.assertNotIn("dest", self.unsettled('printf %s "dest=/tmp/one"\n'))

    def test_an_escaped_equals_opens_no_assignment(self):
        self.assertNotIn("dest", self.unsettled('printf %s dest\\=/tmp/one\n'))

    def test_an_assigning_command_unsettles_its_operand(self):
        self.assertIn("dest", self.unsettled('read -r dest\n'))

    def test_an_assigning_command_unsettles_a_quoted_operand(self):
        self.assertIn("dest", self.unsettled("read -r 'dest'\n"))

    def test_an_exported_name_is_unsettled(self):
        self.assertIn("dest", self.unsettled('export dest=/tmp/one\n'))

    def test_a_launcher_that_stays_in_the_shell_reads_what_it_launches(self):
        self.assertNotIn(
            "dest", self.unsettled('dest=/tmp/one\ncommand true dest\n')
        )
        self.assertIn("dest", self.unsettled('command read -r dest\n'))
        self.assertIn("dest", self.unsettled('command "$reader" dest\n'))

    def test_a_launcher_that_forks_settles_a_bare_operand(self):
        self.assertNotIn(
            "dest", self.unsettled('dest=/tmp/one\nenv dest true\n')
        )

    def test_a_command_word_carrying_a_slash_settles_a_bare_operand(self):
        self.assertNotIn(
            "dest", self.unsettled('dest=/tmp/one\n"$helper/run.sh" dest\n')
        )

    def test_a_command_reached_through_a_name_unsettles_its_operand(self):
        self.assertIn("dest", self.unsettled('reader=read\n"$reader" -r dest\n'))

    def test_a_command_reached_through_two_names_unsettles_its_operand(self):
        self.assertIn(
            "dest",
            self.unsettled('first=read\nsecond=$first\n"$second" -r dest\n'),
        )

    def test_a_declared_assigning_command_still_unsettles_its_operand(self):
        self.assertIn(
            "dest",
            self.unsettled('read() { :; }\nread dest\n'),
        )

    def test_a_dynamic_operand_of_an_assigning_command_unsettles_every_name(self):
        unsettled = self.unsettled(
            'dest=/tmp/one\nname=dest=/evil\nexport $name\n'
        )
        self.assertIn("dest", unsettled)
        self.assertIn("name", unsettled)

    def test_a_dynamic_operand_of_an_unresolvable_command_unsettles_every_name(self):
        unsettled = self.unsettled(
            'dest=/tmp/one\nrunner=export\nvalue=dest=/evil\n"$runner" "$value"\n'
        )
        self.assertIn("dest", unsettled)

    def test_a_dynamic_named_option_target_unsettles_every_name(self):
        self.assertIn(
            "dest",
            self.unsettled('dest=/tmp/one\nptr=dest\nprintf -v "$ptr" %s /evil\n'),
        )

    def test_a_sourced_path_operand_settles_its_names(self):
        self.assertNotIn(
            "dest",
            self.unsettled('dest=/tmp/one\nlib=/tmp/lib.sh\n. "$lib"\n'),
        )

    def test_a_loop_head_unsettles_its_name(self):
        self.assertIn("dest", self.unsettled('for dest in a b; do :; done\n'))

    def test_a_continued_loop_head_unsettles_its_name(self):
        self.assertIn("dest", self.unsettled('for \\\n  dest in a b; do :; done\n'))

    def test_a_name_a_shell_keeps_itself_is_unsettled(self):
        self.assertIn("PWD", self.unsettled('printf %s "$PWD"\n'))
        self.assertIn("IFS", self.unsettled('printf %s "$IFS"\n'))

    def test_a_first_assignment_written_under_a_condition_is_unsettled(self):
        self.assertIn(
            "dest",
            self.unsettled('if false; then\n  dest=/tmp/one\nfi\n'),
        )

    def test_a_first_assignment_written_in_a_function_body_is_unsettled(self):
        self.assertIn(
            "dest",
            self.unsettled('run() {\n  dest=/tmp/one\n}\nrun\n'),
        )

    def test_a_later_assignment_in_a_function_body_is_unsettled(self):
        self.assertIn(
            "dest",
            self.unsettled('dest=/tmp/one\nrun() {\n  dest=/tmp/two\n}\nrun\n'),
        )

    def test_a_separator_written_inside_a_quoted_span_opens_no_command(self):
        self.assertNotIn(
            "dest",
            self.unsettled('printf %s "; dest=/tmp/one"\ndest=/tmp/two\n'),
        )

    def test_a_command_written_after_a_separator_is_read_as_its_own(self):
        self.assertIn("dest", self.unsettled('printf %s x; dest=/tmp/one printf %s y\n'))

    def test_a_reserved_word_never_hides_a_prefix_assignment(self):
        self.assertIn("dest", self.unsettled('if dest=/tmp/one printf %s x; then :; fi\n'))

    def test_a_heredoc_body_opens_no_command(self):
        self.assertNotIn(
            "dest",
            self.unsettled('cat <<EOF\ndest=/tmp/one printf\nEOF\ndest=/tmp/two\n'),
        )

    def test_a_redirection_target_is_not_a_command_word(self):
        self.assertNotIn(
            "dest",
            self.unsettled('printf %s x >/tmp/out\ndest=/tmp/two\n'),
        )

    def test_an_assignment_written_under_a_condition_is_unsettled(self):
        self.assertIn(
            "dest",
            self.unsettled('dest=/tmp/one\nif false; then dest=/tmp/two; fi\n'),
        )

    def test_an_assignment_written_in_a_loop_body_is_unsettled(self):
        self.assertIn(
            "dest",
            self.unsettled('dest=/tmp/one\nfor i in a; do dest=/tmp/two; done\n'),
        )

    def test_an_assignment_written_in_a_case_branch_is_unsettled(self):
        self.assertIn(
            "dest",
            self.unsettled('dest=/tmp/one\ncase x in y) dest=/tmp/two;; esac\n'),
        )

    def test_an_assignment_written_behind_an_or_is_unsettled(self):
        self.assertIn(
            "dest", self.unsettled('dest=/tmp/one\nfalse || dest=/tmp/two\n')
        )

    def test_an_assignment_written_in_a_subshell_is_unsettled(self):
        self.assertIn("dest", self.unsettled('dest=/tmp/one\n( dest=/tmp/two )\n'))

    def test_an_assignment_written_in_a_pipeline_is_unsettled(self):
        self.assertIn(
            "dest",
            self.unsettled('dest=/tmp/one\nprintf %s x | { dest=/tmp/two; }\n'),
        )

    def test_an_assignment_written_behind_an_ampersand_is_unsettled(self):
        self.assertIn(
            "dest", self.unsettled('dest=/tmp/one\n{ dest=/tmp/two; } &\n')
        )

    def test_a_parenthesis_written_inside_a_quoted_span_detaches_nothing(self):
        self.assertNotIn(
            "dest",
            self.unsettled('printf %s "("\ndest=/tmp/one\nprintf %s "$dest"\n'),
        )

    def test_an_assigning_parameter_expansion_is_unsettled(self):
        self.assertIn(
            "dest",
            self.unsettled('dest=/tmp/one\nprintf %s "${dest:=/tmp/two}"\n'),
        )

    def test_a_reading_parameter_expansion_settles_its_name(self):
        self.assertNotIn(
            "dest",
            self.unsettled('dest=/tmp/one\nprintf %s "${dest:-/tmp/two}"\n'),
        )

    def test_an_arithmetic_expansion_unsettles_every_name_it_writes(self):
        self.assertIn("dest", self.unsettled('dest=1\n: $((dest + 1))\n'))

    def test_a_trap_string_unsettles_the_name_it_assigns(self):
        self.assertIn(
            "dest",
            self.unsettled('dest=/tmp/one\ntrap "dest=/tmp/two" EXIT\n'),
        )

    def test_an_attached_named_option_unsettles_its_name(self):
        self.assertIn(
            "dest", self.unsettled('dest=/safe\nprintf -vdest "%s" /evil\n')
        )

    def test_a_detached_named_option_unsettles_its_name(self):
        self.assertIn(
            "dest", self.unsettled('dest=/safe\nprintf -v dest "%s" /evil\n')
        )

    def test_an_arithmetic_expansion_in_a_heredoc_body_is_unsettled(self):
        self.assertIn(
            "dest",
            self.unsettled('dest=1\ncat <<EOF >/dev/null\n$((dest=5))\nEOF\n'),
        )

    def test_a_parameter_assignment_in_a_heredoc_body_is_unsettled(self):
        self.assertIn(
            "dest",
            self.unsettled('cat <<EOF >/dev/null\n${dest:=/tmp/evil}\nEOF\n'),
        )

    def test_a_continued_assignment_name_is_unsettled(self):
        self.assertIn("dest", self.unsettled('de\\\nst=/evil\n'))

    def test_a_redirected_group_written_behind_an_ampersand_is_unsettled(self):
        self.assertIn(
            "dest", self.unsettled('{ dest=/tmp/two; } >/dev/null &\n')
        )

    def test_a_redirected_group_written_beside_a_pipe_is_unsettled(self):
        self.assertIn(
            "dest", self.unsettled('{ dest=/tmp/two; } 2>/dev/null | cat\n')
        )

    def test_a_group_written_with_a_heredoc_behind_an_ampersand_is_unsettled(self):
        self.assertIn(
            "dest",
            self.unsettled('{ dest=/tmp/two; } <<EOF &\nbody\nEOF\n'),
        )

    def test_a_redirected_group_that_is_not_detached_settles_its_name(self):
        self.assertNotIn(
            "dest",
            self.unsettled(
                'dest=/tmp/one\n{ dest=/tmp/two; } >/dev/null\nprintf %s "$dest"\n'
            ),
        )

    def test_a_descriptor_variable_redirection_unsettles_its_name(self):
        self.assertIn(
            "dest",
            self.unsettled('dest=/tmp/one\nexec {dest}>/dev/null\n'),
        )

    def test_an_unaccepted_construct_unsettles_every_written_name(self):
        fixture = self.build('dest=/tmp/one\nexec {fd}>/dev/null\nother=/tmp/two\n')
        self.assertTrue(fixture.unaccepted_constructs())
        unsettled = fixture.unsettled_names()
        self.assertIn("dest", unsettled)
        self.assertIn("other", unsettled)
        self.assertIn("fd", unsettled)

    def test_a_brace_expansion_is_an_unaccepted_construct(self):
        self.assertTrue(self.build('printf %s a{b,c}\n').unaccepted_constructs())

    def test_a_quoted_brace_is_an_accepted_construct(self):
        fixture = self.build('dest=/tmp/one\nprintf %s "{}"\n')
        self.assertEqual(fixture.unaccepted_constructs(), ())
        self.assertNotIn("dest", fixture.unsettled_names())

    def test_a_group_brace_is_an_accepted_construct(self):
        fixture = self.build('dest=/tmp/one\n{ printf %s x; }\n')
        self.assertEqual(fixture.unaccepted_constructs(), ())
        self.assertNotIn("dest", fixture.unsettled_names())

    def test_the_accepted_constructs_cover_the_forms_the_grammar_reads(self):
        fixture = self.build(
            'dest=/tmp/one\n'
            "printf '%s' \"$dest\" >/dev/null 2>&1\n"
            'cat <<EOF | { printf %s x; } || true\nbody\nEOF\n'
            '# a comment\n'
            'run() { printf %s "$(printf y)"; }\n'
            'for item in a b; do run; done\n'
        )
        self.assertEqual(fixture.unaccepted_constructs(), ())

    def test_an_expanded_word_denotes_no_settled_text(self):
        text = shell_lexical.project('"$dest"').tokens[0]
        self.assertIsNone(copier_fixture_validator._token_text(text))

    def test_a_quoted_word_denotes_its_inner_text(self):
        text = shell_lexical.project('"de"st').tokens[0]
        self.assertEqual(copier_fixture_validator._token_text(text), "dest")


class WordGrammarTest(unittest.TestCase):
    """Prove a word settles only when the modelled grammar writes all of it."""

    module = copier_fixture_validator

    def fixture(self, source: str):
        records = self.module.shell_lexical.project(source)
        table = self.module.shell_functions.derive(records)
        graph = self.module.shell_execution.derive(records, table)
        return self.module._Fixture(source, records, table, graph)

    def bind(self, values: dict[str, tuple[str, ...]] | None):
        """Return one binding map holding only values written as plain text.

        A substitution is bound only where an assignment runs it once, which
        this helper cannot express, so it refuses a value that carries one and
        every test that needs one builds a fixture instead.
        """

        bindings: dict[str, object] = {}
        for name, texts in (values or {}).items():
            settled: list[object] = []
            for index, text in enumerate(texts):
                parts = self.module._word_parts(text, f"a{name}{index}", splits=False)
                if parts is None:
                    settled = None
                    break
                self.assertFalse(
                    self.module._carries_substitution((parts,)),
                    "bind() holds only values written as plain text",
                )
                grown = self.module._resolve_parts(parts, bindings, frozenset())
                if grown is None:
                    settled = None
                    break
                settled.extend(grown)
            bindings[name] = None if settled is None else tuple(settled)
        return bindings

    def settle(self, word: str, values: dict[str, tuple[str, ...]] | None = None):
        return self.module._settle_word(word, self.bind(values), origin=word)

    def settled_word(self, source: str, word: str, command: str = "printf"):
        """Return every path one word names where one fixture command runs."""

        fixture = self.fixture(source)
        operation = next(
            item
            for item in fixture.operations
            if item.reachable and item.name == command
        )
        return self.module._settle_written_word(fixture, operation, word)

    def test_a_word_outside_the_grammar_is_unproven(self) -> None:
        for word in (
            '"$1"',
            '"$@"',
            '"$*/x"',
            '"$$/x"',
            '"$!/x"',
            '"$-/x"',
            '"$?/x"',
            '"${x:-ln}"',
            '"${x#/a}"',
            "'$dest'",
            "'a\"b'",
            '"$tmp/*"',
            '"$tmp/a?"',
            '"$tmp/[ab]"',
            '"~/p"',
            '"$tmp/a\\b"',
            '"$tmp/a b"',
            '"$tmp',
            '""',
            "",
            '"$((1 + 1))/x"',
            '"$(printf %s $(echo x))"',
            '"$(printf %s x"',
            '"a;b"',
            '"a|b"',
            '"a>b"',
            '"a&b"',
        ):
            with self.subTest(word=word):
                self.assertEqual(
                    self.settle(word, {"tmp": ("/tmp",), "dest": ("/tmp/a",)}),
                    frozenset(),
                )

    def test_an_unquoted_expansion_in_a_command_word_is_unproven(self) -> None:
        """A shell splits an unquoted expansion into fields it may not model."""

        for word in ("$tmp/x", "${tmp}/x", "$(printf %s /tmp)/x", "a$tmp"):
            with self.subTest(word=word):
                self.assertEqual(self.settle(word, {"tmp": ("/tmp",)}), frozenset())

    def test_an_assignment_reads_its_value_without_splitting_it(self) -> None:
        settled = self.settled_word(
            'base=$(pwd -P)\nprintf %s "$base/x"\n', '"$base/x"'
        )
        self.assertEqual(len(settled), 1)
        self.assertEqual(next(iter(settled))[1][1:], ("x",))

    def test_a_backquote_never_settles(self) -> None:
        self.assertEqual(self.settle('"`printf %s /tmp`/x"'), frozenset())

    def test_a_modelled_word_settles_to_its_segments(self) -> None:
        for word, values, expected in (
            ("/a/b", {}, (True, ("a", "b"))),
            ('"$tmp/p"', {"tmp": ("/tmp",)}, (True, ("tmp", "p"))),
            ('"${tmp}/p"', {"tmp": ("/tmp",)}, (True, ("tmp", "p"))),
            ("/a//b/./c/", {}, (True, ("a", "b", "c"))),
            ('"$t/x"', {}, (False, ("$t", "x"))),
        ):
            with self.subTest(word=word):
                self.assertEqual(self.settle(word, values), frozenset({expected}))

    def test_a_substitution_in_a_command_word_is_unproven(self) -> None:
        """A command word runs its substitution again each time it runs."""

        for word in ('"$(cat anchor)/a"', '"$(pwd -P)/a"'):
            with self.subTest(word=word):
                self.assertEqual(
                    self.settled_word(f"printf %s {word}\n", word), frozenset()
                )

    def test_a_bound_substitution_settles_as_one_opaque_segment(self) -> None:
        source = 'base=$(CDPATH= cd -- /tmp && pwd -P)\nprintf %s "$base/x"\n'
        settled = self.settled_word(source, '"$base/x"')
        self.assertEqual(len(settled), 1)
        anchored, segments = next(iter(settled))
        self.assertTrue(anchored)
        self.assertTrue(self.module._carries_expansion(segments[0]))
        self.assertEqual(segments[1:], ("x",))

    def test_only_the_modelled_command_list_anchors_a_substitution(self) -> None:
        """Any other list may write a path the working directory decides."""

        for value in (
            "$(mktemp -d)",
            "$(printf %s x; pwd)",
            "$(printf .)",
            "$(cd /tmp && printf %s x)",
        ):
            source = f'base={value}\nprintf %s "$base/x"\n'
            with self.subTest(value=value):
                settled = self.settled_word(source, '"$base/x"')
                self.assertEqual({anchored for anchored, _ in settled}, {False})

    def test_a_declared_command_never_anchors_a_substitution(self) -> None:
        source = (
            "pwd() { printf %s relative; }\n"
            "base=$(cd /tmp && pwd)\n"
            'printf %s "$base/x"\n'
        )
        settled = self.settled_word(source, '"$base/x"')
        self.assertEqual({anchored for anchored, _ in settled}, {False})

    def test_a_special_parameter_is_never_settled(self) -> None:
        """A special parameter names text no assignment in the fixture writes."""

        for word in ('"$0"', '"$1/x"', '"$@"', '"$#"', '"$?"', '"$$/x"', '"$!"'):
            with self.subTest(word=word):
                self.assertEqual(self.settle(word), frozenset())

    def test_a_substitution_list_writing_more_than_one_command_is_unanchored(
        self,
    ) -> None:
        """Only the one modelled list anchors a path; every other list does not."""

        for value in (
            "$(cd /tmp && pwd && printf %s /evil)",
            "$(pwd; printf %s /evil)",
            "$(printf %s /evil && pwd)",
            "$(cd /tmp && pwd | tr -d x)",
        ):
            with self.subTest(value=value):
                source = f"base={value}\nprintf %s \"$base/x\"\n"
                settled = self.settled_word(source, '"$base/x"')
                self.assertNotIn(True, {anchored for anchored, _ in settled})

    def test_the_committed_fixture_anchors_only_the_modelled_list(self) -> None:
        """The committed fixture writes both a modelled and an unmodelled list."""

        source = Path("tests/copier-update.sh").read_text(encoding="utf-8")
        fixture = self.fixture(source)
        bindings = fixture.bindings_before(len(source))
        unsettled = fixture.unsettled_names()
        self.assertEqual(
            self.module._settle_word('"$root"', bindings, unsettled),
            frozenset(),
            "a nested substitution is outside the grammar",
        )
        self.assertEqual(
            {anchored for anchored, _ in self.module._settle_word(
                '"$tmp/x"', bindings, unsettled
            )},
            {True},
            "the modelled command list anchors the path it writes",
        )

    def test_a_parent_segment_is_never_modelled(self) -> None:
        """A parent segment names a directory the links above it decide."""

        for word in ('"$t/.."', "../a", "/a/b/../c", "/a/..", '"/tmp/a/../b"'):
            with self.subTest(word=word):
                self.assertEqual(self.settle(word), frozenset())

    def test_every_value_a_name_may_hold_is_settled(self) -> None:
        """A name bound more than once settles to every value it may hold."""

        self.assertEqual(
            self.settle('"$dest/x"', {"dest": ("/tmp/one", "/tmp/two")}),
            frozenset({(True, ("tmp", "one", "x")), (True, ("tmp", "two", "x"))}),
        )

    def test_a_name_the_binding_surfaces_report_unsettled_is_unproven(self) -> None:
        """A name a branch may rebind is reported unsettled, so it proves nothing.

        The binding surfaces report which names this checker settles, and a
        name written under a condition is one of them. The parts each value
        carries are still enumerated, but the word that reads the name is
        unproven, because a value this checker never settles may name any path
        at all.
        """

        source = (
            "dest=/tmp/one\n"
            "if [ -d /tmp ]; then\n  dest=/tmp/two\nfi\n"
            'printf %s "$dest"\n'
        )
        fixture = self.fixture(source)
        self.assertIn("dest", fixture.unsettled_names())
        self.assertEqual(self.settled_word(source, '"$dest"'), frozenset())

    def test_a_value_outside_the_grammar_leaves_the_word_unproven(self) -> None:
        self.assertEqual(self.settle('"$dest/x"', {"dest": ("/tmp/*",)}), frozenset())

    def test_a_value_is_read_where_the_assignment_is_written(self) -> None:
        """A shell settles a value once, not again where the name is read."""

        source = "y=/tmp/old\nx=$y\ny=/tmp/new\nprintf %s \"$x\"\n"
        self.assertEqual(
            self.settled_word(source, '"$x"'), frozenset({(True, ("tmp", "old"))})
        )

    def test_a_self_referential_value_terminates(self) -> None:
        source = 't=$t/x\nprintf %s "$t"\n'
        self.assertEqual(
            self.settled_word(source, '"$t"'), frozenset({(False, ("$t", "x"))})
        )

    def test_a_settlement_past_the_text_bound_is_unproven(self) -> None:
        values = {
            f"n{index}": tuple(f"/v{index}-{choice}" for choice in range(4))
            for index in range(4)
        }
        word = '"' + "".join(f"$n{index}" for index in range(4)) + '"'
        self.assertEqual(self.settle(word, values), frozenset())

    def test_a_long_word_settles_without_growing(self) -> None:
        """Repeated names settle once each rather than once per combination."""

        source = (
            "".join(f"n{index}=/a\n" for index in range(20))
            + 'printf %s "'
            + "/".join(f"$n{index}" for index in range(20))
            + '"\n'
        )
        word = '"' + "/".join(f"$n{index}" for index in range(20)) + '"'
        self.assertEqual(
            self.settled_word(source, word), frozenset({(True, ("a",) * 20)})
        )

    def test_a_call_site_value_reaches_a_function_body(self) -> None:
        source = (
            "dest=/tmp/first\n"
            'inner() { printf %s "$dest"; }\n'
            "outer() { inner; }\n"
            "dest=/tmp/second\n"
            "outer\n"
        )
        self.assertEqual(
            self.settled_word(source, '"$dest"'),
            frozenset({(True, ("tmp", "first")), (True, ("tmp", "second"))}),
        )

    def test_a_name_a_command_may_assign_is_never_settled(self) -> None:
        for assigning in (
            "export dest=/tmp/actual",
            "readonly dest=/tmp/actual",
            "read dest",
            "getopts x dest",
            'assign=export\n"$assign" dest=/tmp/actual',
            "command export dest=/tmp/actual",
            "printf -v dest /tmp/actual",
        ):
            source = f'dest=/tmp/outer\n{assigning}\nprintf %s "$dest"\n'
            with self.subTest(assigning=assigning):
                fixture = self.fixture(source)
                self.assertIn("dest", fixture.unsettled_names())

    def test_a_name_written_with_a_value_anywhere_is_never_settled(self) -> None:
        """Only the first assignment of one command is recorded in position."""

        for written in (
            "other=x dest=/tmp/new",
            'dest=/tmp/new other="a b" printf %s x',
            'export de"st"=/tmp/new',
            "unset dest",
        ):
            source = f'dest=/tmp/old\n{written}\nprintf %s "$dest"\n'
            with self.subTest(written=written):
                fixture = self.fixture(source)
                self.assertIn("dest", fixture.unsettled_names())
                self.assertEqual(self.settled_word(source, '"$dest"'), frozenset())

    def test_a_name_the_shell_keeps_itself_is_never_settled(self) -> None:
        """A shell changes these names where no assignment is written."""

        for name in ("PWD", "OLDPWD", "IFS", "OPTIND", "REPLY"):
            with self.subTest(name=name):
                fixture = self.fixture(f'printf %s "${name}/x"\n')
                self.assertIn(name, fixture.unsettled_names())
                self.assertEqual(
                    self.settled_word(f'printf %s "${name}/x"\n', f'"${name}/x"'),
                    frozenset(),
                )

    def test_a_name_a_function_body_assigns_is_never_settled(self) -> None:
        """A function runs where it is called, so its assignment reaches later."""

        source = (
            "set_dest() { dest=/tmp/new; }\n"
            "dest=/tmp/old\n"
            "set_dest\n"
            'printf %s "$dest"\n'
        )
        fixture = self.fixture(source)
        self.assertIn("dest", fixture.unsettled_names())
        self.assertEqual(self.settled_word(source, '"$dest"'), frozenset())

    def test_a_name_a_loop_head_binds_holds_the_head_words(self) -> None:
        """A loop head binds its name from the words written after `in`.

        The name is unsettled everywhere else, because a word written outside
        the loop reads whatever the assignments around it hold, but a word
        written under the loop reads one of the head words.
        """

        source = (
            "dest=/tmp/old\nfor dest in /tmp/new; do\n"
            '  printf %s "$dest"\ndone\n'
        )
        continued = (
            "dest=/tmp/old\nfor \\\n dest in /tmp/new; do\n"
            '  printf %s "$dest"\ndone\n'
        )
        for written in (source, continued):
            with self.subTest(written=written):
                fixture = self.fixture(written)
                self.assertIn("dest", fixture.unsettled_names())
                self.assertEqual(
                    self.settled_word(written, '"$dest"'),
                    frozenset({(True, ("tmp", "new"))}),
                )

    def test_a_loop_head_this_checker_cannot_read_settles_no_name(self) -> None:
        written = (
            'for dest in $(printf %s /tmp/new); do\n'
            '  printf %s "$dest"\ndone\n'
        )
        self.assertEqual(self.settled_word(written, '"$dest"'), frozenset())

    def test_a_prefix_assigned_name_is_never_settled(self) -> None:
        for prefix in (
            'dest=/tmp/new printf %s "$dest"',
            'dest=/tmp/new other=x printf %s "$dest"',
            'dest=/tmp/new \\\n  printf %s "$dest"',
        ):
            source = f'dest=/tmp/old\n{prefix}\n'
            with self.subTest(prefix=prefix):
                fixture = self.fixture(source)
                self.assertIn("dest", fixture.unsettled_names())

    def test_a_standalone_assignment_is_not_a_prefix_assignment(self) -> None:
        fixture = self.fixture('dest=/tmp/old\nprintf %s "$dest"\n')
        self.assertNotIn("dest", fixture.prefix_assigned_names())

    def test_two_paths_are_separate_only_when_written_text_keeps_them_apart(
        self,
    ) -> None:
        for left, right, expected in (
            ('"$x/a"', '"$x/b"', False),
            ('"/tmp/a"', '"/tmp/b"', True),
            ('"${x}a"', '"${x}/a"', False),
            ('"/tmp/a"', '"/tmp//a"', False),
            ('"/tmp/a/$tail"', '"/tmp/b/$tail"', False),
            ('"/tmp/a"', '"/tmp/a/b"', False),
            ('"/tmp/a"', '"/tmp/a"', False),
            ("project", "/tmp/project", False),
            ("project", "other", False),
            ('"$x/a"', '"/tmp/a"', False),
        ):
            with self.subTest(left=left, right=right):
                self.assertIs(
                    self.module._paths_are_lexically_separate(
                        self.settle(left), self.settle(right)
                    ),
                    expected,
                )

    def test_a_path_this_checker_cannot_anchor_is_never_separate(self) -> None:
        """A fixture may change the directory a relative path starts from."""

        source = (
            "base=$(printf .)\n"
            'printf %s "$base/scripts"\n'
            "cd scripts\n"
            'printf %s "$base/other"\n'
        )
        fixture = self.fixture(source)
        commands = [
            item
            for item in fixture.operations
            if item.reachable and item.name == "printf"
        ]
        left = self.module._settle_written_word(fixture, commands[0], '"$base/scripts"')
        right = self.module._settle_written_word(fixture, commands[1], '"$base/other"')
        self.assertTrue(left)
        self.assertTrue(right)
        self.assertFalse(self.module._paths_are_lexically_separate(left, right))

    def test_one_binding_read_twice_is_one_anchor(self) -> None:
        source = (
            'base=$(pwd -P)\nprintf %s "$base/a"\nprintf %s "$base/b"\n'
        )
        fixture = self.fixture(source)
        commands = [
            item
            for item in fixture.operations
            if item.reachable and item.name == "printf"
        ]
        left = self.module._settle_written_word(fixture, commands[0], '"$base/a"')
        right = self.module._settle_written_word(fixture, commands[1], '"$base/b"')
        self.assertTrue(
            self.module._paths_are_lexically_separate(left, right)
        )
        self.assertFalse(
            self.module._paths_are_lexically_separate(
                left,
                self.module._settle_written_word(
                    fixture, commands[1], '"$base/a/b"'
                ),
            )
        )

    def test_a_repeated_binding_never_anchors_a_comparison(self) -> None:
        """An assignment that may run again may hold another value."""

        source = (
            "if [ -d /tmp ]; then\n  base=$(pwd -P)\nfi\n"
            'printf %s "$base/a"\n'
        )
        self.assertEqual(self.settled_word(source, '"$base/a"'), frozenset())

    def test_an_unproven_side_is_never_separate(self) -> None:
        settled = self.settle("/tmp/a")
        self.assertFalse(
            self.module._paths_are_lexically_separate(settled, frozenset())
        )
        self.assertFalse(
            self.module._paths_are_lexically_separate(frozenset(), settled)
        )

    def test_the_committed_fixture_settles_the_paths_it_writes(self) -> None:
        """The words are read from the fixture rather than written here."""

        source = (ROOT / "tests" / "copier-update.sh").read_text(encoding="utf-8")
        fixture = self.fixture(source)
        self.assertNotIn("tmp", fixture.unsettled_names())
        written: dict[str, tuple[object, frozenset]] = {}
        for operation in fixture.operations:
            if not operation.reachable:
                continue
            for word in operation.text.split():
                if not word.startswith('"$tmp/') or word in written:
                    continue
                settled = self.module._settle_written_word(fixture, operation, word)
                if len(settled) == 1:
                    written[word] = (operation, settled)
        self.assertGreaterEqual(len(written), 2)
        for word, (_, settled) in written.items():
            with self.subTest(word=word):
                anchored, segments = next(iter(settled))
                self.assertTrue(anchored)
                self.assertTrue(self.module._carries_expansion(segments[0]))
                self.assertEqual(
                    len(segments), len(word.strip('"').rstrip("/").split("/"))
                )
        paths = [settled for _, settled in written.values()]
        separate = [
            self.module._paths_are_lexically_separate(left, right)
            for index, left in enumerate(paths)
            for right in paths[index + 1 :]
        ]
        self.assertIn(True, separate)
        first = next(iter(written.values()))[1]
        anchored, segments = next(iter(first))
        inside = (anchored, segments + ("inside",))
        self.assertFalse(
            self.module._paths_are_lexically_separate(first, frozenset({inside}))
        )


class AliasCollectionTest(unittest.TestCase):
    """Prove an alias is collected only from the modelled command grammar."""

    module = copier_fixture_validator

    def fixture(self, source: str):
        records = self.module.shell_lexical.project(source)
        table = self.module.shell_functions.derive(records)
        graph = self.module.shell_execution.derive(records, table)
        return self.module._Fixture(source, records, table, graph)

    def aliases(self, body: str):
        source = "#!/bin/sh\nset -eu\n" + body
        links, unplaced = self.module._symlinked_paths(self.fixture(source))
        return frozenset(self.module._path_text(path) for path in links), unplaced

    def placed(self, body: str) -> frozenset[str]:
        links, unplaced = self.aliases(body)
        self.assertFalse(unplaced, "expected every alias of this fixture to be placed")
        return links

    def test_a_written_symbolic_link_places_both_readings(self) -> None:
        """A second operand may name a directory, so both readings are placed."""

        self.assertEqual(
            self.placed("ln -s /tmp/one /tmp/two\n"),
            frozenset({"/tmp/two", "/tmp/two/one"}),
        )

    def test_a_hard_link_places_no_alias(self) -> None:
        self.assertEqual(self.placed("ln /tmp/one /tmp/two\n"), frozenset())

    def test_a_plain_copy_places_no_alias(self) -> None:
        self.assertEqual(self.placed("cp /tmp/one /tmp/two\n"), frozenset())

    def test_every_symbolic_option_spelling_is_read(self) -> None:
        for option in ("-s", "-sf", "-fs", "--symbolic", "--sym", "--s"):
            with self.subTest(option=option):
                self.assertIn(
                    "/tmp/two", self.placed(f"ln {option} /tmp/one /tmp/two\n")
                )

    def test_a_launched_link_is_read_as_a_link(self) -> None:
        for launcher in ("env", "command", "exec", "nohup"):
            with self.subTest(launcher=launcher):
                self.assertIn(
                    "/tmp/two",
                    self.placed(f"{launcher} ln -s /tmp/one /tmp/two\n"),
                )

    def test_a_command_word_this_checker_cannot_read_is_held_to_the_link_form(
        self,
    ) -> None:
        """An unread command word may name a link, so a link spelling is read."""

        linked, unplaced = self.aliases('runner=/bin/ln\n"$runner" -s /tmp/one /tmp/two\n')
        self.assertEqual(linked, frozenset({"/tmp/two", "/tmp/two/one"}))
        self.assertFalse(unplaced)

    def test_an_unread_command_word_without_a_link_option_places_no_alias(self) -> None:
        self.assertEqual(
            self.placed('runner=/bin/cat\n"$runner" -n /tmp/one\n'), frozenset()
        )

    def test_an_option_this_checker_cannot_read_leaves_the_alias_unplaced(self) -> None:
        """A link option written through an expansion may ask for a link."""

        for body in (
            "opt=-s\nln \"$opt\" /tmp/one /tmp/two\n",
            "opt=-s\nln \"${opt}\" /tmp/one /tmp/two\n",
            'ln "$(printf %s -s)" /tmp/one /tmp/two\n',
            'opt=--symbolic\ncp "$opt" /tmp/one /tmp/two\n',
        ):
            with self.subTest(body=body):
                self.assertTrue(self.aliases(body)[1])

    def test_a_word_written_with_a_slash_is_never_read_as_an_option(self) -> None:
        """A slash is not an option letter, so such a word is an operand."""

        self.assertEqual(
            self.placed('base=/tmp\ncp "$base/one" "$base/two"\n'), frozenset()
        )

    def test_an_operand_settling_to_an_anchored_path_is_never_an_option(self) -> None:
        self.assertEqual(
            self.placed('one=/tmp/one\ntwo=/tmp/two\nln "$one" "$two"\n'), frozenset()
        )

    def test_a_copy_keeps_a_link_whatever_case_the_option_is_written_in(self) -> None:
        """`-R` is a synonym of `-r`, and `-P` asks for no dereference."""

        for option in ("-R", "-P", "-r", "-a", "-d", "-p"):
            with self.subTest(option=option):
                self.assertIn(
                    "/tmp/three",
                    self.placed(
                        "ln -s /tmp/one /tmp/two\n"
                        f"cp {option} /tmp/two /tmp/three\n"
                    ),
                )

    def test_a_long_symbolic_option_is_read_in_every_spelling(self) -> None:
        for option in ("--symbolic", "--symbolic-link", "--sym"):
            with self.subTest(option=option):
                self.assertIn(
                    "/tmp/two",
                    self.placed(f'runner=/bin/cp\n"$runner" {option} /tmp/one /tmp/two\n'),
                )

    def test_a_target_directory_option_leaves_the_alias_unplaced(self) -> None:
        for option in ("-t", "-st", "--target-directory", "--target", "--t"):
            with self.subTest(option=option):
                _, unplaced = self.aliases(f"ln -s {option} /tmp/dir /tmp/one\n")
                self.assertTrue(unplaced)

    def test_an_operand_count_this_checker_does_not_read_leaves_it_unplaced(
        self,
    ) -> None:
        for body in (
            "ln -s /tmp/one\n",
            "ln -s /tmp/one /tmp/two /tmp/dir\n",
        ):
            with self.subTest(body=body):
                self.assertTrue(self.aliases(body)[1])

    def test_an_operand_this_checker_cannot_settle_leaves_it_unplaced(self) -> None:
        self.assertTrue(self.aliases('ln -s /tmp/one "$(printf %s /tmp/two)"\n')[1])

    def test_a_bare_double_dash_ends_the_options(self) -> None:
        self.assertEqual(
            self.placed("ln -s -- /tmp/one /tmp/two\n"),
            frozenset({"/tmp/two", "/tmp/two/one"}),
        )

    def test_a_move_carries_a_tracked_alias(self) -> None:
        self.assertEqual(
            self.placed("ln -s /tmp/one /tmp/two\nmv /tmp/two /tmp/three\n"),
            frozenset(
                {"/tmp/two", "/tmp/two/one", "/tmp/three", "/tmp/three/two"}
            ),
        )

    def test_a_move_option_never_stops_the_alias(self) -> None:
        """A move carries a link whatever options are written with it."""

        self.assertIn(
            "/tmp/three",
            self.placed("ln -s /tmp/one /tmp/two\nmv -f /tmp/two /tmp/three\n"),
        )

    def test_a_copy_keeps_a_link_only_with_a_preserving_option(self) -> None:
        kept = self.placed("ln -s /tmp/one /tmp/two\ncp -a /tmp/two /tmp/three\n")
        self.assertIn("/tmp/three", kept)
        stored = self.placed("ln -s /tmp/one /tmp/two\ncp /tmp/two /tmp/three\n")
        self.assertNotIn("/tmp/three", stored)

    def test_a_copy_option_this_checker_cannot_read_leaves_it_unplaced(self) -> None:
        self.assertTrue(
            self.aliases("ln -s /tmp/one /tmp/two\ncp --reflink /tmp/two /tmp/three\n")[1]
        )

    def test_a_relocation_this_checker_cannot_read_leaves_it_unplaced(self) -> None:
        for body in (
            "ln -s /tmp/one /tmp/two\nmv -t /tmp/dir /tmp/two\n",
            "ln -s /tmp/one /tmp/two\nmv /tmp/two\n",
            'ln -s /tmp/one /tmp/two\nmv /tmp/two "$(printf %s /tmp/three)"\n',
        ):
            with self.subTest(body=body):
                self.assertTrue(self.aliases(body)[1])

    def test_a_relocation_of_an_untracked_path_carries_nothing(self) -> None:
        self.assertEqual(
            self.placed("ln -s /tmp/one /tmp/two\nmv /other/four /other/five\n"),
            frozenset({"/tmp/two", "/tmp/two/one"}),
        )

    def test_a_chain_of_relocations_is_followed(self) -> None:
        carried = self.placed(
            "ln -s /tmp/one /tmp/two\n"
            "mv /tmp/two /tmp/three\n"
            "mv /tmp/three /tmp/four\n"
        )
        self.assertIn("/tmp/four", carried)

    def test_an_alias_this_checker_cannot_anchor_holds_every_path(self) -> None:
        """An unanchored alias names a directory no written text decides."""

        source = '#!/bin/sh\nset -eu\nln -s /tmp/one "$outside/two"\n'
        links, _ = self.module._symlinked_paths(self.fixture(source))
        self.assertTrue(links, "an unanchored alias is still collected")
        self.assertTrue(
            self.module._may_be_linked(links, frozenset({(True, ("other", "place"))})),
            "an unanchored alias may name any destination",
        )

    def test_a_path_a_link_holds_may_be_named_by_it(self) -> None:
        link = (True, ("tmp", "two"))
        self.assertTrue(self.module._may_be_ancestor(link, (True, ("tmp", "two", "x"))))
        self.assertFalse(self.module._may_be_ancestor(link, (True, ("tmp",))))
        self.assertFalse(self.module._may_be_ancestor(link, (True, ("tmp", "three"))))
        self.assertTrue(self.module._may_be_ancestor(link, link))

    def test_a_segment_written_with_an_expansion_never_holds_a_path(self) -> None:
        self.assertFalse(
            self.module._holds_path((True, ("$a",)), (True, ("$a", "x")))
        )

    def test_the_committed_fixture_places_every_alias_it_writes(self) -> None:
        source = Path("tests/copier-update.sh").read_text(encoding="utf-8")
        links, unplaced = self.module._symlinked_paths(self.fixture(source))
        self.assertFalse(unplaced, "the committed fixture writes only modelled aliases")
        self.assertTrue(links, "the committed fixture writes a symbolic link")


if __name__ == "__main__":
    unittest.main()
