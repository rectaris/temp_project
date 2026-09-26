"""External-service policy tests."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from .support import ROOT, ROOT_EXTERNAL_SERVICE_CHECK, load_module


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



    def test_opencode_go_inference_reads_require_exact_runtime_facts_and_ordinary_effect(self) -> None:
        policy_text = (ROOT / "docs/agent/external-services.yaml").read_text(encoding="utf-8")
        self.assertIn("  opencode_go:", policy_text)
        for model in ("glm-5.3", "qwen3-coder"):
            target = f"https://opencode.ai/zen/go/v1/chat/completions#model={model}"
            with self.subTest(model=model):
                self.assertEqual(
                    self.authorize(
                        service="opencode_go",
                        access="read",
                        operation="inference.chat_completions",
                        target=target,
                    ).returncode,
                    0,
                )
        target = "https://opencode.ai/zen/go/v1/chat/completions#model=glm-5.3"

        def inference(**overrides: object) -> subprocess.CompletedProcess[str]:
            arguments: dict[str, object] = {
                "service": "opencode_go",
                "access": "read",
                "operation": "inference.chat_completions",
                "target": target,
            }
            arguments.update(overrides)
            return self.authorize(**arguments)

        rejected = {
            "provider not configured": {"provider_configured": False},
            "task does not require the call": {"task_authorized": False},
            "missing target": {"target": ""},
            "credential material transfer": {"effects": ("credential_material_transfer",)},
            "secret persistence": {"effects": ("secret_persistence",)},
            "write credentials to untrusted code": {
                "effects": ("write_credentials_to_untrusted_code",)
            },
            "read with a non-ordinary effect": {"effects": ("public_communication",)},
            "read with a combined effect": {"effects": ("ordinary", "public_communication")},
        }
        for label, overrides in rejected.items():
            with self.subTest(label=label):
                result = inference(**overrides)
                self.assertNotEqual(
                    result.returncode, 0, msg=result.stdout + result.stderr
                )

    def test_opencode_go_is_seeded_disabled_in_a_version_1_policy(self) -> None:
        maintained_check = ROOT / "template/.project-agent-workflow/scripts/check-external-service-policy.py"
        policy_text = """version: 1

states:
  disabled: Policy exists, but service reads and writes are not authorized.

external_services:
  opencode_go:
    state: disabled
    connection: ""
    authentication: none
    credential_reference: ""
    allowed_reads: []
    allowed_writes: []
    write_authorization_rule: ""
    dry_run_or_local_validation: ""
    unavailable_fallback: "Answer from local repository files."
