#!/usr/bin/env python3
"""Behavior tests for the bounded OpenCode Go inference transport.

The transport exists to keep one credential on the parent side of a sandbox
boundary while still letting a delegated process ask one admitted model for one
answer. These tests therefore check two different things: that the ordinary
path works, and that each way of widening the boundary fails before any
upstream request is made.

The real Bubblewrap case is required rather than optional. A skipped isolation
check reports success without having proved isolation, which is the one
conclusion these tests exist to prevent.
"""

from __future__ import annotations

import contextlib
import http.client
import importlib.util
import json
import os
import pickle
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/project_workflow/opencode_go_transport.py"
TEMPLATE_MODULE_PATH = ROOT / "template/.project-agent-workflow/scripts/opencode_go_transport.py"

# The sandbox probe searches its own readable files, so the value it looks for
# must never appear contiguously in any source it can read. It is stored in two
# halves and joined at use.
SENTINEL_HEAD = "sk-opencode-go-probe-"
SENTINEL_TAIL = "8f3b1d0a5c7e2946"
SENTINEL = SENTINEL_HEAD + SENTINEL_TAIL

SANDBOX_SYSTEM_DIRECTORIES = ("/usr", "/bin", "/sbin", "/lib", "/lib64")
SANDBOX_SYSTEM_OPTIONAL_DIRECTORIES = ("/etc/ssl", "/etc/alternatives")
SANDBOX_SYSTEM_FILES = (
    "/etc/passwd",
    "/etc/group",
    "/etc/nsswitch.conf",
    "/etc/hosts",
    "/etc/resolv.conf",
)


def load_transport_module():
    """Load the module by path so either repository layout works."""

    name = "opencode_go_transport_under_test"
    spec = importlib.util.spec_from_file_location(name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    # Dataclass construction resolves annotations through sys.modules, so the
    # module has to be registered before it is executed.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


TRANSPORT = load_transport_module()


class _FakeUpstreamHandler(BaseHTTPRequestHandler):
    """Answer exactly what the current test asked the upstream to answer."""

    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def do_POST(self) -> None:
        server = self.server
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b""
        server.record(  # type: ignore[attr-defined]
            {
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
                "user_agent": self.headers.get("User-Agent"),
                "session": self.headers.get(TRANSPORT.SESSION_HEADER),
                "accept": self.headers.get("Accept"),
                "content_type": self.headers.get("Content-Type"),
                "header_names": sorted(name.lower() for name in self.headers.keys()),
                "body": body,
            }
        )
        spec = server.next_response()  # type: ignore[attr-defined]
        kind = spec.get("kind", "ok")
        if kind == "redirect":
            self.send_response(spec.get("status", 302))
            self.send_header("Location", spec.get("location", "https://elsewhere.invalid/"))
            self.send_header("Content-Length", "0")
            self.end_headers()
            self.close_connection = True
            return
        if kind == "status":
            payload = spec.get("body", b"upstream refused")
            self.send_response(spec["status"])
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            self.close_connection = True
            return
        if kind == "truncated":
            payload = spec.get("body", b"data: partial")
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(payload) + 64))
            self.end_headers()
            self.wfile.write(payload)
            self.wfile.flush()
            self.close_connection = True
            return
        if kind == "slow":
            payload = spec.get("body", b"data: slow\n\n")
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            deadline = time.monotonic() + float(spec.get("seconds", 3.0))
            try:
                while time.monotonic() < deadline:
                    self.wfile.write(f"{len(payload):x}\r\n".encode("ascii"))
                    self.wfile.write(payload)
                    self.wfile.write(b"\r\n")
                    self.wfile.flush()
                    time.sleep(0.05)
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
            except OSError:
                pass
            self.close_connection = True
            return
        payload = spec.get("body", json.dumps({"ok": True}).encode("utf-8"))
        self.send_response(200)
        self.send_header("Content-Type", spec.get("content_type", "application/json"))
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
        self.close_connection = True


class _FakeUpstreamServer(HTTPServer):
    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _FakeUpstreamHandler)
        self._lock = threading.Lock()
        self.requests: list[dict[str, Any]] = []
        self._script: list[dict[str, Any]] = []
        self._default: dict[str, Any] = {"kind": "ok"}

    def record(self, entry: dict[str, Any]) -> None:
        with self._lock:
            self.requests.append(entry)

    def next_response(self) -> dict[str, Any]:
        with self._lock:
            if self._script:
                return self._script.pop(0)
            return dict(self._default)

    def script(self, *responses: dict[str, Any]) -> None:
        with self._lock:
            self._script = [dict(response) for response in responses]

    def set_default(self, response: dict[str, Any]) -> None:
        with self._lock:
            self._default = dict(response)

    @property
    def count(self) -> int:
        with self._lock:
            return len(self.requests)


