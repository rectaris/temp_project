#!/bin/sh
set -eu

if ! command -v skillspector >/dev/null 2>&1; then
  echo "skillspector CLI not found." >&2
  echo "Install NVIDIA SkillSpector in an isolated environment before running this check." >&2
  echo "Reference: https://github.com/NVIDIA/SkillSpector" >&2
  exit 127
fi

target=${1:-.}
if [ "$#" -gt 0 ]; then
  shift
fi

if [ "${SKILLSPECTOR_USE_LLM:-0}" = "1" ]; then
  exec skillspector scan "$target" "$@"
fi

exec skillspector scan "$target" --no-llm "$@"
