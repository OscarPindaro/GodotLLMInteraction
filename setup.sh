if ! command -v uv >/dev/null 2>&1; then
  echo "Error: 'uv' is not installed. Install it from https://docs.astral.sh/uv/" >&2
  exit 1
fi

uv sync
if ! uv tool list 2>/dev/null | grep -q '^semble '; then
  uv tool install semble
fi

uv run pre-commit install

# Download extension_api.json reference files for integration tests
if command -v godotctl >/dev/null 2>&1; then
  echo "Downloading extension_api.json reference files..."
  godotctl download-apis || echo "Warning: could not download extension_api.json files. Integration tests will be skipped."
  godotctl check-missing-binaries
else
  echo "Warning: godotctl not found. Install it with: bash install-godot.sh self-register"
  echo "  Then run: godotctl download-apis"
fi
