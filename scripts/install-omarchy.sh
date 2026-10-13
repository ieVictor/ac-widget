#!/usr/bin/env bash
# Instala somente nosso plugin; nunca altera fontes empacotadas ou chaves LAN.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="$ROOT/omarchy/victor.midea"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
TARGET="$CONFIG_HOME/omarchy/plugins/victor.midea"
BACKUPS="${XDG_STATE_HOME:-$HOME/.local/state}/midea-desktop/backups"
STAMP="$(date +%Y%m%d-%H%M%S)-$$"

[[ -x "$ROOT/.venv/bin/midea-desktop" ]] || {
  echo "Execute uv sync --dev no projeto primeiro." >&2; exit 1;
}
if [[ -e "$TARGET" && "${1:-}" != "--replace" ]]; then
  echo "O plugin já existe. Use --replace para atualizá-lo com backup." >&2
  exit 1
fi
command -v omarchy >/dev/null
[[ "$(omarchy-shell shell ping)" == "ok" ]]
omarchy plugin validate "$SOURCE"

mkdir -p -m 700 "$BACKUPS"
STAGING="$(mktemp -d "$BACKUPS/.midea-stage.XXXXXX")"
trap 'if [[ -d $STAGING ]]; then rm -rf -- "$STAGING"; fi' EXIT
cp -a "$SOURCE/." "$STAGING/"
"$ROOT/.venv/bin/python" - "$STAGING/manifest.json" "$ROOT/.venv/bin/midea-desktop" <<'PY'
import json
import sys
from pathlib import Path
path = Path(sys.argv[1])
data = json.loads(path.read_text())
data["barWidget"]["defaults"]["executable"] = sys.argv[2]
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
PY
omarchy plugin validate "$STAGING"

if [[ -f "$CONFIG_HOME/omarchy/shell.json" ]]; then
  cp -p "$CONFIG_HOME/omarchy/shell.json" "$BACKUPS/shell-$STAMP.json"
fi
mkdir -p "$CONFIG_HOME/omarchy/plugins"
if [[ -e "$TARGET" ]]; then
  mv -- "$TARGET" "$BACKUPS/plugin-$STAMP"
fi
mv -- "$STAGING" "$TARGET"

omarchy-shell shell rescanPlugins
omarchy plugin enable victor.midea --section right
echo "Plugin instalado: $TARGET"
echo "Backup da barra: $BACKUPS/shell-$STAMP.json"
echo "Remover da barra: omarchy plugin disable victor.midea"
echo "Se Backend.qml foi atualizado: omarchy restart shell (não executado automaticamente)"
