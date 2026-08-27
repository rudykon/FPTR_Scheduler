#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "${script_dir}/wasm"

em++ \
  -std=c++17 \
  -O3 \
  -fexceptions \
  --no-entry \
  "${script_dir}/src/core.cpp" \
  "${script_dir}/src/wasm_api.cpp" \
  -o "${script_dir}/wasm/fptr_solver.js" \
  -sMODULARIZE=1 \
  -sEXPORT_NAME=createFPTRModule \
  -sENVIRONMENT=web,node \
  -sALLOW_MEMORY_GROWTH=1 \
  -sFILESYSTEM=0 \
  -sASSERTIONS=0 \
  -sEXPORTED_FUNCTIONS='["_fptr_run","_malloc","_free"]' \
  -sEXPORTED_RUNTIME_METHODS='["ccall"]'

test -s "${script_dir}/wasm/fptr_solver.js"
test -s "${script_dir}/wasm/fptr_solver.wasm"
echo "Built ${script_dir}/wasm/fptr_solver.js and fptr_solver.wasm"
