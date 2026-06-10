copier_available() {
  command -v copier >/dev/null 2>&1 || { command -v uv >/dev/null 2>&1 && [ -f "$root/pyproject.toml" ]; }
}

run_copier() {
  if command -v copier >/dev/null 2>&1; then
    copier "$@"
  else
    (cd "$root" && UV_CACHE_DIR="$root/.uv-cache" uv run copier "$@")
  fi
}
