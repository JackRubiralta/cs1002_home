#!/usr/bin/env bash
# Linux / macOS installer: a private Python environment, Playwright + its browser,
# and a `cs1002` command in ~/.local/bin.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null || { echo "Python 3 is needed (python3)"; exit 1; }
echo "Setting up Python environment in $HERE/.venv ..."
"$PY" -m venv "$HERE/.venv"
"$HERE/.venv/bin/python" -m pip install --quiet --upgrade pip
"$HERE/.venv/bin/python" -m pip install --quiet -r "$HERE/requirements.txt"
echo "Getting the browser used for signing in (Chromium, ~150 MB, once) ..."
"$HERE/.venv/bin/python" -m playwright install chromium
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/cs1002" <<LAUNCH
#!/usr/bin/env bash
exec "$HERE/.venv/bin/python" "$HERE/cs1002.py" "\$@"
LAUNCH
chmod +x "$HOME/.local/bin/cs1002"
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *)
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
  echo "(added ~/.local/bin to PATH in ~/.bashrc - open a new terminal)";;
esac
"$HOME/.local/bin/cs1002" setup || true
