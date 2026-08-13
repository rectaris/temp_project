"""External-service policy tests."""

import subprocess
import sys
import tempfile
import unittest

from validation_tools_support import ROOT, ROOT_EXTERNAL_SERVICE_CHECK


class RootExternalServicePolicyTest(unittest.TestCase):
    @staticmethod
    def run_check(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-B", str(ROOT_EXTERNAL_SERVICE_CHECK), *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def authorize(
        self,
        *,
        service: str = "github",
        access: str = "write",
        operation: str = "git.push",
        target: str = "rectaris/temp_project:refs/heads/release+candidate",
        effects: tuple[str, ...] = ("ordinary",),
        confirmed_target: str | None = None,
        confirmed_effects: tuple[str, ...] = (),
        provider_configured: bool = True,
        task_authorized: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        command = ["authorize", service, access, operation]
        if provider_configured:
            command.append("--provider-configured")
        if task_authorized:
            command.append("--task-authorized")
        command.extend(["--target", target])
        for effect in effects:
            command.extend(["--effect", effect])
        if confirmed_target is not None:
            command.extend(["--confirmed-target", confirmed_target])
        for effect in confirmed_effects:
            command.extend(["--confirmed-effect", effect])
        return self.run_check(*command)

    def assert_rejected(self, *args: str) -> None:
        result = self.run_check(*args)
        self.assertNotEqual(result.returncode, 0, msg=result.stdout + result.stderr)

    def test_root_policy_check_and_ordinary_github_reads_and_writes(self) -> None:
        self.assertEqual(self.run_check("check").returncode, 0)
        self.assertEqual(self.authorize().returncode, 0)
        self.assertEqual(
            self.authorize(
                target="rectaris/temp_project:refs/tags/release+candidate",
            ).returncode,
            0,
        )
        self.assertEqual(
            self.authorize(
                access="read",
                operation="repository.read",
                target="rectaris/temp_project",
            ).returncode,
            0,
        )

    def test_github_public_writes_require_exact_effects_and_confirmation(self) -> None:
        pull_request_target = "rectaris/temp_project:refs/heads/dev+candidate->refs/heads/main"
        release_target = "rectaris/temp_project:release:v1.2.3"
        for operation, target in (
            ("pull_request.publish", pull_request_target),
            ("release.publish", release_target),
        ):
            with self.subTest(operation=operation):
                result = self.authorize(
                    operation=operation,
                    target=target,
                    effects=("public_communication",),
                    confirmed_target=target,
                    confirmed_effects=("public_communication",),
                )
                self.assertEqual(result.returncode, 0, msg=result.stderr)

        self.assert_rejected(
            *self.authorize_command(
                operation="pull_request.publish",
                target=pull_request_target,
                effects=("ordinary",),
            )
        )
        self.assert_rejected(
            *self.authorize_command(
                operation="git.push",
                target="rectaris/temp_project:refs/heads/main",
                effects=("public_communication",),
            )
        )
        self.assert_rejected(
            *self.authorize_command(
                operation="release.publish",
                target=release_target,
                effects=("public_communication",),
            )
        )
        self.assert_rejected(
            *self.authorize_command(
                operation="release.publish",
                target=release_target,
                effects=("public_communication",),
                confirmed_target=release_target,
            )
        )
        self.assert_rejected(
            *self.authorize_command(
                operation="release.publish",
                target=release_target,
                effects=("public_communication",),
                confirmed_target="rectaris/temp_project:release:other",
                confirmed_effects=("public_communication",),
            )
        )
        for effect in (
            "remote_delete",
            "financial_commitment",
            "production_change",
            "access_control_change",
        ):
            with self.subTest(effect=effect):
                target = "rectaris/temp_project"
                result = self.authorize(
                    operation=f"operation.{effect}",
                    target=target,
                    effects=(effect,),
                    confirmed_target=target,
                    confirmed_effects=(effect,),
                )
                self.assertEqual(result.returncode, 0, msg=result.stderr)

    def authorize_command(self, **kwargs: object) -> list[str]:
        service = str(kwargs.get("service", "github"))
        access = str(kwargs.get("access", "write"))
        operation = str(kwargs.get("operation", "git.push"))
        target = str(kwargs.get("target", "rectaris/temp_project:refs/heads/release+candidate"))
        effects = tuple(kwargs.get("effects", ("ordinary",)))
        confirmed_target = kwargs.get("confirmed_target")
        confirmed_effects = tuple(kwargs.get("confirmed_effects", ()))
        provider_configured = bool(kwargs.get("provider_configured", True))
        task_authorized = bool(kwargs.get("task_authorized", True))
        command = ["authorize", service, access, operation]
        if provider_configured:
            command.append("--provider-configured")
        if task_authorized:
            command.append("--task-authorized")
        command.extend(["--target", target])
        for effect in effects:
            command.extend(["--effect", str(effect)])
        if confirmed_target is not None:
            command.extend(["--confirmed-target", str(confirmed_target)])
        for effect in confirmed_effects:
            command.extend(["--confirmed-effect", str(effect)])
        return command

    def test_denied_effects_and_missing_runtime_facts_fail_closed(self) -> None:
        self.assert_rejected(*self.authorize_command(provider_configured=False))
        self.assert_rejected(*self.authorize_command(task_authorized=False))
        for effect in (
            "credential_material_transfer",
            "secret_persistence",
            "write_credentials_to_untrusted_code",
        ):
            with self.subTest(effect=effect):
                self.assert_rejected(
                    *self.authorize_command(
                        effects=(effect,),
                        confirmed_target="rectaris/temp_project:refs/heads/release+candidate",
                        confirmed_effects=(effect,),
                    )
                )
        self.assert_rejected(
            *self.authorize_command(
                effects=("ordinary", "public_communication"),
                confirmed_target="rectaris/temp_project:refs/heads/release+candidate",
                confirmed_effects=("ordinary", "public_communication"),
            )
        )

    def test_github_targets_use_exact_repository_and_git_ref_validation(self) -> None:
        for target in (
            "rectaris/temp_project:refs/heads/release+candidate",
            "rectaris/temp_project:refs/tags/release+candidate",
        ):
            with self.subTest(target=target):
                self.assertEqual(self.authorize(target=target).returncode, 0)
        rejected = (
            "rectaris/temp_project:refs/heads/release.",
            "rectaris/temp_project:refs/tags/release.",
            "rectaris/temp_project:refs/branches/release",
            "rectaris/temp_project:refs/tags/release:extra",
        )
        for target in rejected:
            with self.subTest(target=target):
                self.assert_rejected(*self.authorize_command(target=target))

        pull_request_targets = (
            "rectaris/temp_project:refs/heads/HEAD->refs/heads/main",
            "rectaris/temp_project:refs/heads/-dev->refs/heads/main",
            "rectaris/temp_project:refs/heads/dev->refs/heads/main.",
            "rectaris/temp_project:refs/tags/v1.2.3",
        )
        for target in pull_request_targets[:3]:
            with self.subTest(target=target):
                self.assert_rejected(
                    *self.authorize_command(
                        operation="pull_request.publish",
                        target=target,
                        effects=("public_communication",),
                        confirmed_target=target,
                        confirmed_effects=("public_communication",),
                    )
                )
        self.assert_rejected(
            *self.authorize_command(
                operation="pull_request.publish",
                target=pull_request_targets[3],
                effects=("public_communication",),
                confirmed_target=pull_request_targets[3],
                confirmed_effects=("public_communication",),
            )
        )
        release_invalid_target = "rectaris/temp_project:release:v1.2.3."
        self.assert_rejected(
            *self.authorize_command(
                operation="release.publish",
                target=release_invalid_target,
                effects=("public_communication",),
                confirmed_target=release_invalid_target,
                confirmed_effects=("public_communication",),
            )
        )
        self.assert_rejected(
            *self.authorize_command(
                service="gh",
                operation="git.push",
            )
        )
        self.assert_rejected(
            *self.authorize_command(
                operation="git.push",
                target="other/repository:refs/heads/main",
            )
        )

    def test_root_rejects_empty_and_whitespace_only_operation_and_target(self) -> None:
        for operation in ("", " \t"):
            with self.subTest(operation=repr(operation)):
                self.assert_rejected(*self.authorize_command(operation=operation))
        for target in ("", " \t"):
            with self.subTest(target=repr(target)):
                self.assert_rejected(*self.authorize_command(target=target))

    def test_root_rejects_unknown_options_help_policy_overrides_and_escaped_help(self) -> None:
        base = self.authorize_command()
        negative_commands = {
            "unknown authorize option": [*base, "--unknown"],
            "exact --policy": [*base, "--policy", "other-policy.yaml"],
            "--policy abbreviation": [*base, "--pol", "other-policy.yaml"],
            "authorize --help": ["authorize", "--help"],
            "authorize -h": ["authorize", "-h"],
            "option-like service": ["authorize", "--", "--help", "write", "git.push"],
            "escaped positional --help": ["authorize", "github", "write", "--", "--help"],
            "escaped positional -h": ["authorize", "github", "write", "--", "-h"],
        }
        for label, command in negative_commands.items():
            with self.subTest(label=label):
                self.assert_rejected(*command)
        for prefix_length in range(1, len("--policy")):
            with self.subTest(prefix=prefix_length):
                self.assert_rejected(*base, "--policy"[:prefix_length], "other-policy.yaml")



if __name__ == "__main__":
    unittest.main()
