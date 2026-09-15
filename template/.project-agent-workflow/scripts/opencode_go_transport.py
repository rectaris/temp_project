#!/usr/bin/env python3
"""Forward bounded OpenCode Go inference without giving the child the credential.

A delegated process must be able to ask one admitted model for one answer, and
must not be able to read the upstream API key, choose another destination, or
turn the parent into a general forwarding service. Those two requirements are
met by splitting the path in two.

The parent process owns a Unix-socket relay. It holds the upstream key in
memory only, rewrites every request into the one fixed Go Chat Completions
call, authorizes each actual upstream request separately, and enforces request,
byte, and wall-clock budgets. The child receives only the socket, so it can
reach exactly that one relay and nothing else.

Inside the sandbox a small loopback bridge accepts the OpenAI-compatible
request that OpenCode already knows how to make and hands the bytes to the
mounted socket. OpenCode is configured with the loopback base URL and a
placeholder key, so a key never exists on the child side of the boundary and a
child that reads its own files, environment, or process view finds nothing to
steal.

The module is written for two layouts, so it imports nothing from its siblings
and the root and generated copies stay byte-identical.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import errno
import http.client
import http.server
import json
import os
import re
import secrets
import socket
import socketserver
import ssl
import stat
import sys
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any

UPSTREAM_SCHEME = "https"
UPSTREAM_HOST = "opencode.ai"
UPSTREAM_PORT = 443
UPSTREAM_PATH = "/zen/go/v1/chat/completions"
UPSTREAM_URL = f"{UPSTREAM_SCHEME}://{UPSTREAM_HOST}{UPSTREAM_PATH}"

SUPPORTED_PROTOCOL = "chat_completions"
SUPPORTED_PROTOCOLS = (SUPPORTED_PROTOCOL,)

PROVIDER_SERVICE = "opencode_go"
PROVIDER_OPERATION = "inference.chat_completions"
PROVIDER_ACCESS = "read"
PROVIDER_EFFECT = "ordinary"

BRIDGE_REQUEST_PATH = "/v1/chat/completions"
BRIDGE_BASE_PATH = "/v1"
BRIDGE_HOST = "127.0.0.1"
LOOPBACK_HOSTS = ("127.0.0.1", "::1", "localhost")

# The child is told to use this string as its API key. It authorizes nothing:
# the relay discards whatever the child sends and supplies the real credential
# itself, so a leak of this value discloses no secret.
PLACEHOLDER_API_KEY = "opencode-go-local-bridge-placeholder"
FORWARDED_USER_AGENT = "project-agent-workflow-opencode-go/1"
SESSION_HEADER = "x-opencode-session"

DEFAULT_WALL_DEADLINE_SECONDS = 300.0
DEFAULT_MAX_UPSTREAM_REQUESTS = 32
DEFAULT_MAX_REQUEST_BYTES = 2 * 1024 * 1024
DEFAULT_MAX_RESPONSE_BYTES = 8 * 1024 * 1024

MAX_UNIX_SOCKET_PATH_BYTES = 107
MAX_REQUEST_HEADER_BYTES = 16 * 1024
# A child that declares a body it never finishes sending would otherwise hold a
# handler thread for the whole attempt. The read is bounded separately from the
# wall deadline so that an unfinished request fails as a malformed request
# rather than as an expired attempt.
MAX_REQUEST_READ_SECONDS = 30.0
# The send phase runs under its own smaller bound, because a terminal verdict
# waits behind it and cancellation must not inherit the full socket timeout.
MAX_REQUEST_SEND_SECONDS = 5.0
# One wording for the wall-clock verdict, so the published detail and the
# error a caller sees can never drift apart.
DEADLINE_DETAIL = "the attempt reached its wall-clock deadline"
MAX_REQUEST_HEADERS = 64

STATUS_OK = "ok"
STATUS_NOT_STARTED = "not_started"
STATUS_AUTHORIZATION_DENIED = "authorization_denied"
STATUS_CANCELLED = "cancelled"
STATUS_CREDENTIAL_UNAVAILABLE = "credential_unavailable"
STATUS_DEADLINE_EXCEEDED = "deadline_exceeded"
STATUS_MALFORMED_REQUEST = "malformed_request"
STATUS_MODEL_REJECTED = "model_rejected"
STATUS_REDIRECT_REFUSED = "redirect_refused"
STATUS_REQUEST_BUDGET_EXHAUSTED = "request_budget_exhausted"
STATUS_REQUEST_REJECTED = "request_rejected"
STATUS_RESPONSE_BUDGET_EXCEEDED = "response_budget_exceeded"
STATUS_UPSTREAM_RATE_LIMITED = "upstream_rate_limited"
STATUS_UPSTREAM_STATUS_ERROR = "upstream_status_error"
STATUS_UPSTREAM_STREAM_TRUNCATED = "upstream_stream_truncated"
STATUS_UPSTREAM_UNAVAILABLE = "upstream_unavailable"
STATUS_UPSTREAM_UNAUTHORIZED = "upstream_unauthorized"

# A terminal status other than ok stops the relay. Restarting after an
# uncertain termination would repeat a request whose upstream effect is
# unknown, and retrying a refused credential or an exhausted budget would only
# spend the remaining allowance on the same refusal.
TERMINAL_STATUSES = frozenset(
    {
        STATUS_AUTHORIZATION_DENIED,
        STATUS_CANCELLED,
        STATUS_CREDENTIAL_UNAVAILABLE,
        STATUS_DEADLINE_EXCEEDED,
        STATUS_MODEL_REJECTED,
        STATUS_REDIRECT_REFUSED,
        STATUS_REQUEST_BUDGET_EXHAUSTED,
        STATUS_RESPONSE_BUDGET_EXCEEDED,
        STATUS_UPSTREAM_RATE_LIMITED,
        STATUS_UPSTREAM_STATUS_ERROR,
        STATUS_UPSTREAM_STREAM_TRUNCATED,
        STATUS_UPSTREAM_UNAVAILABLE,
        STATUS_UPSTREAM_UNAUTHORIZED,
    }
)

CREDENTIAL_SOURCE_ENVIRONMENT = "environment"
CREDENTIAL_SOURCE_FILE = "file"
CREDENTIAL_SOURCE_CLASSES = (CREDENTIAL_SOURCE_ENVIRONMENT, CREDENTIAL_SOURCE_FILE)

# The child is configured with a placeholder key, so it sends an Authorization
# header on every request. That header is discarded rather than refused: the
# relay supplies the real credential itself, so whatever the child sent decides
# nothing and rejecting it would only break the ordinary path.
STRIPPED_REQUEST_HEADERS = frozenset(
    {
        "api-key",
        "authorization",
        "cookie",
        "proxy-authorization",
        "x-api-key",
        "x-goog-api-key",
    }
)

# These headers do not carry authentication; they try to change where the
# request appears to come from or where it goes. A child that sends one is
# reaching past the boundary, so the request fails instead of continuing
# quietly with less than it asked for.
DENIED_REQUEST_HEADERS = frozenset(
    {
        "forwarded",
        "proxy-connection",
        "x-forwarded-for",
        "x-forwarded-host",
        "x-forwarded-proto",
    }
)

FORWARDED_REQUEST_HEADERS = ("content-type", "accept")
ALLOWED_CONTENT_TYPES = frozenset({"application/json"})
ALLOWED_ACCEPT_VALUES = frozenset({"application/json", "text/event-stream", "*/*"})

DENIED_REQUEST_BODY_KEYS = frozenset(
    {
        "api-key",
        "api_base",
        "api_key",
        "apibase",
        "apikey",
        "authorization",
        "base_url",
        "baseurl",
        "credentials",
        "endpoint",
        "extra_body",
        "extra_headers",
        "headers",
        "host",
        "key",
        "organization",
        "origin",
        "provider",
        "provider_id",
        "providerid",
        "proxy",
        "secret",
        "token",
        "url",
    }
)

MODEL_PATTERN = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
SESSION_PATTERN = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
CREDENTIAL_PATTERN = re.compile(r"\A[\x21-\x7e]{8,4096}\Z")
ENVIRONMENT_NAME_PATTERN = re.compile(r"\A[A-Z][A-Z0-9_]{0,63}\Z")


class TransportError(RuntimeError):
    """Raised when the transport refuses to start, forward, or continue.

    The message is written for a report and carries no credential material,
    because the same text reaches logs, plans, and terminal output.
    """

    def __init__(self, message: str, *, code: str = STATUS_REQUEST_REJECTED) -> None:
        super().__init__(message)
        self.code = code


class _Secret:
    """Hold the upstream key so that no ordinary serialization can reach it.

    Repr, str, format, pickling, and copying are the paths by which a value
    reaches a log line, a manifest, or an error record without anyone deciding
    that it should. Each of them is closed here, so the only way to obtain the
    key is to ask for it explicitly at the point of use.
    """

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "<opencode-go-credential redacted>"

    __str__ = __repr__

    def __format__(self, _spec: str) -> str:
        return repr(self)

    def __reduce__(self) -> Any:
        raise TypeError("an OpenCode Go credential must not be serialized")

    def __deepcopy__(self, _memo: Any) -> Any:
        raise TypeError("an OpenCode Go credential must not be copied")

    def __copy__(self) -> Any:
        raise TypeError("an OpenCode Go credential must not be copied")


@dataclasses.dataclass(frozen=True)
class TransportLimits:
    """Bound one attempt in requests, bytes, and elapsed time."""

    wall_deadline_seconds: float = DEFAULT_WALL_DEADLINE_SECONDS
    max_upstream_requests: int = DEFAULT_MAX_UPSTREAM_REQUESTS
    max_request_bytes: int = DEFAULT_MAX_REQUEST_BYTES
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES

    def __post_init__(self) -> None:
        if not isinstance(self.wall_deadline_seconds, (int, float)):
            raise TransportError("wall_deadline_seconds must be a number")
        if not (0 < float(self.wall_deadline_seconds) <= DEFAULT_WALL_DEADLINE_SECONDS):
            raise TransportError(
                "wall_deadline_seconds must be positive and may only lower "
                f"{DEFAULT_WALL_DEADLINE_SECONDS}"
            )
        for name, ceiling in (
            ("max_upstream_requests", DEFAULT_MAX_UPSTREAM_REQUESTS),
            ("max_request_bytes", DEFAULT_MAX_REQUEST_BYTES),
            ("max_response_bytes", DEFAULT_MAX_RESPONSE_BYTES),
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise TransportError(f"{name} must be an integer")
            if not 0 < value <= ceiling:
                raise TransportError(f"{name} must be positive and may only lower {ceiling}")

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class CredentialSource:
    """Name where the parent reads the key, never the key itself."""

    kind: str
    locator: str

    def __post_init__(self) -> None:
        if self.kind not in CREDENTIAL_SOURCE_CLASSES:
            raise TransportError(
                f"unsupported credential source class: {self.kind}",
                code=STATUS_CREDENTIAL_UNAVAILABLE,
            )
        if not isinstance(self.locator, str) or not self.locator.strip():
            raise TransportError(
                "credential source locator must be a non-empty string",
                code=STATUS_CREDENTIAL_UNAVAILABLE,
            )
        if self.kind == CREDENTIAL_SOURCE_ENVIRONMENT and not ENVIRONMENT_NAME_PATTERN.fullmatch(
            self.locator
        ):
            raise TransportError(
                "credential environment variable name is not an ordinary upper-case identifier",
                code=STATUS_CREDENTIAL_UNAVAILABLE,
            )

    def describe(self) -> dict[str, str]:
        """Report the source class only, never the exact binding."""

        return {"credential_source_class": self.kind}

    def available(self) -> bool:
        """Answer whether the key can be read, without reading its value."""

        if self.kind == CREDENTIAL_SOURCE_ENVIRONMENT:
            return bool(os.environ.get(self.locator, "").strip())
        path = Path(self.locator)
        try:
            info = path.stat()
        except OSError:
            return False
        return stat.S_ISREG(info.st_mode) and info.st_size > 0

    def load(self) -> _Secret:
        if self.kind == CREDENTIAL_SOURCE_ENVIRONMENT:
            raw = os.environ.get(self.locator)
            if raw is None:
                raise TransportError(
                    "the selected credential environment variable is not set",
                    code=STATUS_CREDENTIAL_UNAVAILABLE,
                )
        else:
            path = Path(self.locator)
            if path.is_symlink():
                raise TransportError(
                    "the selected credential file must not be a symbolic link",
                    code=STATUS_CREDENTIAL_UNAVAILABLE,
                )
            try:
                info = path.stat()
            except OSError as error:
                raise TransportError(
                    f"the selected credential file cannot be read: {error.strerror}",
                    code=STATUS_CREDENTIAL_UNAVAILABLE,
                ) from None
            if not stat.S_ISREG(info.st_mode):
                raise TransportError(
                    "the selected credential file must be a regular file",
                    code=STATUS_CREDENTIAL_UNAVAILABLE,
                )
            if info.st_uid != os.getuid():
                raise TransportError(
                    "the selected credential file must belong to the current user",
                    code=STATUS_CREDENTIAL_UNAVAILABLE,
                )
            if info.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
                raise TransportError(
                    "the selected credential file must not be group or world accessible",
                    code=STATUS_CREDENTIAL_UNAVAILABLE,
                )
            raw = path.read_text(encoding="utf-8", errors="strict")
        value = raw.strip()
        if not CREDENTIAL_PATTERN.fullmatch(value):
            # The value itself stays out of the message: a caller reading this
            # report is told that the shape is wrong, not what was found.
            raise TransportError(
                "the selected credential is empty or contains characters an HTTP header cannot carry",
                code=STATUS_CREDENTIAL_UNAVAILABLE,
            )
        return _Secret(value)


@dataclasses.dataclass(frozen=True)
class UpstreamTarget:
    """Name the exact destination one relay may reach.

    Production uses the fixed Go route. A test may substitute a loopback
    target, and only a loopback target, so an override can never become a way
    to send an authorized request somewhere else.
    """

    host: str = UPSTREAM_HOST
    port: int = UPSTREAM_PORT
    path: str = UPSTREAM_PATH
    tls: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.host, str) or not self.host:
            raise TransportError("upstream host must be a non-empty string")
        if not isinstance(self.port, int) or isinstance(self.port, bool):
            raise TransportError("upstream port must be an integer")
        if not 0 < self.port <= 65535:
            raise TransportError("upstream port must be a valid TCP port")
        if not isinstance(self.path, str) or not self.path.startswith("/"):
            raise TransportError("upstream path must be an absolute path")
        if self.is_default:
            return
        if self.host not in LOOPBACK_HOSTS:
            raise TransportError(
                "an upstream override may only address a loopback host, "
                f"so {UPSTREAM_URL} remains the only reachable external destination"
            )
        if self.tls:
            raise TransportError("a loopback upstream override must not claim TLS")

    @property
    def is_default(self) -> bool:
        return (
            self.host == UPSTREAM_HOST
            and self.port == UPSTREAM_PORT
            and self.path == UPSTREAM_PATH
            and self.tls is True
        )

    @property
    def url(self) -> str:
        scheme = "https" if self.tls else "http"
        if (self.tls and self.port == 443) or (not self.tls and self.port == 80):
            return f"{scheme}://{self.host}{self.path}"
        return f"{scheme}://{self.host}:{self.port}{self.path}"


@dataclasses.dataclass(frozen=True)
class AuthorizationRequest:
    """Describe one actual upstream call for the project authorization gate."""

    service: str
    access: str
    operation: str
    target: str
    effect: str
    model: str
    protocol: str
    request_index: int

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


AuthorizationCallback = Callable[[AuthorizationRequest], bool]


@dataclasses.dataclass(frozen=True)
class TransportResult:
    """Report how one attempt ended, in terms safe to keep."""

    status: str
    detail: str
    model: str
    protocol: str
    upstream_url: str
    upstream_override: bool
    session_id: str
    credential_source_class: str
    downstream_request_count: int
    upstream_request_count: int
    rejected_request_count: int
    upstream_response_bytes: int
    elapsed_seconds: float
    limits: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.status == STATUS_OK

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def validate_model(model: str) -> str:
    if not isinstance(model, str) or not MODEL_PATTERN.fullmatch(model):
        raise TransportError("the admitted model must be an exact ordinary model identifier")
    return model


def validate_protocol(protocol: str) -> str:
    if protocol not in SUPPORTED_PROTOCOLS:
        raise TransportError(
            f"unsupported OpenCode Go protocol: {protocol}; "
            f"this release admits only {', '.join(SUPPORTED_PROTOCOLS)}"
        )
    return protocol


def validate_session_id(session_id: str) -> str:
    if not isinstance(session_id, str) or not SESSION_PATTERN.fullmatch(session_id):
        raise TransportError("the session identity must be an ordinary bounded token")
    return session_id


def new_session_id() -> str:
    """Choose one stable per-attempt identity the child cannot influence."""

    return f"pawgo{secrets.token_hex(12)}"


def validate_socket_path(socket_path: str | os.PathLike[str]) -> Path:
    """Refuse a socket path the parent does not exclusively control.

    The socket is the whole boundary. A path another user can reach, replace,
    or already occupies would let someone else answer in the relay's place, so
    each of those conditions fails before the socket exists.
    """

    path = Path(socket_path)
    if not path.is_absolute():
        raise TransportError("the relay socket path must be absolute")
    text = str(path)
    if len(os.fsencode(text)) > MAX_UNIX_SOCKET_PATH_BYTES:
        raise TransportError(
            f"the relay socket path exceeds the {MAX_UNIX_SOCKET_PATH_BYTES}-byte Unix socket limit"
        )
    if "\x00" in text:
        raise TransportError("the relay socket path must not contain a null byte")
    if path.parent == path:
        raise TransportError("the relay socket path must name an entry inside a directory")
    for component in (path, *path.parents):
        if component.is_symlink():
            raise TransportError(
                "the relay socket path must not traverse a symbolic link"
            )
    if path.exists():
        raise TransportError("the relay socket path is already occupied")
    parent = path.parent
    try:
        parent_info = parent.stat()
    except OSError as error:
        raise TransportError(
            f"the relay socket directory cannot be read: {error.strerror}"
        ) from None
    if not stat.S_ISDIR(parent_info.st_mode):
        raise TransportError("the relay socket parent must be a directory")
    if parent_info.st_uid != os.getuid():
        raise TransportError("the relay socket directory must belong to the current user")
    if parent_info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise TransportError(
            "the relay socket directory must not be writable by other users"
        )
    return path


def _header_name(raw: str) -> str:
    return raw.strip().lower()


def _split_media_type(raw: str) -> str:
    return raw.split(";", 1)[0].strip().lower()


class _DuplicateJSONKey(ValueError):
    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJSONKey(key)
        result[key] = value
    return result


class _RelayState:
    """Own every counter and the one terminal verdict for an attempt."""

    def __init__(self, limits: TransportLimits) -> None:
        self._lock = threading.Lock()
        self._limits = limits
        self._started = time.monotonic()
        self.deadline = self._started + float(limits.wall_deadline_seconds)
        self.downstream_requests = 0
        self.upstream_requests = 0
        self.rejected_requests = 0
        self.response_bytes = 0
        self._status = STATUS_NOT_STARTED
        self._detail = ""
        # A send cannot be recalled once it starts, so the terminal verdict and
        # the start of a send take this lock in turn. It is ordered before
        # `_lock`; nothing acquires them the other way round.
        self._send_lock = threading.Lock()

    @property
    def status(self) -> str:
        """Read the current status.

        There is deliberately no setter. Every write goes through `_publish` or
        `_publish_locked`, which is what keeps the `_send_lock` ordering from
        depending on each caller remembering it.
        """

        return self._status

    @property
    def detail(self) -> str:
        return self._detail

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self._started

    @property
    def remaining(self) -> float:
        return self.deadline - time.monotonic()

    def stopped(self) -> bool:
        with self._lock:
            return self.status in TERMINAL_STATUSES

    def _publish_locked(self, status: str, detail: str) -> None:
        """Assign the status. The caller already holds `_send_lock` and `_lock`."""

        if self._status in TERMINAL_STATUSES:
            return
        self._status = status
        self._detail = detail

    def _publish(self, status: str, detail: str) -> None:
        """Assign the status in the one order the send guard relies on."""

        with self._send_lock:
            with self._lock:
                self._publish_locked(status, detail)

    def record_terminal(self, status: str, detail: str) -> None:
        """Keep the first terminal verdict, because it caused the rest.

        The verdict is written while `_send_lock` is held, so it can never land
        between a sender's admission check and the request that sender makes.
        Waiting here is what buys that ordering; the send phase carries its own
        short socket timeout so the wait stays bounded.
        """

        self._publish(status, detail)

    @contextlib.contextmanager
    def send_guard(self) -> Iterator[None]:
        """Order one upstream send against the terminal verdict.

        A counter cannot express this. Reserving a slot and then sending leaves
        the interval between the two unguarded, so a verdict recorded in that
        interval would still be followed by a credential-bearing request.

        This is also the last point that can still refuse an expired attempt, so
        the deadline is rechecked here rather than only at dispatch.
        """

        with self._send_lock:
            with self._lock:
                if self._status in TERMINAL_STATUSES:
                    raise TransportError(
                        "the relay reached a terminal status before this request was sent",
                        code=self._status,
                    )
                if self.deadline - time.monotonic() <= 0:
                    self._publish_locked(STATUS_DEADLINE_EXCEEDED, DEADLINE_DETAIL)
                    raise TransportError(DEADLINE_DETAIL, code=STATUS_DEADLINE_EXCEEDED)
            yield

    def record_success(self) -> None:
        self._publish(STATUS_OK, "")

    def count_downstream(self) -> None:
        with self._lock:
            self.downstream_requests += 1

    def count_rejected(self) -> None:
        with self._lock:
            self.rejected_requests += 1

    def claim_upstream_slot(self) -> int:
        """Reserve one upstream request, or refuse before any bytes are sent."""

        with self._lock:
            if self.status in TERMINAL_STATUSES:
                raise TransportError(
                    "the relay already reached a terminal status and forwards nothing further",
                    code=self.status,
                )
            if self.upstream_requests >= self._limits.max_upstream_requests:
                raise TransportError(
                    "the attempt has already used its upstream request budget",
                    code=STATUS_REQUEST_BUDGET_EXHAUSTED,
                )
            self.upstream_requests += 1
            return self.upstream_requests

    def release_upstream_slot(self) -> None:
        """Return an unused reservation so a denial does not spend the budget."""

        with self._lock:
            if self.upstream_requests > 0:
                self.upstream_requests -= 1

    def claim_dispatch(self) -> None:
        """Admit network I/O only while the attempt is still live.

        The authorization callback runs before this, and it may be slow, so the
        terminal verdict and the deadline are rechecked here. The expired
        verdict is published outside `_lock` so it still takes `_send_lock`
        first and cannot land inside another sender's guarded interval.
        """

        with self._lock:
            if self._status in TERMINAL_STATUSES:
                raise TransportError(
                    "the relay reached a terminal status before this request was dispatched",
                    code=self._status,
                )
            expired = self.deadline - time.monotonic() <= 0
        if expired:
            self._publish(STATUS_DEADLINE_EXCEEDED, DEADLINE_DETAIL)
            raise TransportError(DEADLINE_DETAIL, code=STATUS_DEADLINE_EXCEEDED)

    def add_response_bytes(self, count: int) -> None:
        with self._lock:
            self.response_bytes += count
            if self.response_bytes > self._limits.max_response_bytes:
                raise TransportError(
                    "the attempt exceeded its upstream response byte budget",
                    code=STATUS_RESPONSE_BUDGET_EXCEEDED,
                )

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "status": self.status,
                "detail": self.detail,
                "downstream_request_count": self.downstream_requests,
                "upstream_request_count": self.upstream_requests,
                "rejected_request_count": self.rejected_requests,
                "upstream_response_bytes": self.response_bytes,
            }


class _RelayHandler(http.server.BaseHTTPRequestHandler):
    """Answer one child request by making at most one fixed upstream call."""

    protocol_version = "HTTP/1.1"
    server_version = "opencode-go-relay"
    sys_version = ""

    # A Unix peer has no address, and the default implementation indexes the
    # empty client address, so the name is fixed here instead.
    def address_string(self) -> str:
        return "unix"

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def log_error(self, _format: str, *_args: Any) -> None:
        return

    @property
    def relay(self) -> "_Relay":
        return self.server.relay  # type: ignore[attr-defined]

    def setup(self) -> None:
        super().setup()
        self._headers_sent = False
        limits = self.relay.limits
        with contextlib.suppress(OSError):
            # The read window stays strictly inside the attempt so an unfinished
            # request fails as a malformed request while the relay can still
            # answer, rather than being cut off by the deadline teardown.
            self.connection.settimeout(
                max(
                    0.5,
                    min(MAX_REQUEST_READ_SECONDS, float(limits.wall_deadline_seconds) / 2),
                )
            )
        self.relay.track_downstream(self.connection)

    def finish(self) -> None:
        self.relay.forget_downstream(self.connection)
        super().finish()

    def do_GET(self) -> None:
        self._refuse_method()

    def do_PUT(self) -> None:
        self._refuse_method()

    def do_HEAD(self) -> None:
        self._refuse_method()

    def do_DELETE(self) -> None:
        self._refuse_method()

    def do_PATCH(self) -> None:
        self._refuse_method()

    def do_OPTIONS(self) -> None:
        self._refuse_method()

    def do_CONNECT(self) -> None:
        # A tunnel would make the relay a general forwarding service, which is
        # exactly the capability the child must not gain.
        self._refuse_method()

    def _refuse_method(self) -> None:
        self.relay.state.count_downstream()
        self.relay.state.count_rejected()
        self._send_error(
            405,
            STATUS_REQUEST_REJECTED,
            f"the relay forwards only POST {BRIDGE_REQUEST_PATH}",
        )

    def do_POST(self) -> None:
        state = self.relay.state
        state.count_downstream()
        if state.stopped():
            state.count_rejected()
            snapshot = state.snapshot()
            self._send_error(
                503,
                str(snapshot["status"]),
                "the relay already reached a terminal status and forwards nothing further",
            )
            return
        try:
            body, forwarded = self._read_admissible_request()
        except TransportError as error:
            state.count_rejected()
            if error.code in TERMINAL_STATUSES:
                self.relay.record_terminal(error.code, str(error))
            self._send_error(400, error.code, str(error))
            return
        try:
            self._forward(body, forwarded)
        except TransportError as error:
            self.relay.record_terminal(error.code, str(error))
            self._send_error(502, error.code, str(error))

    def _read_admissible_request(self) -> tuple[bytes, dict[str, str]]:
        relay = self.relay
        limits = relay.limits
        self._require_strict_framing()
        if self.path != BRIDGE_REQUEST_PATH:
            raise TransportError(
                f"the relay forwards only {BRIDGE_REQUEST_PATH}",
                code=STATUS_REQUEST_REJECTED,
            )
        if self.headers.get_all("Transfer-Encoding"):
            raise TransportError(
                "the relay requires a declared Content-Length so the request stays bounded",
                code=STATUS_MALFORMED_REQUEST,
            )
        for raw_name in self.headers.keys():
            if _header_name(raw_name) in DENIED_REQUEST_HEADERS:
                raise TransportError(
                    f"the relay refuses the {_header_name(raw_name)} request header",
                    code=STATUS_REQUEST_REJECTED,
                )
        supplied_session = self.headers.get(SESSION_HEADER)
        if supplied_session is not None and supplied_session != relay.session_id:
            # The child may echo the identity it was given, but it may not
            # select a different one, because the identity is the parent's.
            raise TransportError(
                f"the relay refuses a {SESSION_HEADER} value the parent did not select",
                code=STATUS_REQUEST_REJECTED,
            )
        raw_lengths = self.headers.get_all("Content-Length")
        if not raw_lengths:
            raise TransportError(
                "the relay requires a Content-Length", code=STATUS_MALFORMED_REQUEST
            )
        if len(raw_lengths) != 1:
            # Two declared lengths let a downstream and an upstream parser
            # disagree about where the body ends.
            raise TransportError(
                "the relay requires exactly one Content-Length",
                code=STATUS_MALFORMED_REQUEST,
            )
        raw_length = raw_lengths[0]
        if not raw_length.strip().isdigit():
            raise TransportError(
                "the relay requires an integer Content-Length", code=STATUS_MALFORMED_REQUEST
            )
        length = int(raw_length.strip())
        if length <= 0:
            raise TransportError(
                "the relay requires a non-empty request body", code=STATUS_MALFORMED_REQUEST
            )
        if length > limits.max_request_bytes:
            raise TransportError(
                "the request body exceeds the admitted request byte budget",
                code=STATUS_MALFORMED_REQUEST,
            )
        try:
            body = self.rfile.read(length)
        except (TimeoutError, OSError):
            raise TransportError(
                "the request body did not arrive within its bounded read window",
                code=STATUS_MALFORMED_REQUEST,
            ) from None
        if len(body) != length:
            raise TransportError(
                "the request body ended before its declared length",
                code=STATUS_MALFORMED_REQUEST,
            )
        forwarded = self._admissible_headers()
        self._require_admitted_payload(body)
        return body, forwarded

    def _require_strict_framing(self) -> None:
        """Refuse a request whose framing two parsers could read differently."""

        if not self.raw_requestline.endswith(b"\r\n"):
            raise TransportError(
                "the relay requires CRLF request framing",
                code=STATUS_MALFORMED_REQUEST,
            )
        if len(self.requestline.split(" ")) != 3 or not self.path.startswith("/"):
            # Absolute-form and authority-form targets are how a client asks a
            # forwarder to choose a destination, which this relay never does.
            raise TransportError(
                "the relay accepts only an origin-form request target",
                code=STATUS_REQUEST_REJECTED,
            )
        if getattr(self.headers, "defects", None):
            raise TransportError(
                "the relay refuses a request with malformed headers",
                code=STATUS_MALFORMED_REQUEST,
            )
        header_bytes = sum(
            len(name) + len(value) + 4 for name, value in self.headers.items()
        )
        if len(self.headers) > MAX_REQUEST_HEADERS or header_bytes > MAX_REQUEST_HEADER_BYTES:
            raise TransportError(
                "the request headers exceed the admitted header budget",
                code=STATUS_MALFORMED_REQUEST,
            )

    def _admissible_headers(self) -> dict[str, str]:
        forwarded: dict[str, str] = {}
        content_type = self.headers.get("Content-Type")
        if content_type is None or _split_media_type(content_type) not in ALLOWED_CONTENT_TYPES:
            raise TransportError(
                "the relay forwards only an application/json request body",
                code=STATUS_REQUEST_REJECTED,
            )
        forwarded["Content-Type"] = "application/json"
        accept = self.headers.get("Accept")
        if accept is not None:
            values = {_split_media_type(part) for part in accept.split(",") if part.strip()}
            if not values or not values <= ALLOWED_ACCEPT_VALUES:
                raise TransportError(
                    "the relay forwards only a JSON or event-stream Accept header",
                    code=STATUS_REQUEST_REJECTED,
                )
            forwarded["Accept"] = ", ".join(sorted(values))
        return forwarded

    def _require_admitted_payload(self, body: bytes) -> None:
        relay = self.relay
        try:
            payload = json.loads(body.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise TransportError(
                "the relay forwards only a JSON object body", code=STATUS_MALFORMED_REQUEST
            ) from None
        except _DuplicateJSONKey as error:
            # The body is forwarded verbatim, so a duplicate key would let the
            # relay authorize one value while the upstream parser reads another.
            raise TransportError(
                f"the relay refuses a duplicated {error.key} request field",
                code=STATUS_MALFORMED_REQUEST,
            ) from None
        if not isinstance(payload, dict):
            raise TransportError(
                "the relay forwards only a JSON object body", code=STATUS_MALFORMED_REQUEST
            )
        for key in payload:
            if not isinstance(key, str):
                raise TransportError(
                    "the relay forwards only string request keys",
                    code=STATUS_MALFORMED_REQUEST,
                )
            if key.strip().lower().replace(" ", "") in DENIED_REQUEST_BODY_KEYS:
                raise TransportError(
                    f"the relay refuses the {key} request field because it can change "
                    "the destination, the authorization, or the protocol",
                    code=STATUS_REQUEST_REJECTED,
                )
        model = payload.get("model")
        if not isinstance(model, str) or model != relay.model:
            # A transport that quietly rewrote the model would report success
            # for an answer the caller never asked for.
            raise TransportError(
                f"the relay forwards only the admitted model {relay.model}",
                code=STATUS_MODEL_REJECTED,
            )

    def _forward(self, body: bytes, forwarded: Mapping[str, str]) -> None:
        relay = self.relay
        state = relay.state
        if state.remaining <= 0:
            raise TransportError(DEADLINE_DETAIL, code=STATUS_DEADLINE_EXCEEDED)
        index = state.claim_upstream_slot()
        request = AuthorizationRequest(
            service=PROVIDER_SERVICE,
            access=PROVIDER_ACCESS,
            operation=PROVIDER_OPERATION,
            target=f"{relay.target.url}#model={relay.model}",
            effect=PROVIDER_EFFECT,
            model=relay.model,
            protocol=relay.protocol,
            request_index=index,
        )
        try:
            admitted = relay.authorize(request)
        except TransportError:
            state.release_upstream_slot()
            raise
        if not admitted:
            state.release_upstream_slot()
            raise TransportError(
                "the project authorization gate refused this upstream inference request",
                code=STATUS_AUTHORIZATION_DENIED,
            )
        try:
            state.claim_dispatch()
        except TransportError:
            state.release_upstream_slot()
            raise
        try:
            connection = relay.open_upstream()
        except (OSError, http.client.HTTPException) as error:
            raise TransportError(
                f"the upstream inference request did not complete: {type(error).__name__}",
                code=STATUS_UPSTREAM_UNAVAILABLE,
            ) from None
        try:
            relay.track_upstream(connection)
        except TransportError:
            with contextlib.suppress(Exception):
                connection.close()
            raise
        try:
            # Only the content headers survive the boundary. The credential is
            # added here and nowhere else, so no downstream header can reach
            # the upstream request even if the allowlist above were widened.
            downstream = {
                name: value
                for name, value in forwarded.items()
                if _header_name(name) in FORWARDED_REQUEST_HEADERS
            }
            headers = {
                **downstream,
                "Authorization": f"Bearer {relay.reveal_credential()}",
                "User-Agent": FORWARDED_USER_AGENT,
                SESSION_HEADER: relay.session_id,
                "Content-Length": str(len(body)),
                "Connection": "close",
            }
            try:
                # send_guard holds the lock that record_terminal also needs, so
                # no verdict can land between its check and this request.
                # getresponse stays outside it: reading a slow upstream must
                # not keep a cancellation waiting.
                with state.send_guard():
                    self._send_upstream(connection, relay, body, headers)
                response = connection.getresponse()
            except (OSError, http.client.HTTPException) as error:
                raise TransportError(
                    f"the upstream inference request did not complete: {type(error).__name__}",
                    code=STATUS_UPSTREAM_UNAVAILABLE,
                ) from None
            self._relay_response(response)
        finally:
            relay.forget_upstream(connection)
            with contextlib.suppress(Exception):
                connection.close()

    def _send_upstream(
        self,
        connection: http.client.HTTPConnection,
        relay: "_Relay",
        body: bytes,
        headers: dict[str, str],
    ) -> None:
        """Write the one upstream request under a short, separate timeout.

        The connection timeout has to cover a slow upstream read, but holding
        the send lock for that long would make a cancellation wait just as long.
        The send gets its own smaller bound and the original is restored for the
        response.
        """

        original = connection.sock.gettimeout()  # type: ignore[union-attr]
        send_timeout = max(1.0, min(MAX_REQUEST_SEND_SECONDS, relay.state.remaining))
        connection.sock.settimeout(send_timeout)  # type: ignore[union-attr]
        try:
            connection.request("POST", relay.target.path, body=body, headers=headers)
        finally:
            with contextlib.suppress(Exception):
                connection.sock.settimeout(original)  # type: ignore[union-attr]

    def _relay_response(self, response: http.client.HTTPResponse) -> None:
        relay = self.relay
        state = relay.state
        status = response.status
        if 300 <= status < 400:
            # Following a redirect would send an authorized request to a
            # destination this policy never admitted.
            raise TransportError(
                f"the upstream answered with redirect status {status}, which the relay refuses",
                code=STATUS_REDIRECT_REFUSED,
            )
        if status in (401, 403):
            raise TransportError(
                f"the upstream refused the credential with status {status}",
                code=STATUS_UPSTREAM_UNAUTHORIZED,
            )
        if status == 429:
            raise TransportError(
                "the upstream rate limited the attempt, and the relay does not retry",
                code=STATUS_UPSTREAM_RATE_LIMITED,
            )
        if not 200 <= status < 300:
            raise TransportError(
                f"the upstream answered with status {status}",
                code=STATUS_UPSTREAM_STATUS_ERROR,
            )
        self.send_response(status)
        content_type = response.getheader("Content-Type")
        self.send_header("Content-Type", content_type or "application/json")
        self.send_header("Connection", "close")
        declared = response.getheader("Content-Length")
        expected: int | None = None
        if declared is not None and declared.isdigit():
            expected = int(declared)
            self.send_header("Content-Length", declared)
        else:
            self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        self._headers_sent = True
        self.close_connection = True
        chunked = expected is None
        transferred = 0
        try:
            while True:
                if state.remaining <= 0:
                    raise TransportError(
                        "the attempt reached its wall-clock deadline while streaming",
                        code=STATUS_DEADLINE_EXCEEDED,
                    )
                # read1 returns as soon as bytes are available, so a streamed
                # answer stays observable and the deadline check below runs
                # between events instead of after the whole response.
                chunk = response.read1(65536)
                if not chunk:
                    break
                transferred += len(chunk)
                state.add_response_bytes(len(chunk))
                if chunked:
                    self.wfile.write(f"{len(chunk):x}\r\n".encode("ascii"))
                    self.wfile.write(chunk)
                    self.wfile.write(b"\r\n")
                else:
                    self.wfile.write(chunk)
                self.wfile.flush()
        except http.client.IncompleteRead:
            raise TransportError(
                "the upstream response ended before its declared length",
                code=STATUS_UPSTREAM_STREAM_TRUNCATED,
            ) from None
        except OSError as error:
            raise TransportError(
                f"the upstream response could not be relayed: {type(error).__name__}",
                code=STATUS_UPSTREAM_STREAM_TRUNCATED,
            ) from None
        if expected is not None and transferred != expected:
            raise TransportError(
                "the upstream response ended before its declared length",
                code=STATUS_UPSTREAM_STREAM_TRUNCATED,
            )
        if chunked:
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        state.record_success()

    def _send_error(self, http_status: int, code: str, message: str) -> None:
        self.close_connection = True
        if self._headers_sent:
            # A second status line after a started 2xx body would be read as
            # part of that body, so the connection is dropped instead.
            with contextlib.suppress(Exception):
                self.wfile.flush()
            with contextlib.suppress(Exception):
                self.connection.shutdown(socket.SHUT_RDWR)
            return
        payload = json.dumps(
            {"error": {"type": "opencode_go_transport", "code": code, "message": message}}
        ).encode("utf-8")
        with contextlib.suppress(OSError):
            self.send_response(http_status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Connection", "close")
            self.end_headers()
            self._headers_sent = True
            self.wfile.write(payload)
            self.wfile.flush()


class _RelayServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    # Handler threads are joined on close so that no forwarding thread outlives
    # the attempt that authorized it.
    daemon_threads = False
    block_on_close = True
    allow_reuse_address = False
    request_queue_size = 8

    def __init__(self, socket_path: str, relay: "_Relay") -> None:
        self.relay = relay
        super().__init__(socket_path, _RelayHandler)

    def handle_error(self, request: Any, client_address: Any) -> None:
        # The default implementation prints the traceback, which can contain
        # request bytes. The terminal status already records the outcome.
        return


class _Relay:
    """Hold everything one attempt needs, including the key the child must not see."""

    def __init__(
        self,
        *,
        socket_path: Path,
        model: str,
        protocol: str,
        session_id: str,
        credential_source: CredentialSource,
        credential: _Secret,
        authorize: AuthorizationCallback,
        limits: TransportLimits,
        target: UpstreamTarget,
    ) -> None:
        self.socket_path = socket_path
        self.model = model
        self.protocol = protocol
        self.session_id = session_id
        self.credential_source = credential_source
        self._credential = credential
        self._authorize = authorize
        self.limits = limits
        self.target = target
        self.state = _RelayState(limits)
        self._active_lock = threading.Lock()
        self._active_upstream: set[http.client.HTTPConnection] = set()
        self._active_downstream: set[socket.socket] = set()
        self._terminating = False

    def reveal_credential(self) -> str:
        return self._credential.reveal()

    def authorize(self, request: AuthorizationRequest) -> bool:
        try:
            return bool(self._authorize(request))
        except Exception:  # noqa: BLE001 - a gate defect must deny, not allow
            # The callback may hold project context the child must never read,
            # so no exception text, type name, or code crosses this boundary.
            raise TransportError(
                "the project authorization gate refused this upstream inference request",
                code=STATUS_AUTHORIZATION_DENIED,
            ) from None

    def track_upstream(self, connection: http.client.HTTPConnection) -> None:
        """Register a connection, or refuse it once termination has begun.

        Registration and the terminal latch share one lock, so a connection is
        either shut down by shutdown_active or refused here. Without the latch a
        connection opened just after shutdown_active copied its set would carry
        the credential upstream after cancellation or the deadline.
        """

        with self._active_lock:
            if self._terminating:
                raise TransportError(
                    "the attempt stopped before this upstream request was sent",
                    code=self.state.status if self.state.status in TERMINAL_STATUSES
                    else STATUS_CANCELLED,
                )
            self._active_upstream.add(connection)

    def forget_upstream(self, connection: http.client.HTTPConnection) -> None:
        with self._active_lock:
            self._active_upstream.discard(connection)

    def track_downstream(self, connection: socket.socket) -> None:
        with self._active_lock:
            self._active_downstream.add(connection)

    def forget_downstream(self, connection: socket.socket) -> None:
        with self._active_lock:
            self._active_downstream.discard(connection)

    def record_terminal(self, status: str, detail: str) -> None:
        """Record a verdict and immediately stop the upstream side.

        Every terminal path goes through here so the verdict, the send barrier,
        and the upstream teardown are one step. Recording alone would leave a
        handler that is already past its admission check free to send the
        credential afterwards.
        """

        self.state.record_terminal(status, detail)
        self.bar_upstream()

    def bar_upstream(self) -> None:
        """Latch termination and drop every tracked upstream socket.

        `_RelayState.record_terminal` has already ordered the verdict against
        any send in progress, so this only has to stop connections that are
        tracked but idle, and refuse ones registered later.
        """

        with self._active_lock:
            self._terminating = True
            upstream = list(self._active_upstream)
            self._active_upstream.clear()
        for connection in upstream:
            with contextlib.suppress(Exception):
                connection.sock.shutdown(socket.SHUT_RDWR)  # type: ignore[union-attr]
            with contextlib.suppress(Exception):
                connection.close()

    def shutdown_active(self) -> None:
        """Break every live connection so a terminal verdict actually ends work.

        Recording a status stops new requests but leaves a handler blocked in
        an upstream read or a slow child write, and close joins those handlers.
        Shutting the sockets down makes cancellation and the deadline effective
        instead of advisory.
        """

        self.bar_upstream()
        with self._active_lock:
            downstream = list(self._active_downstream)
        for peer in downstream:
            with contextlib.suppress(Exception):
                peer.shutdown(socket.SHUT_RDWR)

    def open_upstream(self) -> http.client.HTTPConnection:
        """Return an already connected upstream connection that cannot reopen.

        Connecting here rather than inside request() means a tracked connection
        always owns a real socket, so shutdown_active can actually break it.
        Clearing auto_open makes a later request on a closed connection raise
        instead of silently dialling again and sending the credential.
        """

        timeout = max(1.0, min(30.0, self.state.remaining))
        if self.target.tls:
            context = ssl.create_default_context()
            connection: http.client.HTTPConnection = http.client.HTTPSConnection(
                self.target.host, self.target.port, timeout=timeout, context=context
            )
        else:
            connection = http.client.HTTPConnection(
                self.target.host, self.target.port, timeout=timeout
            )
        connection.connect()
        connection.auto_open = 0
        return connection


class InferenceTransport:
    """The parent-facing handle for one bounded attempt."""

    def __init__(self, relay: _Relay, server: _RelayServer) -> None:
        self._relay = relay
        self._server = server
        self._closed = False
        self._result: TransportResult | None = None
        self._stop = threading.Event()
        self._serve_thread = threading.Thread(
            target=self._server.serve_forever,
            kwargs={"poll_interval": 0.1},
            name="opencode-go-relay",
            daemon=True,
        )
        self._serve_thread.start()
        self._watchdog = threading.Thread(
            target=self._watch_deadline, name="opencode-go-relay-deadline", daemon=True
        )
        self._watchdog.start()

    @property
    def socket_path(self) -> Path:
        return self._relay.socket_path

    @property
    def session_id(self) -> str:
        return self._relay.session_id

    @property
    def model(self) -> str:
        return self._relay.model

    @property
    def protocol(self) -> str:
        return self._relay.protocol

    @property
    def upstream_url(self) -> str:
        return self._relay.target.url

    def endpoint(self) -> dict[str, Any]:
        """Describe the socket the child may use. It carries no secret."""

        return {
            "socket_path": str(self._relay.socket_path),
            "session_id": self._relay.session_id,
            "model": self._relay.model,
            "protocol": self._relay.protocol,
            "request_path": BRIDGE_REQUEST_PATH,
        }

    def child_configuration(self, *, bridge_port: int, bridge_host: str = BRIDGE_HOST) -> dict[str, Any]:
        """Build the provider settings OpenCode receives inside the sandbox."""

        if not isinstance(bridge_port, int) or isinstance(bridge_port, bool):
            raise TransportError("the bridge port must be an integer")
        if not 0 < bridge_port <= 65535:
            raise TransportError("the bridge port must be a valid TCP port")
        if bridge_host not in LOOPBACK_HOSTS:
            raise TransportError("the bridge host must be a loopback address")
        return {
            "provider": PROVIDER_SERVICE,
            "protocol": self._relay.protocol,
            "model": self._relay.model,
            "baseURL": f"http://{bridge_host}:{bridge_port}{BRIDGE_BASE_PATH}",
            "apiKey": PLACEHOLDER_API_KEY,
        }

    def bridge_command(
        self,
        *,
        module_path: str | os.PathLike[str],
        socket_path: str | os.PathLike[str] | None = None,
        port: int = 0,
        host: str = BRIDGE_HOST,
        port_file: str | os.PathLike[str] | None = None,
        python: str = "/usr/bin/env python3",
    ) -> list[str]:
        """Build the inner bridge command, which receives socket and port settings only."""

        if host not in LOOPBACK_HOSTS:
            raise TransportError("the bridge host must be a loopback address")
        if not isinstance(port, int) or isinstance(port, bool) or not 0 <= port <= 65535:
            raise TransportError("the bridge port must be a valid TCP port or zero")
        inner_socket = str(socket_path) if socket_path is not None else str(self._relay.socket_path)
        argv = [*python.split(), str(module_path), "bridge", "--socket", inner_socket]
        argv.extend(["--host", host, "--port", str(port)])
        if port_file is not None:
            argv.extend(["--port-file", str(port_file)])
        return argv

    def _watch_deadline(self) -> None:
        remaining = self._relay.state.remaining
        if self._stop.wait(max(0.0, remaining)):
            return
        self._relay.record_terminal(
            STATUS_DEADLINE_EXCEEDED, DEADLINE_DETAIL
        )
        # Break live work but keep accepting, so a later child request receives
        # the terminal status instead of an unexplained hang.
        self._relay.shutdown_active()

    def cancel(self, detail: str = "the parent cancelled the attempt") -> None:
        self._relay.record_terminal(STATUS_CANCELLED, detail)
        self._relay.shutdown_active()

    def result(self) -> TransportResult:
        """Return the sanitized terminal status, stable after close."""

        if self._result is not None:
            return self._result
        return self._build_result()

    def _build_result(self) -> TransportResult:
        snapshot = self._relay.state.snapshot()
        return TransportResult(
            status=str(snapshot["status"]),
            detail=str(snapshot["detail"]),
            model=self._relay.model,
            protocol=self._relay.protocol,
            upstream_url=self._relay.target.url,
            upstream_override=not self._relay.target.is_default,
            session_id=self._relay.session_id,
            credential_source_class=self._relay.credential_source.kind,
            downstream_request_count=int(snapshot["downstream_request_count"]),
            upstream_request_count=int(snapshot["upstream_request_count"]),
            rejected_request_count=int(snapshot["rejected_request_count"]),
            upstream_response_bytes=int(snapshot["upstream_response_bytes"]),
            elapsed_seconds=round(self._relay.state.elapsed, 3),
            limits=self._relay.limits.to_dict(),
        )

    def close(self) -> TransportResult:
        """Stop the relay and release the socket. Calling it twice is safe."""

        if self._closed:
            assert self._result is not None
            return self._result
        self._closed = True
        self._stop.set()
        self._relay.shutdown_active()
        with contextlib.suppress(Exception):
            self._server.shutdown()
        with contextlib.suppress(Exception):
            self._server.server_close()
        self._serve_thread.join(timeout=10.0)
        self._watchdog.join(timeout=5.0)
        with contextlib.suppress(OSError):
            os.unlink(self._relay.socket_path)
        self._result = self._build_result()
        return self._result

    def __enter__(self) -> "InferenceTransport":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()


def create_transport(
    *,
    socket_path: str | os.PathLike[str],
    model: str,
    credential_source: CredentialSource,
    authorize: AuthorizationCallback,
    protocol: str = SUPPORTED_PROTOCOL,
    session_id: str | None = None,
    limits: TransportLimits | None = None,
    target: UpstreamTarget | None = None,
) -> InferenceTransport:
    """Start one relay and return its handle. The caller owns close."""

    if not callable(authorize):
        raise TransportError("the transport requires a per-request authorization callback")
    if not isinstance(credential_source, CredentialSource):
        raise TransportError("the transport requires an explicit credential source")
    resolved_model = validate_model(model)
    resolved_protocol = validate_protocol(protocol)
    resolved_session = (
        new_session_id() if session_id is None else validate_session_id(session_id)
    )
    resolved_limits = limits if limits is not None else TransportLimits()
    if not isinstance(resolved_limits, TransportLimits):
        raise TransportError("limits must be a TransportLimits value")
    resolved_target = target if target is not None else UpstreamTarget()
    if not isinstance(resolved_target, UpstreamTarget):
        raise TransportError("target must be an UpstreamTarget value")
    path = validate_socket_path(socket_path)
    credential = credential_source.load()
    relay = _Relay(
        socket_path=path,
        model=resolved_model,
        protocol=resolved_protocol,
        session_id=resolved_session,
        credential_source=credential_source,
        credential=credential,
        authorize=authorize,
        limits=resolved_limits,
        target=resolved_target,
    )
    previous_umask = os.umask(0o077)
    try:
        server = _RelayServer(str(path), relay)
    except OSError as error:
        with contextlib.suppress(OSError):
            os.unlink(path)
        raise TransportError(
            f"the relay socket could not be created: {error.strerror}"
        ) from None
    finally:
        os.umask(previous_umask)
    try:
        os.chmod(path, 0o600)
        info = os.stat(path)
        if info.st_uid != os.getuid() or info.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            raise TransportError("the relay socket did not become owner-only")
    except (OSError, TransportError):
        with contextlib.suppress(Exception):
            server.server_close()
        with contextlib.suppress(OSError):
            os.unlink(path)
        raise
    return InferenceTransport(relay, server)


@contextlib.contextmanager
def start_transport(**kwargs: Any) -> Iterator[InferenceTransport]:
    """Run one bounded attempt and close the relay on every exit path."""

    transport = create_transport(**kwargs)
    try:
        yield transport
    finally:
        transport.close()


class _BridgeHandler(http.server.BaseHTTPRequestHandler):
    """Carry loopback bytes to the mounted socket and back, deciding nothing."""

    protocol_version = "HTTP/1.1"
    server_version = "opencode-go-bridge"
    sys_version = ""

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def log_error(self, _format: str, *_args: Any) -> None:
        return

    def do_POST(self) -> None:
        socket_path = self.server.relay_socket  # type: ignore[attr-defined]
        raw_length = self.headers.get("Content-Length")
        try:
            length = int(raw_length) if raw_length is not None else 0
        except ValueError:
            length = -1
        if length < 0:
            self._fail(400, "the bridge requires an integer Content-Length")
            return
        body = self.rfile.read(length) if length else b""
        lines = [f"POST {self.path} HTTP/1.1".encode("latin-1")]
        lines.append(b"Host: opencode-go-relay")
        for name, value in self.headers.items():
            if _header_name(name) in {"host", "connection", "content-length"}:
                continue
            lines.append(f"{name}: {value}".encode("latin-1"))
        lines.append(f"Content-Length: {len(body)}".encode("latin-1"))
        lines.append(b"Connection: close")
        request = b"\r\n".join(lines) + b"\r\n\r\n" + body
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as upstream:
                upstream.settimeout(300.0)
                upstream.connect(socket_path)
                upstream.sendall(request)
                upstream.shutdown(socket.SHUT_WR)
                while True:
                    chunk = upstream.recv(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                self.wfile.flush()
        except OSError as error:
            self._fail(502, f"the bridge could not reach the relay socket: {error.strerror}")
            return
        self.close_connection = True

    def do_GET(self) -> None:
        self._fail(405, "the bridge forwards only POST")

    def do_CONNECT(self) -> None:
        self._fail(405, "the bridge forwards only POST")

    def _fail(self, status: int, message: str) -> None:
        payload = json.dumps(
            {"error": {"type": "opencode_go_bridge", "message": message}}
        ).encode("utf-8")
        with contextlib.suppress(OSError):
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(payload)
            self.wfile.flush()
        self.close_connection = True


class _BridgeServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    block_on_close = False

    def __init__(self, address: tuple[str, int], relay_socket: str) -> None:
        self.relay_socket = relay_socket
        super().__init__(address, _BridgeHandler)


def run_bridge(
    *,
    socket_path: str,
    host: str = BRIDGE_HOST,
    port: int = 0,
    port_file: str | None = None,
    ready: threading.Event | None = None,
    server_box: list[Any] | None = None,
) -> int:
    """Serve the loopback bridge until the process is stopped.

    The bridge receives socket and port settings only. It never sees a
    credential, so the sandbox it runs in has nothing to disclose.
    """

    if host not in LOOPBACK_HOSTS:
        raise TransportError("the bridge host must be a loopback address")
    server = _BridgeServer((host, port), socket_path)
    if server_box is not None:
        server_box.append(server)
    bound_port = server.server_address[1]
    if port_file is not None:
        Path(port_file).write_text(f"{bound_port}\n", encoding="utf-8")
    if ready is not None:
        ready.set()
    try:
        server.serve_forever(poll_interval=0.1)
    finally:
        with contextlib.suppress(Exception):
            server.server_close()
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="opencode_go_transport",
        description="Bounded OpenCode Go inference transport.",
        allow_abbrev=False,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    bridge = subparsers.add_parser(
        "bridge",
        help="Run the inner loopback bridge for one sandboxed attempt.",
        allow_abbrev=False,
    )
    bridge.add_argument("--socket", required=True)
    bridge.add_argument("--host", default=BRIDGE_HOST, choices=list(LOOPBACK_HOSTS))
    bridge.add_argument("--port", type=int, default=0)
    bridge.add_argument("--port-file", default=None)
    subparsers.add_parser(
        "describe",
        help="Print the fixed upstream route and protocol this release admits.",
        allow_abbrev=False,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "describe":
        print(
            json.dumps(
                {
                    "upstream_url": UPSTREAM_URL,
                    "protocols": list(SUPPORTED_PROTOCOLS),
                    "request_path": BRIDGE_REQUEST_PATH,
                    "service": PROVIDER_SERVICE,
                    "operation": PROVIDER_OPERATION,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if not 0 <= args.port <= 65535:
        parser.error("--port must be a valid TCP port or zero")
    try:
        return run_bridge(
            socket_path=args.socket,
            host=args.host,
            port=args.port,
            port_file=args.port_file,
        )
    except KeyboardInterrupt:
        return 130
    except TransportError as error:
        print(str(error), file=sys.stderr)
        return 2
    except OSError as error:
        if error.errno == errno.ENOENT:
            print("the relay socket does not exist", file=sys.stderr)
            return 2
        print(f"the bridge could not start: {error.strerror}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
