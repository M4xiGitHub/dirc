#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.}"
FORCE="${2:-0}"

if [[ ! -d "$ROOT/.git" ]]; then
  echo "dirc: not a git repo: $ROOT" >&2
  exit 2
fi

HOOKS_DIR="$ROOT/.git/hooks"

install_hook() {
  local name="$1"
  local target="$HOOKS_DIR/$name"

  if [[ -e "$target" && "$FORCE" != "1" ]]; then
    echo "dirc: hook already exists (pass FORCE=1): $target" >&2
    return 1
  fi

  cat >"$target" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

python3 -m dirc check
EOF

  chmod +x "$target"
  echo "dirc: installed $target"
}

install_hook pre-commit || true
install_hook pre-push || true

