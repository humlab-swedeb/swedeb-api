#!/usr/bin/env bash
set -euo pipefail

CORPUS="${1:?Usage: $0 CORPUS [registry_dir] [runs] [parallel_jobs]}"
REGISTRY="${2:-${CORPUS_REGISTRY:-}}"
RUNS="${3:-5}"
JOBS="${4:-4}"

CQP_BIN="${CQP_BIN:-cqp}"
CWB_DESCRIBE="${CWB_DESCRIBE:-cwb-describe-corpus}"
CWB_LEXDECODE="${CWB_LEXDECODE:-cwb-lexdecode}"

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

cqp_args=()
[ -n "$REGISTRY" ] && cqp_args+=("-r" "$REGISTRY")

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing command: $1" >&2
    exit 1
  }
}

need "$CQP_BIN"
need "$CWB_DESCRIBE"
need "$CWB_LEXDECODE"

time_cmd() {
  local label="$1"; shift
  local out="$TMPDIR/out.$$"
  local err="$TMPDIR/err.$$"

  local t
  t=$(/usr/bin/time -f "%e" "$@" >"$out" 2>"$err" || {
    echo "FAIL,$label,NA"
    cat "$err" >&2
    return 0
  })

  echo "OK,$label,$t"
}

run_cqp() {
  local script="$1"
  "$CQP_BIN" "${cqp_args[@]}" -f "$script"
}

make_cqp_script() {
  local file="$1"
  shift
  {
    echo "${CORPUS};"
    echo "set PrettyPrint off;"
    echo "set ProgressBar off;"
    for q in "$@"; do
      echo "$q"
    done
  } > "$file"
}

echo "status,test,seconds"
echo "# corpus=$CORPUS registry=${REGISTRY:-default} runs=$RUNS parallel_jobs=$JOBS" >&2

# 1. Registry / metadata lookup
for i in $(seq 1 "$RUNS"); do
  time_cmd "describe_corpus_run_$i" "$CWB_DESCRIBE" ${REGISTRY:+-r "$REGISTRY"} "$CORPUS"
done

# 2. Lexicon scan: tests attribute lexicon access
for i in $(seq 1 "$RUNS"); do
  time_cmd "lexdecode_word_run_$i" "$CWB_LEXDECODE" ${REGISTRY:+-r "$REGISTRY"} "$CORPUS" -P word
done

# 3. CQP startup + corpus activation
for i in $(seq 1 "$RUNS"); do
  s="$TMPDIR/startup_$i.cqp"
  make_cqp_script "$s" "exit;"
  time_cmd "cqp_startup_run_$i" run_cqp "$s"
done

# 4. Simple exact-token query
for i in $(seq 1 "$RUNS"); do
  s="$TMPDIR/simple_$i.cqp"
  make_cqp_script "$s" \
    'A = [word = "the"];' \
    'size A;' \
    'cat A 0 5;' \
    'exit;'
  time_cmd "cqp_simple_word_query_run_$i" run_cqp "$s"
done

# 5. Case-insensitive / regex-style word query
for i in $(seq 1 "$RUNS"); do
  s="$TMPDIR/regex_$i.cqp"
  make_cqp_script "$s" \
    'A = [word = "(?i)the"];' \
    'size A;' \
    'cat A 0 5;' \
    'exit;'
  time_cmd "cqp_regex_word_query_run_$i" run_cqp "$s"
done

# 6. Positional context query
for i in $(seq 1 "$RUNS"); do
  s="$TMPDIR/context_$i.cqp"
  make_cqp_script "$s" \
    'A = [word = "of"] [word = "the"];' \
    'size A;' \
    'cat A 0 5;' \
    'exit;'
  time_cmd "cqp_bigram_query_run_$i" run_cqp "$s"
done

# 7. Frequency distribution over result set
for i in $(seq 1 "$RUNS"); do
  s="$TMPDIR/freq_$i.cqp"
  make_cqp_script "$s" \
    'A = [word = "the"] [];' \
    'group A matchend word;' \
    'exit;'
  time_cmd "cqp_frequency_run_$i" run_cqp "$s"
done

# 8. Parallel CQP load: approximates multi-user contention
parallel_script="$TMPDIR/parallel.cqp"
make_cqp_script "$parallel_script" \
  'A = [word = "the"];' \
  'size A;' \
  'cat A 0 10;' \
  'exit;'

for i in $(seq 1 "$RUNS"); do
  label="parallel_${JOBS}_cqp_users_run_$i"
  start="$(date +%s.%N)"

  pids=()
  for j in $(seq 1 "$JOBS"); do
    run_cqp "$parallel_script" >"$TMPDIR/par_${i}_${j}.out" 2>"$TMPDIR/par_${i}_${j}.err" &
    pids+=("$!")
  done

  failed=0
  for p in "${pids[@]}"; do
    wait "$p" || failed=1
  done

  end="$(date +%s.%N)"
  elapsed="$(awk -v s="$start" -v e="$end" 'BEGIN { printf "%.3f", e - s }')"

  if [ "$failed" -eq 0 ]; then
    echo "OK,$label,$elapsed"
  else
    echo "FAIL,$label,$elapsed"
  fi
done