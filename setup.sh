if ! command -v uv >/dev/null 2>&1; then
  echo "Error: 'uv' is not installed. Install it from https://docs.astral.sh/uv/" >&2
  exit 1
fi

uv sync
if ! uv tool list 2>/dev/null | grep -q '^semble '; then
  uv tool install semble
fi