"""
        with tempfile.TemporaryDirectory() as directory:
            policy = Path(directory) / "external-services.yaml"
            policy.write_text(policy_text, encoding="utf-8")
            base = [
                sys.executable,
                "-B",
                str(maintained_check),
                "--policy",
                str(policy),
            ]
            check = subprocess.run(
                [*base, "check"],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(check.returncode, 0, msg=check.stdout + check.stderr)
            denied = subprocess.run(
                [*base, "authorize", "opencode_go", "read", "inference.chat_completions"],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(denied.returncode, 0)
            self.assertIn("does not authorize reads", denied.stderr)

    TYPESAFE_TARGET = "https://api.typesafe.ai/v1/systemone#model=jev-1.13.0"
    TYPESAFE_KEY_SENTINEL = "typesafe-test-key-3f9c1e0b"
    TARGET_SECRET_SENTINEL = "target-secret-5d2a7c4e"

    def run_typesafe(self, **overrides: object) -> subprocess.CompletedProcess[str]:
        arguments: dict[str, object] = {
            "service": "typesafe",
            "access": "read",
            "operation": "decision.evaluate",
            "target": self.TYPESAFE_TARGET,
        }
        arguments.update(overrides)
        environment = dict(os.environ)
        environment["TYPESAFE_API_KEY"] = self.TYPESAFE_KEY_SENTINEL
        return subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT_EXTERNAL_SERVICE_CHECK),
                *self.authorize_command(**arguments),
            ],
            cwd=ROOT,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def assert_typesafe_refused_before_delegation(
        self, result: subprocess.CompletedProcess[str]
    ) -> None:
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, msg=output)
        self.assertTrue(
            result.stderr.startswith("root external-service policy error: "), msg=output
        )
        self.assertNotIn("check passed", output)
        for exposed in (
            self.TYPESAFE_KEY_SENTINEL,
            self.TARGET_SECRET_SENTINEL,
            "TYPESAFE_API_KEY",
        ):
            self.assertNotIn(exposed, output)

    def test_typesafe_decision_reads_admit_only_pinned_model_targets(self) -> None:
        policy_text = (ROOT / "docs/agent/external-services.yaml").read_text(encoding="utf-8")
        self.assertIn("  typesafe:", policy_text)
        for model in ("jev-1.13.0", "jev-0.0.0", "jev-10.20.300", "jev-12345678901.0.0"):
            with self.subTest(model=model):
                result = self.run_typesafe(
                    target=f"https://api.typesafe.ai/v1/systemone#model={model}"
                )
                self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
                self.assertIn("external-service policy check passed", result.stdout)

        endpoint = "https://api.typesafe.ai/v1/systemone"
        secret = self.TARGET_SECRET_SENTINEL
        refused_targets = (
            endpoint,
            f"{endpoint}#model=jev-latest",
            f"{endpoint}#model=jev-preview",
            f"{endpoint}#model=jev-1.13",
            f"{endpoint}#model=jev-1",
            f"{endpoint}#model=jev-01.13.0",
            f"{endpoint}#model=jev-1.13.0-rc1",
            f"{endpoint}#model=jev-1.13.0\n",
            f"{endpoint}#model=jev-\uff11.13.0",
            f"{endpoint}#model=typesafe/jev-1.13",
            f"{endpoint}#model=jev-1.13.0&model=jev-latest",
            f"{endpoint}?base_url={secret}#model=jev-1.13.0",
            f"{endpoint}/#model=jev-1.13.0",
            "http://api.typesafe.ai/v1/systemone#model=jev-1.13.0",
            "https://API.typesafe.ai/v1/systemone#model=jev-1.13.0",
            "https://api.typesafe.ai:443/v1/systemone#model=jev-1.13.0",
            f"https://{secret}@api.typesafe.ai/v1/systemone#model=jev-1.13.0",
            "https://api.typesafe.ai/v2/systemone#model=jev-1.13.0",
            "https://api.typesafe.ai/v1/models#model=jev-1.13.0",
            "https://staging.typesafe.ai/v1/systemone#model=jev-1.13.0",
            "https://api.typesafe.ai.example.com/v1/systemone#model=jev-1.13.0",
            "https://openrouter.ai/api/v1/systemone#model=jev-1.13.0",
        )
        for target in refused_targets:
            with self.subTest(target=target):
                self.assert_typesafe_refused_before_delegation(self.run_typesafe(target=target))

    def test_typesafe_refuses_every_other_access_operation_effect_and_missing_fact(self) -> None:
        refused = {
            "write access": {"access": "write"},
            "public communication effect": {"effects": ("public_communication",)},
            "combined effect": {"effects": ("ordinary", "public_communication")},
            "credential material transfer": {"effects": ("credential_material_transfer",)},
            "secret persistence": {"effects": ("secret_persistence",)},
            "write credentials to untrusted code": {
                "effects": ("write_credentials_to_untrusted_code",)
            },
            "unclassified write effect": {"access": "write", "effects": ("remote_write",)},
            "other operation": {"operation": "inference.chat_completions"},
            "model listing": {"operation": "models.list"},
            "operation carrying a secret": {"operation": f"decision.{self.TARGET_SECRET_SENTINEL}"},
            "provider not configured": {"provider_configured": False},
            "task does not require the call": {"task_authorized": False},
            "both runtime facts missing": {
                "provider_configured": False,
                "task_authorized": False,
            },
            "confirmation supplied": {
                "confirmed_target": self.TYPESAFE_TARGET,
                "confirmed_effects": ("ordinary",),
            },
            "decision operation under another provider": {"service": "github"},
            "typesafe target under another provider": {
                "service": "opencode_go",
                "operation": "inference.chat_completions",
            },
            "invalid access carrying a secret": {"access": self.TARGET_SECRET_SENTINEL},
        }
        for label, overrides in refused.items():
            with self.subTest(label=label):
                self.assert_typesafe_refused_before_delegation(self.run_typesafe(**overrides))

    def test_typesafe_routing_folds_spellings_that_name_the_same_provider(self) -> None:
        for service in (
            " typesafe",
            "typesafe\n",
            "TypeSafe",
            "\uff54ypesafe",
            "type\u00adsafe",
            "type\u0903safe",
        ):
            with self.subTest(service=service):
                self.assert_typesafe_refused_before_delegation(
                    self.run_typesafe(service=service)
                )
        for operation in (
            "decision.evaluate ",
            "\tdecision.evaluate",
            "Decision.Evaluate",
            "\uff44ecision.evaluate",
            "decision%2Eevaluate",
            "decision.\u200bevaluate",
        ):
            with self.subTest(operation=operation):
                self.assert_typesafe_refused_before_delegation(
                    self.run_typesafe(
                        service="github", operation=operation, target="https://example.invalid"
                    )
                )
        for target in (
            "https://API.TypeSafe.AI/v1/systemone#model=jev-latest",
            "HTTPS://API.TYPESAFE.AI/v1/systemone#model=jev-latest",
            "https:api.typesafe.ai/v1/systemone#model=jev-latest",
            "https:/\\api.typesafe.ai/v1/systemone#model=jev-latest",
            "https:\\\\api.typesafe.ai/v1/systemone#model=jev-latest",
            "wss://api.typesafe.ai/v1/systemone",
            "//api.typesafe.ai/v1/systemone#model=jev-latest",
            "api.typesafe.ai/v1/systemone#model=jev-latest",
            "api.typesafe.ai:443/v1/systemone#model=jev-latest",
            "https://typesafe.ai/",
            "https://evil.example@api.typesafe.ai/v1/systemone",
            "https://api.typesafe.ai#@evil.example",
            "gopher://api.typesafe.ai/",
            "///api.typesafe.ai/v1/systemone",
            "\\\\api.typesafe.ai/v1/systemone",
            "/\\api.typesafe.ai/v1/systemone",
            "file://api.typesafe.ai/share",
            f"x:{self.TARGET_SECRET_SENTINEL}@api.typesafe.ai/v1/systemone",
            "mailto:someone@api.typesafe.ai",
            "api.typesafe.ai:/v1/systemone",
            "api.typesafe.ai:",
            "foo.bar://api.typesafe.ai/v1",
            "gopher:/api.typesafe.ai/x",
            "gopher:///api.typesafe.ai/x",
            "dict:\\api.typesafe.ai",
            "sftp:/api.typesafe.ai",
            "ldap:///api.typesafe.ai",
            "foo://api.typesafe.ai/x",
            "api.typesafe.ai:/v1",
        ):
            with self.subTest(target=target):
                self.assert_typesafe_refused_before_delegation(
                    self.run_typesafe(
                        service="opencode_go",
                        operation="inference.chat_completions",
                        target=target,
                    )
                )

    def test_every_service_refuses_a_noncanonical_target_authority(self) -> None:
        for target in (
            "https://api.typesafe.ai./v1/systemone#model=jev-latest",
            "https://api\u3002typesafe\u3002ai/v1/systemone#model=jev-latest",
            "https://api\uff0etypesafe\uff0eai/v1/systemone#model=jev-latest",
            "https://\uff21\uff30\uff29.\uff34\uff39\uff30\uff25\uff33\uff21\uff26\uff25.ai/v1",
            "https://api%2Etypesafe%2Eai/v1/systemone#model=jev-latest",
            "https://api.type\u00adsafe.ai/v1/systemone#model=jev-latest",
            "https://api.type\u1806safe.ai/v1/systemone#model=jev-latest",
            "https://api.typesafe\udcff.ai/v1/systemone#model=jev-latest",
            "https://evil.example\\@api.typesafe.ai/v1/systemone",
            "https://api.typesafe.ai\\@evil.example/v1",
            "https://a@b@api.typesafe.ai/v1",
            "https://under_score.example/v1",
            "https://exa mple.example/v1",
            "https://example.example:port/v1",
            "api.type\u00adsafe.ai/v1/systemone#model=jev-latest",
            "ht\ttps://api.typesafe.ai/v1",
            "https://api.type\nsafe.ai/v1",
            "https://example.example/v1\r",
            " https://example.example/v1",
            "https://example.example/v1\x1f",
            "file:\\\\api.typesafe.ai\\share",
            "file:/\\api.typesafe.ai\\share",
            "https://u%40x@example.example/v1",
            "https://@/v1",
            "https://[:::]/v1",
            "https://[fe80::1%25eth0]/v1",
            "//@/v1",
            "api.typesafe.ai.:443/v1",
            "x:y@api.type\u00adsafe.ai/v1",
            "user@api.typesafe%2Eai/v1",
            "api\u3002typesafe\u3002ai/v1",
            "api\uff0etypesafe\uff0eai",
            "api%2Etypesafe%2Eai/v1",
        ):
            with self.subTest(target=target):
                self.assert_typesafe_refused_before_delegation(
                    self.run_typesafe(
                        service="opencode_go",
                        operation="inference.chat_completions",
                        target=target,
                    )
                )

    def test_canonical_and_non_url_targets_of_other_services_keep_their_results(self) -> None:
        cases: tuple[dict[str, object], ...] = (
            {"target": "rectaris/temp_project:refs/heads/typesafe.ai"},
            {"target": "rectaris/temp_project:refs/heads/x%2F%2Ftypesafe.ai"},
            {"target": "rectaris/temp_project:refs/tags/typesafe.ai-v1"},
            {
                "operation": "pull_request.publish",
                "target": "rectaris/temp_project:refs/heads/typesafe.ai->refs/heads/main",
                "effects": ("public_communication",),
                "confirmed_target": "rectaris/temp_project:refs/heads/typesafe.ai->refs/heads/main",
                "confirmed_effects": ("public_communication",),
            },
            {"access": "read", "operation": "repository.read", "target": "rectaris/temp_project"},
            {
                "service": "opencode_go",
                "access": "read",
                "operation": "inference.chat_completions",
                "target": "https://opencode.ai/zen/go/v1/chat/completions#model=glm-5.3",
            },
            {
                "service": "opencode_go",
                "access": "read",
                "operation": "inference.chat_completions",
                "target": "https://opencode.ai/zen/go/v1/chat/completions#model=typesafe.ai/jev",
            },
            {
                "service": "linear",
                "access": "read",
                "operation": "issue.read",
                "target": "https://api.linear.example/graphql?q=%E3%81%82#typesafe.ai",
            },
            {
                "service": "linear",
                "access": "read",
                "operation": "issue.read",
                "target": "https://user:pass@api.linear.example:8443/x",
            },
            {"service": "linear", "access": "read", "operation": "issue.read", "target": "https://[2001:db8::1]/x"},
            {"service": "linear", "access": "read", "operation": "issue.read", "target": "urn:isbn:0451450523"},
            {"service": "linear", "access": "read", "operation": "issue.read", "target": "Team ABC / 課題"},
            {"service": "linear", "access": "read", "operation": "issue.read", "target": "file:///tmp/typesafe.ai"},
            {"service": "linear", "access": "read", "operation": "issue.read", "target": "file:typesafe.ai"},
            {"service": "linear", "access": "read", "operation": "issue.read", "target": "https://[::1]:8443/x"},
            {"service": "linear", "access": "read", "operation": "issue.read", "target": "//cdn.example/x"},
            {"service": "linear", "access": "read", "operation": "issue.read", "target": "git:///tmp/repo"},
            {"service": "linear", "access": "read", "operation": "issue.read", "target": "git:///typesafe.ai"},
            {"service": "linear", "access": "read", "operation": "issue.read", "target": "foo:/a_b"},
            {"service": "linear", "access": "read", "operation": "issue.read", "target": "foo:/api.typesafe.ai"},
            {"service": "linear", "access": "read", "operation": "issue.read", "target": "C:/Users/typesafe.ai"},
            {"service": "linear", "access": "read", "operation": "issue.read", "target": "/tmp/typesafe.ai"},
            {"service": "linear", "access": "read", "operation": "issue.read", "target": "foo.bar://example.com/x"},
            {"service": "linear", "access": "read", "operation": "issue.read", "target": "vnd.example:opaque"},
            {"service": "linear", "access": "read", "operation": "issue.read", "target": "tag:example.com,2005:x"},
            {"service": "linear", "access": "read", "operation": "issue.read", "target": "mailto:user@example.com"},
            {"service": "linear", "access": "read", "operation": "issue.read", "target": "api.linear.example:443/v1"},
            {"service": "linear", "access": "read", "operation": "issue.read", "target": "\u65e5\u672c\u8a9e"},
        )
        for arguments in cases:
            with self.subTest(**{key: str(value) for key, value in arguments.items()}):
                result = self.authorize(**arguments)
                self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

    def test_every_non_ascii_host_character_is_refused(self) -> None:
        module = load_module(ROOT_EXTERNAL_SERVICE_CHECK, "root_external_service_check_hosts")
        admitted: list[str] = []
        for code_point in range(0x80, 0x110000):
            target = f"https://api.type{chr(code_point)}safe.ai/v1/systemone"
            try:
                module.names_typesafe_host(target)
            except module.RootPolicyError:
                continue
            admitted.append(f"U+{code_point:04X}")
        self.assertEqual(admitted, [])

    def test_repeated_single_value_options_are_refused(self) -> None:
        benign = "https://example.example/v1"
        base = ["authorize", "opencode_go", "read", "inference.chat_completions"]
        flags = ["--provider-configured", "--task-authorized", "--effect", "ordinary"]
        for repeated in (
            ["--target", self.TYPESAFE_TARGET, "--target", benign],
            ["--target", benign, "--target", self.TYPESAFE_TARGET],
            ["--target", benign, "--confirmed-target", benign, "--confirmed-target", benign],
            ["--target", benign, "--authorization-rule", "a", "--authorization-rule", "b"],
        ):
            with self.subTest(repeated=repeated):
                result = self.run_check(*base, *flags, *repeated)
                self.assertEqual(result.returncode, 2, msg=result.stdout + result.stderr)
                self.assertEqual(result.stderr, "root external-service policy error: invalid arguments\n")
                self.assertNotIn("check passed", result.stdout)

    def test_maintained_checker_runs_without_typesafe_environment_variables(self) -> None:
        module = load_module(ROOT_EXTERNAL_SERVICE_CHECK, "root_external_service_check_environment")
        captured: dict[str, object] = {}

        def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            captured.update(kwargs)
            return subprocess.CompletedProcess(command, 0)

        environment = {
            "TYPESAFE_API_KEY": self.TYPESAFE_KEY_SENTINEL,
            "TYPESAFE_BASE_URL": "https://example.example",
            "typesafe_api_key": self.TYPESAFE_KEY_SENTINEL,
            "EXTERNAL_SERVICE_TEST_KEEP": "kept",
        }
        with mock.patch.dict(os.environ, environment), mock.patch.object(
            module.subprocess, "run", side_effect=fake_run
        ):
            self.assertEqual(module.delegate(["check"]), 0)
        child = captured["env"]
        assert isinstance(child, dict)
        self.assertEqual(
            [name for name in child if name.upper().startswith("TYPESAFE_")], []
        )
        self.assertNotIn(self.TYPESAFE_KEY_SENTINEL, child.values())
        self.assertEqual(child["EXTERNAL_SERVICE_TEST_KEEP"], "kept")


if __name__ == "__main__":
    unittest.main()
