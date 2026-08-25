#!/usr/bin/env bash
# Build libocgcore as a shared library for the Python ctypes bindings.
#
# Why this script exists instead of `meson build`:
#   1. Upstream meson.build is stale — it lists group.cpp, removed upstream.
#   2. More importantly, meson does `dependency('lua-5.4')`, which finds a
#      C-compiled system Lua. ygopro-core compiles Lua *as C++* (see
#      lua/premake5.lua: `filter { "files:**.c" } compileas "C++"`), so the
#      symbols are C++-mangled and a system Lua can never link.
#      This is not cosmetic: Lua's error handling uses longjmp in C, which does
#      not run C++ destructors. Compiled as C++, luaD_throw becomes a real C++
#      throw so the core's RAII objects unwind when a card script errors.
#   premake5.lua is the maintained build path; this script reproduces it
#   without adding a premake dependency.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/vendor/ygopro-core"
OUT="$ROOT/engine/lib"
JOBS="$(sysctl -n hw.ncpu 2>/dev/null || nproc)"

CORE_REPO="https://github.com/edo9300/ygopro-core.git"
CORE_REF="${CORE_REF:-master}"

# Lua translation units premake explicitly excludes (standalone interpreter,
# compiler, test harness, and libs the core does not expose to card scripts).
LUA_EXCLUDE="lbitlib lcorolib ldblib linit loadlib loslib ltests lua luac lutf8lib onelua"

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }

# ---------------------------------------------------------------- fetch
if [ ! -d "$SRC/.git" ]; then
  log "cloning ygopro-core ($CORE_REF)"
  git clone --depth 1 --branch "$CORE_REF" "$CORE_REPO" "$SRC"
fi
if [ -z "$(ls -A "$SRC/lua/src" 2>/dev/null)" ]; then
  log "fetching vendored Lua submodule"
  git -C "$SRC" submodule update --init --recursive --depth 1
fi

BUILD="$SRC/build-native"
mkdir -p "$BUILD/lua" "$BUILD/core" "$OUT"

CXX="${CXX:-c++}"
COMMON="-O2 -fPIC"

# ---------------------------------------------------------------- lua (as C++)
log "compiling Lua 5.4 as C++ ($JOBS jobs)"
lua_srcs=()
for f in "$SRC"/lua/src/*.c; do
  base="$(basename "$f" .c)"
  case " $LUA_EXCLUDE " in *" $base "*) continue ;; esac
  lua_srcs+=("$f")
done

# Bounded-parallel compile. Plain job control rather than xargs: the compile
# lines carry enough quoting that xargs -I mangles them.
# Bounded-parallel compile. Plain job control rather than xargs: the compile
# lines carry enough quoting that xargs -I mangles them. Chunked rather than a
# sliding window because macOS ships bash 3.2, which has no `wait -n`.
run_jobs() {
  local max=$1; shift
  local fail=0 n=0 pids="" p
  for cmd in "$@"; do
    eval "$cmd" &
    pids="$pids $!"
    n=$((n + 1))
    if [ "$n" -ge "$max" ]; then
      for p in $pids; do wait "$p" || fail=1; done
      pids=""; n=0
    fi
  done
  for p in $pids; do wait "$p" || fail=1; done
  return $fail
}

lua_cmds=()
for f in "${lua_srcs[@]}"; do
  o="$BUILD/lua/$(basename "$f" .c).o"
  lua_cmds+=("$CXX $COMMON -x c++ -I\"$SRC/lua\" -include \"$SRC/lua/luaconf-customize.h\" -c \"$f\" -o \"$o\"")
done
run_jobs "$JOBS" "${lua_cmds[@]}"

# ---------------------------------------------------------------- ocgcore
log "compiling ocgcore ($JOBS jobs)"
core_srcs=("$SRC"/*.cpp)
# RNG/ is header-only today; premake lists RNG/*.cpp optimistically.
for f in "$SRC"/RNG/*.cpp; do [ -e "$f" ] && core_srcs+=("$f"); done
# -DOCGCORE_EXPORT_FUNCTIONS + hidden visibility: export only the OCG_* API.
CORE_FLAGS="-std=c++17 -fno-rtti -I\"$SRC/lua/src\" -DOCGCORE_EXPORT_FUNCTIONS -fvisibility=hidden -Wno-unused-parameter"
core_cmds=()
for f in "${core_srcs[@]}"; do
  extra=""
  # Apple platforms require this file be built without exceptions (premake5.lua:19).
  if [ "$(basename "$f")" = "processor_visit.cpp" ] && [ "$(uname -s)" = "Darwin" ]; then
    extra="-fno-exceptions"
  fi
  o="$BUILD/core/$(basename "$f" .cpp).o"
  core_cmds+=("$CXX $COMMON $CORE_FLAGS $extra -c \"$f\" -o \"$o\"")
done
run_jobs "$JOBS" "${core_cmds[@]}"

# ---------------------------------------------------------------- link
log "linking libocgcore.dylib"
$CXX -dynamiclib -o "$OUT/libocgcore.dylib" \
  "$BUILD"/core/*.o "$BUILD"/lua/*.o \
  -install_name "@rpath/libocgcore.dylib"

# ---------------------------------------------------------------- provenance
git -C "$SRC" rev-parse HEAD > "$OUT/CORE_COMMIT"
git -C "$SRC/lua/src" rev-parse HEAD > "$OUT/LUA_COMMIT"

log "built $OUT/libocgcore.dylib"
ls -lh "$OUT/libocgcore.dylib"
echo "core: $(cat "$OUT/CORE_COMMIT")"
echo "lua:  $(cat "$OUT/LUA_COMMIT")"
