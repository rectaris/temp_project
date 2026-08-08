#!/bin/sh
set -eu

python3 .project-agent-workflow/scripts/format-plan-docs.py "$@"