class TransportTestCase(unittest.TestCase):
    """Shared fixture: one fake upstream and one owner-only socket directory."""

    model = "glm-5.3"

    def setUp(self) -> None:
        self.upstream = _FakeUpstreamServer()
        self.upstream_thread = threading.Thread(
            target=self.upstream.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        )
        self.upstream_thread.start()
        self.addCleanup(self._stop_upstream)
        self.workspace = Path(tempfile.mkdtemp(prefix="opencode-go-transport-"))
        self.addCleanup(shutil.rmtree, self.workspace, True)
        os.chmod(self.workspace, 0o700)
        self.socket_path = self.workspace / "relay.sock"
        self.environment_name = "OPENCODE_GO_TRANSPORT_TEST_KEY"
        os.environ[self.environment_name] = SENTINEL
        self.addCleanup(os.environ.pop, self.environment_name, None)
        self.authorizations: list[dict[str, Any]] = []

    def _stop_upstream(self) -> None:
        self.upstream.shutdown()
        self.upstream.server_close()
        self.upstream_thread.join(timeout=10)

    def credential_source(self):
        return TRANSPORT.CredentialSource(
            TRANSPORT.CREDENTIAL_SOURCE_ENVIRONMENT, self.environment_name
        )

    def target(self):
        return TRANSPORT.UpstreamTarget(
            host="127.0.0.1",
            port=self.upstream.server_address[1],
            path=TRANSPORT.UPSTREAM_PATH,
            tls=False,
        )

    def allow_all(self, request) -> bool:
        self.authorizations.append(request.to_dict())
        return True

    def start(self, *, authorize=None, limits=None, socket_path=None, **kwargs):
        transport = TRANSPORT.create_transport(
            socket_path=socket_path if socket_path is not None else self.socket_path,
            model=self.model,
            credential_source=self.credential_source(),
            authorize=authorize if authorize is not None else self.allow_all,
            limits=limits,
            target=self.target(),
            **kwargs,
        )
        self.addCleanup(transport.close)
        return transport

    def post(
        self,
        payload: Any = None,
        *,
        headers: dict[str, str] | None = None,
        path: str | None = None,
        method: str = "POST",
        raw_body: bytes | None = None,
        declared_length: int | None = None,
        socket_path: Path | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        """Speak HTTP over the relay socket the way the inner bridge does."""

        if raw_body is None:
            if payload is None:
                payload = {"model": self.model, "messages": [{"role": "user", "content": "hi"}]}
            raw_body = json.dumps(payload).encode("utf-8")
        request_path = TRANSPORT.BRIDGE_REQUEST_PATH if path is None else path
        sent_headers = {
            "Host": "opencode-go-relay",
            "Content-Type": "application/json",
            "Connection": "close",
        }
        if headers:
            sent_headers.update(headers)
        if declared_length is not None:
            sent_headers["Content-Length"] = str(declared_length)
        elif "Content-Length" not in sent_headers and "Transfer-Encoding" not in sent_headers:
            sent_headers["Content-Length"] = str(len(raw_body))
        head = f"{method} {request_path} HTTP/1.1\r\n" + "".join(
            f"{name}: {value}\r\n" for name, value in sent_headers.items()
        )
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(30)
        connection.connect(str(socket_path or self.socket_path))
        try:
            connection.sendall(head.encode("latin-1") + b"\r\n" + raw_body)
            buffer = b""
            while True:
                chunk = connection.recv(65536)
                if not chunk:
                    break
                buffer += chunk
        finally:
            connection.close()
        head_bytes, _, body = buffer.partition(b"\r\n\r\n")
        lines = head_bytes.decode("latin-1").split("\r\n")
        status = int(lines[0].split(" ")[1])
        response_headers = {}
        for line in lines[1:]:
            name, _, value = line.partition(":")
            response_headers[name.strip().lower()] = value.strip()
        return status, response_headers, body

    def error_code(self, body: bytes) -> str:
        return json.loads(body.decode("utf-8"))["error"]["code"]

    def raw_exchange(self, request: bytes) -> bytes:
        """Send exact request bytes so ambiguous framing can be constructed."""

        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(30)
        connection.connect(str(self.socket_path))
        try:
            connection.sendall(request)
            buffer = b""
            while True:
                chunk = connection.recv(65536)
                if not chunk:
                    break
                buffer += chunk
            return buffer
        finally:
            connection.close()


class OrdinaryInferencePathTests(TransportTestCase):
    def test_one_admitted_request_reaches_the_fixed_upstream_with_the_parent_credential(
        self,
    ) -> None:
        self.upstream.set_default(
            {"kind": "ok", "body": b'data: {"type":"text"}\n\n', "content_type": "text/event-stream"}
        )
        with self.start() as transport:
            status, headers, body = self.post(headers={"Accept": "text/event-stream"})
            result_before_close = transport.result()
        self.assertEqual(status, 200)
        self.assertEqual(body, b'data: {"type":"text"}\n\n')
        self.assertEqual(headers["content-type"], "text/event-stream")
        self.assertEqual(self.upstream.count, 1)
        seen = self.upstream.requests[0]
        self.assertEqual(seen["path"], TRANSPORT.UPSTREAM_PATH)
        self.assertEqual(seen["authorization"], f"Bearer {SENTINEL}")
        self.assertEqual(seen["user_agent"], TRANSPORT.FORWARDED_USER_AGENT)
        self.assertEqual(seen["session"], transport.session_id)
        self.assertEqual(result_before_close.status, TRANSPORT.STATUS_OK)

    def test_the_auxiliary_second_request_is_forwarded_for_the_same_model(self) -> None:
        with self.start() as transport:
            first = self.post()
            second = self.post(
                {"model": self.model, "messages": [{"role": "user", "content": "title"}]}
            )
            result = transport.result()
        self.assertEqual(first[0], 200)
        self.assertEqual(second[0], 200)
        self.assertEqual(self.upstream.count, 2)
        self.assertEqual(result.upstream_request_count, 2)
        self.assertEqual(result.status, TRANSPORT.STATUS_OK)
        self.assertEqual([entry["model"] for entry in self.authorizations], [self.model] * 2)

    def test_a_chunked_upstream_answer_is_relayed_without_a_declared_length(self) -> None:
        self.upstream.set_default({"kind": "slow", "seconds": 0.2})
        with self.start() as transport:
            status, headers, body = self.post()
            result = transport.result()
        self.assertEqual(status, 200)
        self.assertIn(b"data: slow", body)
        self.assertEqual(headers.get("transfer-encoding"), "chunked")
        self.assertEqual(result.status, TRANSPORT.STATUS_OK)

    def test_the_child_configuration_carries_a_placeholder_key_and_a_loopback_url(self) -> None:
        with self.start() as transport:
            configuration = transport.child_configuration(bridge_port=41999)
            endpoint = transport.endpoint()
        self.assertEqual(configuration["apiKey"], TRANSPORT.PLACEHOLDER_API_KEY)
        self.assertEqual(configuration["baseURL"], "http://127.0.0.1:41999/v1")
        self.assertEqual(configuration["model"], self.model)
        self.assertNotIn(SENTINEL, json.dumps(configuration))
        self.assertNotIn(SENTINEL, json.dumps(endpoint))
        self.assertEqual(endpoint["socket_path"], str(self.socket_path))


class RequestAdmissionTests(TransportTestCase):
    def test_only_post_to_the_exact_relay_path_is_accepted(self) -> None:
        with self.start():
            for method in ("GET", "PUT", "DELETE", "PATCH", "OPTIONS", "CONNECT"):
                with self.subTest(method=method):
                    status, _, body = self.post(method=method)
                    self.assertEqual(status, 405)
                    self.assertEqual(
                        self.error_code(body), TRANSPORT.STATUS_REQUEST_REJECTED
                    )
            for path in ("/v1/completions", "/", "/v1/chat/completions/extra", "/zen/go/v1/chat/completions"):
                with self.subTest(path=path):
                    status, _, body = self.post(path=path)
                    self.assertEqual(status, 400)
                    self.assertEqual(
                        self.error_code(body), TRANSPORT.STATUS_REQUEST_REJECTED
                    )
        self.assertEqual(self.upstream.count, 0)

    def test_downstream_authentication_is_stripped_and_never_forwarded(self) -> None:
        with self.start():
            status, _, _ = self.post(
                headers={
                    "Authorization": f"Bearer {TRANSPORT.PLACEHOLDER_API_KEY}",
                    "X-Api-Key": "child-supplied",
                    "Cookie": "session=child",
                }
            )
        self.assertEqual(status, 200)
        self.assertEqual(self.upstream.count, 1)
        seen = self.upstream.requests[0]
        self.assertEqual(seen["authorization"], f"Bearer {SENTINEL}")
        self.assertNotIn("x-api-key", seen["header_names"])
        self.assertNotIn("cookie", seen["header_names"])

    def test_routing_headers_are_refused_before_any_upstream_request(self) -> None:
        with self.start():
            for header in ("Forwarded", "X-Forwarded-Host", "X-Forwarded-For", "Proxy-Connection"):
                with self.subTest(header=header):
                    status, _, body = self.post(headers={header: "elsewhere.invalid"})
                    self.assertEqual(status, 400)
                    self.assertEqual(
                        self.error_code(body), TRANSPORT.STATUS_REQUEST_REJECTED
                    )
        self.assertEqual(self.upstream.count, 0)

    def test_a_child_cannot_choose_its_own_session_identity(self) -> None:
        with self.start() as transport:
            forged = self.post(headers={TRANSPORT.SESSION_HEADER: "child-chosen"})
            echoed = self.post(headers={TRANSPORT.SESSION_HEADER: transport.session_id})
        self.assertEqual(forged[0], 400)
        self.assertEqual(self.error_code(forged[2]), TRANSPORT.STATUS_REQUEST_REJECTED)
        self.assertEqual(echoed[0], 200)
        self.assertEqual(self.upstream.count, 1)
        self.assertEqual(self.upstream.requests[0]["session"], transport.session_id)

    def test_destination_and_authorization_fields_are_refused_without_contacting_upstream(
        self,
    ) -> None:
        with self.start():
            for field in ("base_url", "baseURL", "api_key", "provider", "url", "headers", "extra_body"):
                with self.subTest(field=field):
                    status, _, body = self.post(
                        {"model": self.model, "messages": [], field: "https://elsewhere.invalid"}
                    )
                    self.assertEqual(status, 400)
                    self.assertEqual(
                        self.error_code(body), TRANSPORT.STATUS_REQUEST_REJECTED
                    )
        self.assertEqual(self.upstream.count, 0)

    def test_an_unexpected_model_is_a_terminal_error_with_no_upstream_request(self) -> None:
        with self.start() as transport:
            status, _, body = self.post({"model": "some-other-model", "messages": []})
            after = self.post()
            result = transport.result()
        self.assertEqual(status, 400)
        self.assertEqual(self.error_code(body), TRANSPORT.STATUS_MODEL_REJECTED)
        self.assertEqual(after[0], 503)
        self.assertEqual(self.upstream.count, 0)
        self.assertEqual(result.status, TRANSPORT.STATUS_MODEL_REJECTED)
        self.assertEqual(result.upstream_request_count, 0)

    def test_malformed_bodies_and_content_types_are_refused(self) -> None:
        with self.start():
            cases = (
                ("not json", {"raw_body": b"{not json"}, TRANSPORT.STATUS_MALFORMED_REQUEST),
                ("json array", {"raw_body": b"[1, 2]"}, TRANSPORT.STATUS_MALFORMED_REQUEST),
                ("empty body", {"raw_body": b""}, TRANSPORT.STATUS_MALFORMED_REQUEST),
                (
                    "chunked request",
                    {"raw_body": b"{}", "headers": {"Transfer-Encoding": "chunked"}},
                    TRANSPORT.STATUS_MALFORMED_REQUEST,
                ),
                (
                    "wrong content type",
                    {"headers": {"Content-Type": "text/plain"}},
                    TRANSPORT.STATUS_REQUEST_REJECTED,
                ),
                (
                    "wrong accept",
                    {"headers": {"Accept": "text/html"}},
                    TRANSPORT.STATUS_REQUEST_REJECTED,
                ),
            )
            for label, kwargs, expected in cases:
                with self.subTest(case=label):
                    status, _, body = self.post(**kwargs)
                    self.assertEqual(status, 400)
                    self.assertEqual(self.error_code(body), expected)
        self.assertEqual(self.upstream.count, 0)

    def test_a_body_that_never_finishes_arriving_is_refused_within_its_read_window(self) -> None:
        limits = TRANSPORT.TransportLimits(wall_deadline_seconds=2.0)
        with self.start(limits=limits):
            status, _, body = self.post(
                raw_body=b'{"model":"glm-5.3"}', declared_length=4096
            )
        self.assertEqual(status, 400)
        self.assertEqual(self.error_code(body), TRANSPORT.STATUS_MALFORMED_REQUEST)
        self.assertEqual(self.upstream.count, 0)

    def test_a_duplicated_model_key_is_refused_before_any_upstream_request(self) -> None:
        # json.loads keeps the last duplicate while the body is forwarded
        # verbatim, so accepting it would authorize one model and send another.
        body = b'{"model":"some-other-model","model":"glm-5.3","messages":[]}'
        with self.start() as transport:
            status, _, response = self.post(raw_body=body)
            result = transport.result()
        self.assertEqual(status, 400)
        self.assertEqual(self.error_code(response), TRANSPORT.STATUS_MALFORMED_REQUEST)
        self.assertEqual(self.upstream.count, 0)
        self.assertEqual(result.upstream_request_count, 0)
        self.assertEqual(self.authorizations, [])

    def test_ambiguous_http_framing_never_reaches_the_upstream(self) -> None:
        payload = b'{"model":"glm-5.3","messages":[]}'
        cases = {
            "line-feed only request framing": (
                b"POST /v1/chat/completions HTTP/1.1\n"
                b"Host: relay\nContent-Type: application/json\n"
                b"Content-Length: " + str(len(payload)).encode() + b"\n\n" + payload
            ),
            "two content lengths": (
                b"POST /v1/chat/completions HTTP/1.1\r\n"
                b"Host: relay\r\nContent-Type: application/json\r\n"
                b"Content-Length: " + str(len(payload)).encode() + b"\r\n"
                b"Content-Length: 3\r\n\r\n" + payload
            ),
            "blank transfer encoding then chunked": (
                b"POST /v1/chat/completions HTTP/1.1\r\n"
                b"Host: relay\r\nContent-Type: application/json\r\n"
                b"Transfer-Encoding: \r\nTransfer-Encoding: chunked\r\n"
                b"Content-Length: " + str(len(payload)).encode() + b"\r\n\r\n" + payload
            ),
            "absolute form request target": (
                b"POST https://opencode.ai/v1/chat/completions HTTP/1.1\r\n"
                b"Host: relay\r\nContent-Type: application/json\r\n"
                b"Content-Length: " + str(len(payload)).encode() + b"\r\n\r\n" + payload
            ),
        }
        for label, request in cases.items():
            with self.subTest(case=label):
                with self.start():
                    raw = self.raw_exchange(request)
                self.assertTrue(
                    raw.startswith(b"HTTP/1.1 400") or raw.startswith(b"HTTP/1.1 405"),
                    msg=raw[:200],
                )
                self.assertEqual(self.upstream.count, 0)


class AuthorizationGateTests(TransportTestCase):
    def test_each_upstream_request_is_authorized_as_the_inference_operation(self) -> None:
        with self.start():
            self.post()
            self.post()
        self.assertEqual(len(self.authorizations), 2)
        for index, entry in enumerate(self.authorizations, start=1):
            self.assertEqual(entry["service"], TRANSPORT.PROVIDER_SERVICE)
            self.assertEqual(entry["operation"], TRANSPORT.PROVIDER_OPERATION)
            self.assertEqual(entry["access"], TRANSPORT.PROVIDER_ACCESS)
            self.assertEqual(entry["effect"], TRANSPORT.PROVIDER_EFFECT)
            self.assertEqual(entry["protocol"], TRANSPORT.SUPPORTED_PROTOCOL)
            self.assertEqual(entry["request_index"], index)
            self.assertIn(f"#model={self.model}", entry["target"])
            self.assertNotIn("repository", entry["operation"])

    def test_a_denied_request_makes_no_upstream_call_and_stops_the_attempt(self) -> None:
        def deny(request) -> bool:
            self.authorizations.append(request.to_dict())
            return False

        with self.start(authorize=deny) as transport:
            status, _, body = self.post()
            following = self.post()
            result = transport.result()
        self.assertEqual(status, 502)
        self.assertEqual(self.error_code(body), TRANSPORT.STATUS_AUTHORIZATION_DENIED)
        self.assertEqual(following[0], 503)
        self.assertEqual(self.upstream.count, 0)
        self.assertEqual(result.status, TRANSPORT.STATUS_AUTHORIZATION_DENIED)

    def test_a_failing_authorization_callback_denies_rather_than_allows(self) -> None:
        def broken(_request) -> bool:
            raise ValueError("gate defect")

        with self.start(authorize=broken) as transport:
            status, _, body = self.post()
            result = transport.result()
        self.assertEqual(status, 502)
        self.assertEqual(self.error_code(body), TRANSPORT.STATUS_AUTHORIZATION_DENIED)
        self.assertEqual(self.upstream.count, 0)
        self.assertEqual(result.status, TRANSPORT.STATUS_AUTHORIZATION_DENIED)
        self.assertNotIn("gate defect", json.dumps(result.to_dict()))

    def test_a_callback_transport_error_never_returns_its_message_to_the_child(self) -> None:
        # The callback holds parent-side context, so its own TransportError must
        # be sanitized exactly like any other callback failure.
        def leaking(_request) -> bool:
            raise TRANSPORT.TransportError(
                SENTINEL, code=TRANSPORT.STATUS_AUTHORIZATION_DENIED
            )

        with self.start(authorize=leaking) as transport:
            status, _, body = self.post()
            result = transport.result()
        self.assertEqual(status, 502)
        self.assertEqual(self.error_code(body), TRANSPORT.STATUS_AUTHORIZATION_DENIED)
        self.assertEqual(self.upstream.count, 0)
        self.assertNotIn(SENTINEL.encode("ascii"), body)
        self.assertNotIn(SENTINEL, json.dumps(result.to_dict()))

    def test_an_authorization_slower_than_the_deadline_dispatches_nothing(self) -> None:
        def slow(request) -> bool:
            self.authorizations.append(request.to_dict())
            time.sleep(1.25)
            return True

        limits = TRANSPORT.TransportLimits(wall_deadline_seconds=1.0)
        with self.start(authorize=slow, limits=limits) as transport:
            with contextlib.suppress(OSError, http.client.HTTPException, IndexError):
                self.post()
            result = transport.close()
        self.assertEqual(len(self.authorizations), 1)
        self.assertEqual(self.upstream.count, 0)
        self.assertEqual(result.upstream_request_count, 0)
        self.assertEqual(result.status, TRANSPORT.STATUS_DEADLINE_EXCEEDED)


class UpstreamOutcomeTests(TransportTestCase):
    def test_a_redirect_is_refused_rather_than_followed(self) -> None:
        self.upstream.set_default({"kind": "redirect", "status": 302})
        with self.start() as transport:
            status, _, body = self.post()
            result = transport.result()
        self.assertEqual(status, 502)
        self.assertEqual(self.error_code(body), TRANSPORT.STATUS_REDIRECT_REFUSED)
        self.assertEqual(result.status, TRANSPORT.STATUS_REDIRECT_REFUSED)
        self.assertEqual(self.upstream.count, 1)

    def test_refused_credentials_and_rate_limits_stop_without_a_retry(self) -> None:
        for upstream_status, expected in (
            (401, TRANSPORT.STATUS_UPSTREAM_UNAUTHORIZED),
            (403, TRANSPORT.STATUS_UPSTREAM_UNAUTHORIZED),
            (429, TRANSPORT.STATUS_UPSTREAM_RATE_LIMITED),
            (500, TRANSPORT.STATUS_UPSTREAM_STATUS_ERROR),
        ):
            with self.subTest(status=upstream_status):
                self.upstream.requests.clear()
                self.upstream.set_default({"kind": "status", "status": upstream_status})
                socket_path = self.workspace / f"relay-{upstream_status}.sock"
                with self.start(socket_path=socket_path) as transport:
                    status, _, body = self.post(socket_path=socket_path)
                    following = self.post(socket_path=socket_path)
                    result = transport.result()
                self.assertEqual(status, 502)
                self.assertEqual(self.error_code(body), expected)
                self.assertEqual(following[0], 503)
                self.assertEqual(result.status, expected)
                self.assertEqual(self.upstream.count, 1)

    def test_a_truncated_stream_is_reported_as_truncated(self) -> None:
        self.upstream.set_default({"kind": "truncated", "body": b"data: partial"})
        with self.start() as transport:
            self.post()
            result = transport.result()
        self.assertEqual(result.status, TRANSPORT.STATUS_UPSTREAM_STREAM_TRUNCATED)

    def test_a_truncated_stream_never_appends_a_second_response_to_the_first(self) -> None:
        # Once a 2xx body has started, a further status line would be consumed
        # as body bytes and a client could read corruption as success.
        self.upstream.set_default({"kind": "truncated", "body": b"data: partial"})
        payload = b'{"model":"glm-5.3","messages":[]}'
        with self.start() as transport:
            raw = self.raw_exchange(
                b"POST /v1/chat/completions HTTP/1.1\r\n"
                b"Host: relay\r\nContent-Type: application/json\r\n"
                b"Connection: close\r\n"
                b"Content-Length: " + str(len(payload)).encode() + b"\r\n\r\n" + payload
            )
            result = transport.result()
        self.assertEqual(result.status, TRANSPORT.STATUS_UPSTREAM_STREAM_TRUNCATED)
        self.assertEqual(raw.count(b"HTTP/1.1 "), 1, msg=raw[:400])
        self.assertNotIn(b"502 Bad Gateway", raw)

    def test_an_unreachable_upstream_ends_the_attempt_without_a_retry(self) -> None:
        self._stop_upstream()
        self.addCleanup(lambda: None)
        with self.start() as transport:
            status, _, body = self.post()
            result = transport.result()
        self.assertEqual(status, 502)
        self.assertEqual(self.error_code(body), TRANSPORT.STATUS_UPSTREAM_UNAVAILABLE)
        self.assertEqual(result.status, TRANSPORT.STATUS_UPSTREAM_UNAVAILABLE)
        self.assertEqual(result.upstream_request_count, 1)

    def _stop_upstream(self) -> None:
        if getattr(self, "_upstream_stopped", False):
            return
        self._upstream_stopped = True
        self.upstream.shutdown()
        self.upstream.server_close()
        self.upstream_thread.join(timeout=10)


class BudgetTests(TransportTestCase):
    def test_the_request_budget_refuses_before_contacting_the_upstream(self) -> None:
        limits = TRANSPORT.TransportLimits(max_upstream_requests=1)
        with self.start(limits=limits) as transport:
            first = self.post()
            second = self.post()
            result = transport.result()
        self.assertEqual(first[0], 200)
        self.assertEqual(second[0], 502)
        self.assertEqual(
            self.error_code(second[2]), TRANSPORT.STATUS_REQUEST_BUDGET_EXHAUSTED
        )
        self.assertEqual(self.upstream.count, 1)
        self.assertEqual(result.status, TRANSPORT.STATUS_REQUEST_BUDGET_EXHAUSTED)

    def test_an_oversized_request_body_is_refused_without_an_upstream_request(self) -> None:
        limits = TRANSPORT.TransportLimits(max_request_bytes=512)
        with self.start(limits=limits):
            payload = {"model": self.model, "messages": [{"role": "user", "content": "x" * 4096}]}
            status, _, body = self.post(payload)
        self.assertEqual(status, 400)
        self.assertEqual(self.error_code(body), TRANSPORT.STATUS_MALFORMED_REQUEST)
        self.assertEqual(self.upstream.count, 0)

    def test_an_oversized_response_ends_the_attempt(self) -> None:
        limits = TRANSPORT.TransportLimits(max_response_bytes=1024)
        self.upstream.set_default({"kind": "ok", "body": b"y" * 8192})
        with self.start(limits=limits) as transport:
            self.post()
            result = transport.result()
        self.assertEqual(result.status, TRANSPORT.STATUS_RESPONSE_BUDGET_EXCEEDED)

    def test_the_wall_deadline_ends_a_slow_stream(self) -> None:
        limits = TRANSPORT.TransportLimits(wall_deadline_seconds=1.0)
        self.upstream.set_default({"kind": "slow", "seconds": 8.0})
        with self.start(limits=limits) as transport:
            self.post()
            result = transport.result()
        self.assertEqual(result.status, TRANSPORT.STATUS_DEADLINE_EXCEEDED)
        self.assertLess(result.elapsed_seconds, 8.0)

    def test_limits_may_only_lower_the_shipped_ceilings(self) -> None:
        for field, value in (
            ("wall_deadline_seconds", TRANSPORT.DEFAULT_WALL_DEADLINE_SECONDS + 1),
            ("max_upstream_requests", TRANSPORT.DEFAULT_MAX_UPSTREAM_REQUESTS + 1),
            ("max_request_bytes", TRANSPORT.DEFAULT_MAX_REQUEST_BYTES + 1),
            ("max_response_bytes", TRANSPORT.DEFAULT_MAX_RESPONSE_BYTES + 1),
            ("max_upstream_requests", 0),
            ("wall_deadline_seconds", 0),
        ):
            with self.subTest(field=field, value=value):
                with self.assertRaises(TRANSPORT.TransportError):
                    TRANSPORT.TransportLimits(**{field: value})

    def test_cancellation_stops_the_relay_without_a_further_upstream_request(self) -> None:
        with self.start() as transport:
            transport.cancel()
            status, _, body = self.post()
            result = transport.result()
        self.assertEqual(status, 503)
        self.assertEqual(self.error_code(body), TRANSPORT.STATUS_CANCELLED)
        self.assertEqual(self.upstream.count, 0)
        self.assertEqual(result.status, TRANSPORT.STATUS_CANCELLED)

    def test_a_peer_handlers_terminal_verdict_stops_a_dispatched_request(self) -> None:
        # A terminal status recorded anywhere, including by another handler's
        # failure, must stop a request that already passed its admission check.
        with self.start() as transport:
            relay = transport._relay
            original = relay.track_upstream

            def peer_verdict(connection) -> None:
                original(connection)
                relay.record_terminal(TRANSPORT.STATUS_MODEL_REJECTED, "peer verdict")

            relay.track_upstream = peer_verdict
            status, _, payload = self.post()
        self.assertEqual(status, 502)
        self.assertEqual(self.upstream.count, 0)
        self.assertEqual(self.error_code(payload), TRANSPORT.STATUS_MODEL_REJECTED)

    def test_a_recorded_verdict_alone_refuses_a_send(self) -> None:
        # The guard must refuse on the verdict itself, without depending on the
        # socket teardown that follows it as a separate step.
        with self.start() as transport:
            relay = transport._relay
            original = relay.track_upstream

            def verdict_only(connection) -> None:
                original(connection)
                relay.state.record_terminal(TRANSPORT.STATUS_CANCELLED, "verdict only")

            relay.track_upstream = verdict_only
            status, _, payload = self.post()
        self.assertEqual(status, 502)
        self.assertEqual(self.upstream.count, 0)
        self.assertEqual(self.error_code(payload), TRANSPORT.STATUS_CANCELLED)

    def test_a_verdict_cannot_land_while_a_send_holds_the_guard(self) -> None:
        # This is the ordering a counter cannot express. While a sender is
        # inside the guard, no verdict may be recorded, so none can slip into
        # the interval between that sender's check and its request.
        with self.start() as transport:
            state = transport._relay.state
            recorded = threading.Event()

            def verdict() -> None:
                state.record_terminal(TRANSPORT.STATUS_CANCELLED, "concurrent verdict")
                recorded.set()

            worker = threading.Thread(target=verdict, daemon=True)
            with state.send_guard():
                worker.start()
                self.assertFalse(recorded.wait(0.5))
                self.assertNotIn(state.status, TRANSPORT.TERMINAL_STATUSES)
            self.assertTrue(recorded.wait(5))
            worker.join(5)
        self.assertEqual(self.upstream.count, 0)

    def test_an_expired_deadline_cannot_land_while_a_send_holds_the_guard(self) -> None:
        # Routing every verdict through record_terminal is not enough on its
        # own: the wall-clock verdict is published from claim_dispatch, and it
        # has to take the same lock in the same order or it lands mid-send.
        with self.start() as transport:
            state = transport._relay.state
            dispatched = threading.Event()

            def expire() -> None:
                state.deadline = time.monotonic() - 1.0
                with contextlib.suppress(TRANSPORT.TransportError):
                    state.claim_dispatch()
                dispatched.set()

            worker = threading.Thread(target=expire, daemon=True)
            with state.send_guard():
                worker.start()
                self.assertFalse(dispatched.wait(0.5))
                self.assertNotIn(state.status, TRANSPORT.TERMINAL_STATUSES)
            self.assertTrue(dispatched.wait(5))
            worker.join(5)
            self.assertEqual(state.status, TRANSPORT.STATUS_DEADLINE_EXCEEDED)
        self.assertEqual(self.upstream.count, 0)

    def test_the_send_guard_refuses_an_attempt_whose_deadline_expired(self) -> None:
        # The guard is the last point that can still refuse, so an attempt that
        # expired after dispatch must not reach the wire.
        with self.start() as transport:
            state = transport._relay.state
            state.deadline = time.monotonic() - 1.0
            with self.assertRaises(TRANSPORT.TransportError) as caught:
                with state.send_guard():
                    self.fail("the guard admitted an expired attempt")
            self.assertEqual(caught.exception.code, TRANSPORT.STATUS_DEADLINE_EXCEEDED)
            self.assertEqual(state.status, TRANSPORT.STATUS_DEADLINE_EXCEEDED)
        self.assertEqual(self.upstream.count, 0)

    def test_the_relay_status_cannot_be_assigned_from_outside(self) -> None:
        # The ordering guarantee depends on every write taking the send lock,
        # so a direct assignment has to fail rather than quietly bypass it.
        with self.start() as transport:
            state = transport._relay.state
            with self.assertRaises(AttributeError):
                state.status = TRANSPORT.STATUS_CANCELLED
            with self.assertRaises(AttributeError):
                state.detail = "bypassed"
            self.assertNotIn(state.status, TRANSPORT.TERMINAL_STATUSES)

    def test_the_send_phase_uses_its_own_shorter_timeout(self) -> None:
        # A verdict waits behind a send, so the send must not inherit the full
        # socket timeout that exists for reading a slow upstream response.
        observed: list[float] = []
        with self.start() as transport:
            relay = transport._relay
            original = relay.open_upstream

            def watch():
                connection = original()
                real_request = connection.request

                def record(*args, **kwargs):
                    observed.append(connection.sock.gettimeout())
                    return real_request(*args, **kwargs)

                connection.request = record
                return connection

            relay.open_upstream = watch
            status, _, _ = self.post()
        self.assertEqual(status, 200)
        self.assertEqual(len(observed), 1)
        self.assertLessEqual(observed[0], TRANSPORT.MAX_REQUEST_SEND_SECONDS)
        self.assertLess(observed[0], TRANSPORT.MAX_REQUEST_READ_SECONDS)

    def test_a_terminal_verdict_after_dispatch_still_stops_the_upstream_request(self) -> None:
        # claim_dispatch and the upstream send are not one atomic step, so a
        # verdict recorded in that window must refuse the connection instead of
        # letting a credential-bearing request leave afterwards.
        relays: list[Any] = []

        def capture(request) -> bool:
            self.authorizations.append(request.to_dict())
            return True

        transport = self.start(authorize=capture)
        relay = transport._relay
        relays.append(relay)
        original = relay.open_upstream

        def cancel_then_open():
            transport.cancel()
            return original()

        relay.open_upstream = cancel_then_open
        with contextlib.suppress(OSError, http.client.HTTPException, IndexError):
            self.post()
        result = transport.close()
        self.assertEqual(len(self.authorizations), 1)
        self.assertEqual(self.upstream.count, 0)
        self.assertEqual(result.status, TRANSPORT.STATUS_CANCELLED)

    def test_a_shut_down_upstream_connection_cannot_silently_reconnect(self) -> None:
        # http.client reopens a closed connection inside request() by default,
        # which would send the credential after shutdown_active closed it.
        with self.start() as transport:
            connection = transport._relay.open_upstream()
            self.addCleanup(connection.close)
            self.assertEqual(connection.auto_open, 0)
            self.assertIsNotNone(connection.sock)
            connection.close()
            with self.assertRaises(http.client.NotConnected):
                connection.request("POST", "/v1/chat/completions", body=b"{}")
        self.assertEqual(self.upstream.count, 0)

    def test_cancellation_during_a_stream_ends_the_attempt_promptly(self) -> None:
        # Cancelling only recorded a status before, so close waited for the
        # whole stream and cancellation was advisory rather than effective.
        self.upstream.set_default({"kind": "slow", "seconds": 8.0})
        transport = self.start()
        errors: list[BaseException] = []

        def issue() -> None:
            try:
                self.post()
            except BaseException as error:  # noqa: BLE001 - the socket is cut deliberately
                errors.append(error)

        caller = threading.Thread(target=issue, daemon=True)
        caller.start()
        time.sleep(0.5)
        started = time.monotonic()
        transport.cancel()
        result = transport.close()
        elapsed = time.monotonic() - started
        caller.join(timeout=10)
        self.assertFalse(caller.is_alive())
        self.assertLess(elapsed, 4.0)
        self.assertEqual(result.status, TRANSPORT.STATUS_CANCELLED)


class CredentialBoundaryTests(TransportTestCase):
    def test_the_sanitized_result_never_carries_the_credential(self) -> None:
        with self.start() as transport:
            self.post()
            result = transport.close()
            repeated = transport.close()
        serialized = json.dumps(result.to_dict())
        self.assertNotIn(SENTINEL, serialized)
        self.assertNotIn(SENTINEL, repr(result))
        self.assertNotIn(SENTINEL, repr(transport))
        self.assertEqual(result.credential_source_class, TRANSPORT.CREDENTIAL_SOURCE_ENVIRONMENT)
        self.assertEqual(repeated.to_dict(), result.to_dict())
        self.assertNotIn(self.environment_name, serialized)

    def test_the_credential_holder_refuses_every_ordinary_disclosure_path(self) -> None:
        secret = TRANSPORT._Secret(SENTINEL)
        self.assertNotIn(SENTINEL, repr(secret))
        self.assertNotIn(SENTINEL, str(secret))
        self.assertNotIn(SENTINEL, f"{secret}")
        with self.assertRaises(TypeError):
            pickle.dumps(secret)
        self.assertEqual(secret.reveal(), SENTINEL)

    def test_a_missing_or_unsafe_credential_source_fails_closed(self) -> None:
        del os.environ[self.environment_name]
        source = self.credential_source()
        self.assertFalse(source.available())
        with self.assertRaises(TRANSPORT.TransportError) as missing:
            source.load()
        self.assertEqual(missing.exception.code, TRANSPORT.STATUS_CREDENTIAL_UNAVAILABLE)

        readable = self.workspace / "key.txt"
        readable.write_text(SENTINEL, encoding="utf-8")
        os.chmod(readable, 0o644)
        file_source = TRANSPORT.CredentialSource(
            TRANSPORT.CREDENTIAL_SOURCE_FILE, str(readable)
        )
        with self.assertRaises(TRANSPORT.TransportError) as exposed:
            file_source.load()
        self.assertEqual(exposed.exception.code, TRANSPORT.STATUS_CREDENTIAL_UNAVAILABLE)
        os.chmod(readable, 0o600)
        self.assertEqual(file_source.load().reveal(), SENTINEL)
        self.assertEqual(file_source.describe(), {"credential_source_class": "file"})
        self.assertNotIn(SENTINEL, json.dumps(file_source.describe()))

        link = self.workspace / "key-link.txt"
        link.symlink_to(readable)
        with self.assertRaises(TRANSPORT.TransportError):
            TRANSPORT.CredentialSource(TRANSPORT.CREDENTIAL_SOURCE_FILE, str(link)).load()

        blank = self.workspace / "blank.txt"
        blank.write_text("   \n", encoding="utf-8")
        os.chmod(blank, 0o600)
        with self.assertRaises(TRANSPORT.TransportError):
            TRANSPORT.CredentialSource(TRANSPORT.CREDENTIAL_SOURCE_FILE, str(blank)).load()


class BoundaryConfigurationTests(TransportTestCase):
    def test_an_unsafe_socket_path_is_refused_before_the_socket_exists(self) -> None:
        exposed = self.workspace / "exposed"
        exposed.mkdir()
        os.chmod(exposed, 0o777)
        linked = self.workspace / "linked"
        linked.symlink_to(exposed)
        occupied = self.workspace / "occupied.sock"
        occupied.write_text("", encoding="utf-8")
        cases = {
            "relative": Path("relay.sock"),
            "occupied": occupied,
            "world writable directory": exposed / "relay.sock",
            "symlinked directory": linked / "relay.sock",
            "too long": self.workspace / ("d" * 200 + ".sock"),
        }
        for label, candidate in cases.items():
            with self.subTest(case=label):
                with self.assertRaises(TRANSPORT.TransportError):
                    TRANSPORT.validate_socket_path(candidate)

    def test_the_relay_socket_is_owner_only_and_removed_on_close(self) -> None:
        transport = self.start()
        info = os.stat(self.socket_path)
        self.assertTrue(stat.S_ISSOCK(info.st_mode))
        self.assertEqual(info.st_uid, os.getuid())
        self.assertEqual(info.st_mode & 0o777, 0o600)
        transport.close()
        self.assertFalse(self.socket_path.exists())

    def test_only_the_admitted_protocol_and_model_shape_start_a_relay(self) -> None:
        with self.assertRaises(TRANSPORT.TransportError):
            self.start(protocol="messages")
        with self.assertRaises(TRANSPORT.TransportError):
            TRANSPORT.create_transport(
                socket_path=self.workspace / "bad-model.sock",
                model="not a model id",
                credential_source=self.credential_source(),
                authorize=self.allow_all,
                target=self.target(),
            )
        with self.assertRaises(TRANSPORT.TransportError):
            TRANSPORT.create_transport(
                socket_path=self.workspace / "no-gate.sock",
                model=self.model,
                credential_source=self.credential_source(),
                authorize="not callable",
                target=self.target(),
            )

    def test_an_upstream_override_can_only_address_loopback(self) -> None:
        self.assertTrue(TRANSPORT.UpstreamTarget().is_default)
        self.assertEqual(TRANSPORT.UpstreamTarget().url, TRANSPORT.UPSTREAM_URL)
        for host, tls in (
            ("elsewhere.invalid", False),
            ("opencode.ai", False),
            ("127.0.0.1", True),
        ):
            with self.subTest(host=host, tls=tls):
                with self.assertRaises(TRANSPORT.TransportError):
                    TRANSPORT.UpstreamTarget(host=host, port=8080, path="/x", tls=tls)

    def test_the_bridge_command_carries_socket_and_port_settings_only(self) -> None:
        with self.start() as transport:
            argv = transport.bridge_command(
                module_path="/opt/opencode_go_transport.py",
                socket_path="/run/opencode-go/relay.sock",
                port=0,
            )
        joined = " ".join(argv)
        self.assertIn("bridge", argv)
        self.assertIn("/run/opencode-go/relay.sock", argv)
        self.assertNotIn(SENTINEL, joined)
        self.assertNotIn(self.environment_name, joined)
        self.assertNotIn("--api-key", joined)


class RootAndGeneratedTransportIdentityTests(unittest.TestCase):
    """The generated project must run the same transport as the root."""

    def test_root_and_generated_transports_stay_identical(self) -> None:
        self.assertTrue(TEMPLATE_MODULE_PATH.is_file())
        self.assertEqual(MODULE_PATH.read_bytes(), TEMPLATE_MODULE_PATH.read_bytes())
        self.assertEqual(
            MODULE_PATH.stat().st_mode & 0o777,
            TEMPLATE_MODULE_PATH.stat().st_mode & 0o777,
        )

    def test_the_fixed_upstream_route_is_the_documented_go_endpoint(self) -> None:
        self.assertEqual(
            TRANSPORT.UPSTREAM_URL, "https://opencode.ai/zen/go/v1/chat/completions"
        )
        self.assertEqual(TRANSPORT.SUPPORTED_PROTOCOLS, ("chat_completions",))


class ProcessLifetimeTests(TransportTestCase):
    """A terminated owner must leave no relay behind."""

    def _owner_script(self, socket_path: Path, ready: Path, install_handler: bool) -> str:
        return textwrap.dedent(
            f"""
            import json, os, signal, sys, threading, time
            sys.path.insert(0, {str(ROOT / "scripts")!r})
            from project_workflow import opencode_go_transport as T

            transport = T.create_transport(
                socket_path={str(socket_path)!r},
                model={self.model!r},
                credential_source=T.CredentialSource("environment", {self.environment_name!r}),
                authorize=lambda request: True,
                target=T.UpstreamTarget(host="127.0.0.1", port={self.upstream.server_address[1]}, path=T.UPSTREAM_PATH, tls=False),
            )
            if {install_handler!r}:
                def stop(_signum, _frame):
                    transport.close()
                    raise SystemExit(0)
                signal.signal(signal.SIGTERM, stop)
            open({str(ready)!r}, "w").write("ready\\n")
            while True:
                time.sleep(0.05)
            """
        )

    def _run_owner(self, install_handler: bool) -> tuple[subprocess.Popen[str], Path]:
        socket_path = self.workspace / ("handled.sock" if install_handler else "abrupt.sock")
        ready = self.workspace / f"ready-{socket_path.name}"
        script = self.workspace / f"owner-{socket_path.name}.py"
        script.write_text(self._owner_script(socket_path, ready, install_handler), encoding="utf-8")
        process = subprocess.Popen(
            [sys.executable, "-B", str(script)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        self.addCleanup(self._reap, process)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not ready.exists():
            if process.poll() is not None:
                self.fail(f"the owner exited early: {process.communicate()[1]}")
            time.sleep(0.05)
        self.assertTrue(ready.exists(), "the owner never reported a listening relay")
        return process, socket_path

    @staticmethod
    def _reap(process: subprocess.Popen[str]) -> None:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        for stream in (process.stdout, process.stderr):
            if stream is not None and not stream.closed:
                stream.close()

    def test_a_handled_termination_closes_the_relay_and_removes_the_socket(self) -> None:
        process, socket_path = self._run_owner(install_handler=True)
        self.assertEqual(self.post(socket_path=socket_path)[0], 200)
        process.send_signal(signal.SIGTERM)
        self.assertEqual(process.wait(timeout=30), 0)
        self.assertFalse(socket_path.exists())

    def test_an_abrupt_termination_leaves_no_relay_listening(self) -> None:
        process, socket_path = self._run_owner(install_handler=False)
        self.assertEqual(self.post(socket_path=socket_path)[0], 200)
        process.send_signal(signal.SIGTERM)
        process.wait(timeout=30)
        self.assertNotEqual(process.returncode, 0)
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(5)
        with self.assertRaises(OSError):
            try:
                connection.connect(str(socket_path))
                connection.sendall(b"POST /v1/chat/completions HTTP/1.1\r\n\r\n")
                self.assertEqual(connection.recv(1), b"")
                raise OSError("no listener answered")
            finally:
                connection.close()


class SandboxedCredentialIsolationTests(TransportTestCase):
    """Prove the isolation claim against a real Bubblewrap child.

    An unavailable sandbox fails this check. Skipping it would report that
    isolation holds on a host where it was never tested.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.bwrap = shutil.which("bwrap")
        if cls.bwrap is None:
            raise RuntimeError("bwrap is required for OpenCode Go transport isolation tests")
        probe = subprocess.run(
            [cls.bwrap, "--unshare-all", "--ro-bind", "/", "/", "--die-with-parent", "/bin/true"],
            capture_output=True,
            check=False,
        )
        if probe.returncode != 0:
            raise RuntimeError(
                "bwrap is installed but cannot create the namespaces the isolation tests require"
            )

    def _sandbox_command(self, *, module: Path, script: Path, inner_socket: str) -> list[str]:
        argv = [
            self.bwrap,
            "--unshare-all",
            "--unshare-user",
            "--new-session",
            "--disable-userns",
            "--cap-drop",
            "ALL",
            "--die-with-parent",
            "--clearenv",
            "--tmpfs",
            "/",
            "--dir",
            "/tmp",
            "--dir",
            "/run",
            "--dir",
            "/var",
            "--dir",
            "/etc",
            "--dir",
            "/home",
        ]
        for directory in (*SANDBOX_SYSTEM_DIRECTORIES, *SANDBOX_SYSTEM_OPTIONAL_DIRECTORIES):
            if Path(directory).exists():
                argv.extend(("--ro-bind", directory, directory))
        for system_file in SANDBOX_SYSTEM_FILES:
            if Path(system_file).is_file():
                argv.extend(("--ro-bind", system_file, system_file))
        argv.extend(
            (
                "--ro-bind",
                str(module),
                "/opt/opencode_go_transport.py",
                "--ro-bind",
                str(script),
                "/opt/child.py",
                "--dir",
                "/run/opencode-go",
                "--bind",
                str(self.socket_path),
                inner_socket,
                "--proc",
                "/proc",
                "--dev",
                "/dev",
                "--chdir",
                "/tmp",
                "--setenv",
                "PATH",
                "/usr/bin:/bin",
                "--setenv",
                "HOME",
                "/home",
                "--",
                "/usr/bin/env",
                "python3",
                "/opt/child.py",
            )
        )
        return argv

    def _child_script(self, inner_socket: str, upstream_port: int) -> str:
        # The needle is joined at run time so the probe never finds its own
        # source text and reports a leak that did not happen.
        return textwrap.dedent(
            f"""
            import http.client, json, os, socket, sys, threading
            sys.path.insert(0, "/opt")
            import opencode_go_transport as T

            needle = "".join([{SENTINEL_HEAD!r}, {SENTINEL_TAIL!r}])
            box, ready = [], threading.Event()
            threading.Thread(
                target=T.run_bridge,
                kwargs=dict(socket_path={inner_socket!r}, port=0, ready=ready, server_box=box),
                daemon=True,
            ).start()
            if not ready.wait(30):
                print("BRIDGE_NOT_READY")
                raise SystemExit(1)
            port = box[0].server_address[1]
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
            connection.request(
                "POST",
                T.BRIDGE_REQUEST_PATH,
                body=json.dumps({{"model": {self.model!r}, "messages": [{{"role": "user", "content": "hi"}}]}}),
                headers={{
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + T.PLACEHOLDER_API_KEY,
                    "Accept": "text/event-stream",
                }},
            )
            response = connection.getresponse()
            findings = {{"status": response.status, "answer": response.read().decode("utf-8")}}

            readable = ["=".join(item) for item in os.environ.items()]
            for special in ("/proc/self/environ", "/proc/self/cmdline", "/proc/self/maps"):
                try:
                    readable.append(open(special, "rb").read().decode("utf-8", "replace"))
                except OSError:
                    pass
            for root in ("/opt", "/run", "/etc", "/tmp", "/home", "/var"):
                for directory, _subdirectories, names in os.walk(root):
                    for name in names:
                        try:
                            readable.append(
                                open(os.path.join(directory, name), "rb")
                                .read(1000000)
                                .decode("utf-8", "replace")
                            )
                        except OSError:
                            pass
            findings["credential_visible"] = any(needle in blob for blob in readable)

            probe = socket.socket()
            probe.settimeout(5)
            try:
                probe.connect(("127.0.0.1", {upstream_port}))
                findings["reached_upstream_directly"] = True
            except OSError:
                findings["reached_upstream_directly"] = False
            finally:
                probe.close()

            resolver = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            resolver.settimeout(5)
            try:
                resolver.connect(("1.1.1.1", 443))
                findings["reached_public_internet"] = True
            except OSError:
                findings["reached_public_internet"] = False
            finally:
                resolver.close()

            print("FINDINGS " + json.dumps(findings))
            """
        )

    def test_a_private_network_child_gets_an_answer_but_never_the_credential(self) -> None:
        self.upstream.set_default(
            {
                "kind": "ok",
                "body": b'data: {"type":"text","text":"answer"}\n\n',
                "content_type": "text/event-stream",
            }
        )
        inner_socket = "/run/opencode-go/relay.sock"
        script = self.workspace / "child.py"
        script.write_text(
            self._child_script(inner_socket, self.upstream.server_address[1]), encoding="utf-8"
        )
        self.assertNotIn(SENTINEL, script.read_text(encoding="utf-8"))
        with self.start() as transport:
            completed = subprocess.run(
                self._sandbox_command(
                    module=MODULE_PATH, script=script, inner_socket=inner_socket
                ),
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            result = transport.result()
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        marker = "FINDINGS "
        line = next(
            (row for row in completed.stdout.splitlines() if row.startswith(marker)), None
        )
        self.assertIsNotNone(line, msg=completed.stdout + completed.stderr)
        findings = json.loads(line[len(marker) :])
        self.assertEqual(findings["status"], 200)
        self.assertIn("answer", findings["answer"])
        self.assertFalse(findings["credential_visible"])
        self.assertFalse(findings["reached_upstream_directly"])
        self.assertFalse(findings["reached_public_internet"])
        self.assertNotIn(SENTINEL, completed.stdout)
        self.assertNotIn(SENTINEL, completed.stderr)
        self.assertEqual(result.status, TRANSPORT.STATUS_OK)
        self.assertEqual(self.upstream.count, 1)
        self.assertEqual(self.upstream.requests[0]["authorization"], f"Bearer {SENTINEL}")


if __name__ == "__main__":
    unittest.main()
