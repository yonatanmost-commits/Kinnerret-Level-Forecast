#!/bin/bash
# Memory check for the cfc tournament, meant to run detached after cfc_tournament_night.sh.
# Waits for the tournament's "QUEUE DONE", summarises round 1 (A, A1, B14, B60) and
# round 2 (C60 against the round-1 winner), then asks of the overall winner W:
#   sweep      - retrain W with history L = 14, 30, 60, 120, 180 days
#   occlusion  - (B/C only) the same trained nets, with history older than k days blanked
# Outputs go to docs/experiments/cfc_tournament/memory/; every test year is saved, so a
# retry resumes. Most informative runs first: W's own L, then 120, 30, 180, the rest.
cd "$(dirname "$0")"
export PYTHONIOENCODING=utf-8
T="../docs/experiments/cfc_tournament"
LOG="$T/memory.log"
FILTER="rounds\]\|Bathy\|Coeff\|Mean of empty\|nanmean"
until grep -q "QUEUE DONE" "$T/night.log" 2>/dev/null; do
  grep -q "GAVE UP" "$T/night.log" 2>/dev/null && { echo "tournament gave up $(date)" >> "$LOG"; exit 1; }
  sleep 300
done
echo "##### memory check $(date)" >> "$LOG"
# The tournament's winner keeps the fixed rule (mean over all six horizons). The memory
# check studies the LONG-range best instead (mean of 130/260/365 d, clim weather),
# because the goal is long-term forecasts; when the two agree nothing differs.
long_best() {   # long_best <summary tag> -> label with the lowest long-range MAE
  python - "$T/summary_$1.json" <<'EOF'
import json, sys
mae = json.load(open(sys.argv[1]))["mae_m"]
long = {k.split("/")[0]: sum(v[h] for h in ("130", "260", "365")) / 3
        for k, v in mae.items() if k.endswith("/clim")}
print(min(long, key=long.get))
EOF
}
tag() { python -c "import sys;print('_'.join(sorted(set(sys.argv[1:]))))" "$@"; }
python -X utf8 cfc_tournament.py --summary --only A,A1,B14,B60 >> "$LOG" 2>&1
W1=$(python -c "import json;print(json.load(open('$T/summary_A_A1_B14_B60.json'))['winner_clim'].split('/')[0])")
WL1=$(long_best A_A1_B14_B60)
python -X utf8 cfc_tournament.py --summary --only "$W1,C60" >> "$LOG" 2>&1          # round 2, fixed rule
[ "$WL1" != "$W1" ] && python -X utf8 cfc_tournament.py --summary --only "$WL1,C60" >> "$LOG" 2>&1
W=$(long_best "$(tag "$WL1" C60)")
echo "=== round-1 winner (all horizons) $W1, round-1 long-range best $WL1, memory check on $W" >> "$LOG"
case "$W" in                                        # method and its history length
  A|A1) M=$W; L0=14 ;;
  *)    M=${W:0:1}; L0=${W:1} ;;
esac
export CFC_OUT="$T/memory"
mkdir -p "$CFC_OUT"
for attempt in 1 2 3 4 5 6; do
  echo "##### attempt $attempt  $(date)" >> "$LOG"
  ok=1
  for L in $L0 120 30 180 60 14; do
    if [ "$M" = "B" ] || [ "$M" = "C" ]; then
      KS=$(python -c "print(','.join(str(k) for k in (7,14,30,60,120) if k < $L))")
      ARGS="--method $M --enc-len $L --occlude $KS"
    else
      [ "$L" = "180" ] && continue                  # the relay at 180 days would not finish tonight
      ARGS="--method $M --enc-len $L"
    fi
    echo "=== $ARGS  $(date)" >> "$LOG"
    python -X utf8 cfc_tournament.py $ARGS --seeds 3 2>&1 | grep --line-buffered -v "$FILTER" >> "$LOG"
    [ "${PIPESTATUS[0]}" -ne 0 ] && { ok=0; echo "!!! $ARGS exited non-zero" >> "$LOG"; break; }
  done
  [ $ok -eq 1 ] && { echo "=== MEMORY DONE $(date)" >> "$LOG"; exit 0; }
  sleep 120
done
echo "=== MEMORY GAVE UP $(date)" >> "$LOG"
