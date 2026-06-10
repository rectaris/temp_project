"""Shared security detection patterns for generated workflow checks."""

from __future__ import annotations

import re


PRIVATE_KEY_MATERIAL = re.compile(r"-----BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----")
REMOTE_SCRIPT_PIPE = re.compile(r"\b(curl|wget)\b[^\n|]*\|\s*(sh|bash|zsh)\b")
SUDO_COMMAND = re.compile(r"^\s*sudo\b", re.MULTILINE)
