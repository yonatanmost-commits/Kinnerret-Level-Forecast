#!/bin/bash
# Memory check for the cfc tournament, meant to run detached after cfc_tournament_night.sh.
# Waits for the tournament's "QUEUE DONE", summarises round 1 (A, A1, B14, B60) and
# round 2 (C60 against the round-1 winner), then asks of the overall winner W:
#   sweep      - retrain W with history L = 14, 30, 60, 120, 180 days
#   occlusion  - (B/C only) the same trained nets, with history older than k days blanked
# Outputs go to docs/experiments/cfc_tournament/memory/; every test year is saved, so a
# retry resumes. Most informative runs first: W's own L, then 120, 30, 60; then C trained
# like B on four years (round 2's handicap check); B14 on IMS with the past-winters
# ensemble, without and with the soil bucket; 180 (the slowest) last.
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
IMS="../docs/experiments/cfc_ims"
mkdir -p "$CFC_OUT"
run() {   # run <cfc_tournament args>; CFC_OUT / CFC_YEARS come from the environment
  echo "=== $*  $(date)" >> "$LOG"
  python -X utf8 cfc_tournament.py "$@" --seeds 3 2>&1 | grep --line-buffered -v "$FILTER" >> "$LOG"
  local rc=${PIPESTATUS[0]}
  [ "$rc" -ne 0 ] && echo "!!! $* exited non-zero" >> "$LOG"
  return "$rc"
}
sweep() { # sweep <L>: W retrained with L days of history (+ occlusion for B/C)
  if [ "$M" = "B" ] || [ "$M" = "C" ]; then
    run --method "$M" --enc-len "$1" --occlude "$(python -c "print(','.join(str(k) for k in (7,14,30,60,120) if k < $1))")"
  else
    [ "$1" = "180" ] && return 0                     # the relay at 180 days would not finish tonight
    run --method "$M" --enc-len "$1"
  fi
}
for attempt in 1 2 3 4 5 6; do
  echo "##### attempt $attempt  $(date)" >> "$LOG"
  # C trained like B on four spread years, next to round 2: was C's loss its every-other-day,
  # shorter training? Then B14 on the IMS table (2021-2025) with the past-winters ensemble,
  # without and with the soil bucket. All before L=180, the slowest and least informative run.
  if sweep "$L0" && sweep 120 && sweep 30 && sweep 60 &&
     CFC_OUT="$T" CFC_YEARS=2012,2016,2019,2023 run --method C --enc-len 60 --c-full &&
     CFC_OUT="$IMS" run --method B --enc-len 14 --table ims --ensemble &&
     CFC_OUT="$IMS" run --method B --enc-len 14 --table ims --ensemble --bucket &&
     sweep 180; then
    echo "=== MEMORY DONE $(date)" >> "$LOG"; exit 0
  fi
  sleep 120
done
echo "=== MEMORY GAVE UP $(date)" >> "$LOG"
