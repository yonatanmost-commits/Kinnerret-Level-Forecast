#!/usr/bin/env bash
# Weekend runs, stage A (R1-R3 of docs/talk/update_5nov_plan.md), data day 6 Nov 2026.
# One step at a time (memory over time). Stops if R2a does not reproduce the 17 Oct backtest.
# Run from anywhere:  "C:\Program Files\Git\bin\bash.exe" docs/talk/weekend_runs.sh
# Re-runnable: finished model files are skipped by cfc_tournament (it skips years already in CFC_OUT).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd -W)"   # C:/... form: Windows Python can't open /c/... paths
cd "$ROOT"
export PYTHONIOENCODING=utf-8
D="$ROOT/docs/experiments/weekend_D"
LOG="$D/logs"; mkdir -p "$LOG"
step() { echo; echo "=== $(date +%H:%M:%S)  $*" | tee -a "$LOG/steps.log"; }

# R1 freeze the gold
step "R1 freeze gold"
if [ ! -f "$D/gold.csv" ]; then cp "Gold Data/kinneret_gold_features.csv" "$D/gold.csv"; fi
python -c "import pandas as pd;g=pd.read_csv(r'$D/gold.csv');print('rows',len(g),'last level day',g.dropna(subset=['level_m'])['date'].iloc[-1])" | tee -a "$LOG/steps.log"
GOLD_D="$D/gold.csv"

# R2a reproduce the 17 Oct backtest on the old gold (2016 only)
step "R2a reproduce 2016 on old gold"
if [ -f "$D/R2a_ok" ]; then echo "R2a already passed (see $D/R2a_ok), skipping" | tee -a "$LOG/steps.log"; else
git show b80580a:"Gold Data/kinneret_gold_features.csv" > "$D/gold_old.csv"
mkdir -p "$D/repro"
( cd Automation && CFC_GOLD="$D/gold_old.csv" CFC_HORIZONS=monthly CFC_YEARS=2016 CFC_OUT="$D/repro" \
  python cfc_tournament.py --table ims --method B --enc-len 14 --cell gru --ensemble --seas5 --seeds 3 ) \
  > "$LOG/R2a.log" 2>&1
python - "$D/repro/B14gru_s3_ens.json" docs/experiments/cfc_monthly/B14gru_s3_ens.json <<'EOF' | tee -a "$LOG/steps.log"
import json, sys, collections
def mae(p):
    rows = json.load(open(p))["2016"]; acc = collections.defaultdict(list)
    for r in rows:
        if r["weather"] in ("obs", "clim", "seas5", "seas5c", "seas5s"):
            acc[(r["weather"], r["H"])].append(abs(r["pred"] - r["obs"]) * 100)
    return {k: sum(v) / len(v) for k, v in acc.items()}
new, old = mae(sys.argv[1]), mae(sys.argv[2])
missing = sorted(set(old) - set(new))
# Gate on week + month only: two identical runs differ up to ~14 cm in one year's 3-12 month cells (measured 6 Nov).
worst = max(abs(new[k] - old[k]) for k in old if k in new and k[1] <= 30)
for w in ("obs", "seas5"):
    print(w, " ".join(f"H{h}:{old[(w,h)]:.1f}->{new[(w,h)]:.1f}" for h in (7, 30, 182, 365) if (w, h) in old))
print(f"R2a worst |MAE diff| at week/month {worst:.2f} cm, missing cells {len(missing)}")
sys.exit(0 if worst <= 1.0 and not missing else 3)
EOF
echo "R2a OK: the command reproduces the 17 Oct backtest" | tee -a "$LOG/steps.log"; touch "$D/R2a_ok"; fi

# R2 backtest 2011-2025 on the frozen gold, one model at a time
YEARS=2011,2012,2013,2014,2015,2016,2017,2018,2019,2020,2021,2022,2023,2024,2025
OUT="$ROOT/docs/experiments/cfc_monthly_D"; mkdir -p "$OUT"
run() { local name=$1; shift
  step "R2 $name"
  ( cd Automation && CFC_GOLD="$GOLD_D" CFC_HORIZONS=monthly CFC_YEARS=$YEARS CFC_OUT="$OUT" python cfc_tournament.py "$@" ) \
    > "$LOG/R2_$name.log" 2>&1
}
run gru --table ims --method B --enc-len 14 --cell gru --ensemble --seas5 --seeds 3
run gbr --table ims --method G --seas5 --seeds 3
run cfc --table ims --method B --enc-len 14 --cell cfc --ensemble --seas5 --seeds 3
ls -la "$OUT" | tee -a "$LOG/steps.log"

# R3 fan evaluation + track record (old outputs backed up first)
step "R3 fan eval + track record"
[ -d docs/experiments/cfc_fan_eval_1017 ] || cp -r docs/experiments/cfc_fan_eval docs/experiments/cfc_fan_eval_1017
CFC_GOLD="$GOLD_D" python Automation/cfc_fan_eval.py "$OUT" --out docs/experiments/cfc_fan_eval/fan_monthly.json > "$LOG/R3_fan_eval.log" 2>&1
python Automation/cfc_track_record.py > "$LOG/R3_track.log" 2>&1
step "STAGE A DONE. Tell Claude: 'stage A done'."
