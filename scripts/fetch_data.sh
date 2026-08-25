#!/usr/bin/env bash
# Fetch the card pool: card database (BabelCDB) + Lua card scripts (CardScripts).
#
# Both are pinned by commit hash into data/DATA_COMMITS so benchmark results
# stay reproducible after the format moves on. The core does not ship card
# data - it asks our callbacks for it, which is what makes pinning possible.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA="$ROOT/data"
mkdir -p "$DATA"

CDB_REF="${CDB_REF:-master}"
SCRIPTS_REF="${SCRIPTS_REF:-master}"
PUZZLES_REF="${PUZZLES_REF:-master}"

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }

if [ ! -d "$DATA/BabelCDB/.git" ]; then
  log "cloning BabelCDB (card database)"
  git clone --depth 1 --branch "$CDB_REF" \
    https://github.com/ProjectIgnis/BabelCDB.git "$DATA/BabelCDB"
fi

if [ ! -d "$DATA/CardScripts/.git" ]; then
  log "cloning CardScripts (Lua card effects)"
  git clone --depth 1 --branch "$SCRIPTS_REF" \
    https://github.com/ProjectIgnis/CardScripts.git "$DATA/CardScripts"
fi

# EDOPro's puzzle collection. Each script builds a fixed field and demands a
# win in one turn, with the win condition enforced by the engine itself - so
# they are a harness stress test that needs no scoring function. EDOPro ships
# a copy, but reading whatever the install happens to hold today is not
# reproducible, hence our own pin.
if [ ! -d "$DATA/Puzzles/.git" ]; then
  log "cloning Puzzles (EDOPro puzzle collection)"
  git clone --depth 1 --branch "$PUZZLES_REF" \
    https://github.com/ProjectIgnis/Puzzles.git "$DATA/Puzzles"
fi

{
  echo "babelcdb  $(git -C "$DATA/BabelCDB" rev-parse HEAD)"
  echo "cardscripts $(git -C "$DATA/CardScripts" rev-parse HEAD)"
  echo "puzzles $(git -C "$DATA/Puzzles" rev-parse HEAD)"
} > "$DATA/DATA_COMMITS"

log "card databases:"
ls -1 "$DATA/BabelCDB"/*.cdb 2>/dev/null | xargs -n1 basename | head -20
log "scripts: $(ls "$DATA/CardScripts"/official/*.lua 2>/dev/null | wc -l | tr -d ' ') official, $(ls "$DATA/CardScripts"/*.lua 2>/dev/null | wc -l | tr -d ' ') root"
cat "$DATA/DATA_COMMITS"
