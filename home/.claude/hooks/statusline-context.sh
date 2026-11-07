#!/usr/bin/env bash
# Claude Code statusLine: show model, dir, branch, and CONTEXT TOKENS USED.
# The captain's standing rule is to never let a session run past 300k tokens,
# so the token figure is the point of this line and is colored by proximity to
# that ceiling rather than to the model's own context window.
set -uo pipefail

input=$(cat)

json_get() { printf '%s' "$input" | python3 -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: print(''); raise SystemExit
cur=d
for k in sys.argv[1].split('.'):
    if isinstance(cur,dict) and k in cur: cur=cur[k]
    else: print(''); raise SystemExit
print(cur if cur is not None else '')
" "$1" 2>/dev/null; }

model=$(json_get model.display_name)
cwd=$(json_get workspace.current_dir)
transcript=$(json_get transcript_path)

[ -n "$model" ] || model="claude"
dir=$(basename "${cwd:-$PWD}")
branch=$(git -C "${cwd:-$PWD}" rev-parse --abbrev-ref HEAD 2>/dev/null)

# Context size is the last assistant turn's total footprint: fresh input plus
# both cache tiers plus output. Cumulative summing would double count, because
# every turn re-reads the same cached prefix.
tokens=0
if [ -n "$transcript" ] && [ -f "$transcript" ]; then
  tokens=$(python3 - "$transcript" <<'PY' 2>/dev/null || echo 0
import json,sys
total=0
try:
    with open(sys.argv[1],encoding='utf-8',errors='replace') as fh:
        for line in fh:
            line=line.strip()
            if not line: continue
            try: rec=json.loads(line)
            except Exception: continue
            u=(rec.get('message') or {}).get('usage') or rec.get('usage')
            if not isinstance(u,dict): continue
            t=(u.get('input_tokens') or 0)+(u.get('cache_read_input_tokens') or 0) \
              +(u.get('cache_creation_input_tokens') or 0)+(u.get('output_tokens') or 0)
            if t: total=t
except Exception: pass
print(total)
PY
)
fi
[ -n "$tokens" ] || tokens=0

limit=300000
pct=$(( tokens * 100 / limit ))
if   [ "$pct" -ge 90 ]; then col=$'\033[1;31m'; mark="!! COMPACT NOW"
elif [ "$pct" -ge 75 ]; then col=$'\033[1;33m'; mark="! plan handoff"
else                        col=$'\033[32m';   mark=""
fi
dim=$'\033[2m'; rst=$'\033[0m'

human=$(awk -v t="$tokens" 'BEGIN{ if (t>=1000) printf "%.1fk", t/1000; else printf "%d", t }')

printf '%s%s%s %s|%s %s' "$dim" "$model" "$rst" "$dim" "$rst" "$dir"
[ -n "$branch" ] && printf ' %s(%s)%s' "$dim" "$branch" "$rst"
printf ' %s|%s %sctx %s/300k (%s%%)%s' "$dim" "$rst" "$col" "$human" "$pct" "$rst"
[ -n "$mark" ] && printf ' %s%s%s' "$col" "$mark" "$rst"
printf '\n'
