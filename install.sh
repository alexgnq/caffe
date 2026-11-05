#!/bin/sh
# Install caffe: curl -fsSL https://raw.githubusercontent.com/alexgnq/caffe/main/install.sh | sh
set -eu

REPO_RAW="https://raw.githubusercontent.com/alexgnq/caffe/${CAFFE_REF:-main}"
BIN_DIR="${CAFFE_BIN_DIR:-$HOME/.local/bin}"

if [ "$(uname -s)" != "Darwin" ]; then
  echo "caffe needs macOS (it wraps caffeinate)." >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "caffe needs python3. Install Xcode Command Line Tools: xcode-select --install" >&2
  exit 1
fi

mkdir -p "$BIN_DIR"
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
curl -fsSL "$REPO_RAW/caffe" -o "$tmp"
chmod 755 "$tmp"
mv "$tmp" "$BIN_DIR/caffe"
trap - EXIT

echo "☕ caffe installed to $BIN_DIR/caffe"
case ":$PATH:" in
  *":$BIN_DIR:"*) echo "Run: caffe" ;;
  *) echo "Add $BIN_DIR to your PATH, e.g.: echo 'export PATH=\"$BIN_DIR:\$PATH\"' >> ~/.zshrc" ;;
esac
