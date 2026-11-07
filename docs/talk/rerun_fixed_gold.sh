#!/usr/bin/env bash
# Stage A again (R1-R3 of docs/talk/update_5nov_plan.md) on the FIXED gold of 7 Nov 2026.
# The 6 Nov runs (weekend_runs.sh) read a gold with pre-2012 partial days in it (coverage cache
# clobbered by the 18 Oct refresh; fixed in 48cd9b5). Same commands; new folders, so the 6 Nov
# results stay for comparison: weekend_F/ (gold + logs), cfc_monthly_F/ (backtest).
# Run:  "C:\Program Files\Git\bin\bash.exe" docs/talk/rerun_fixed_gold.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd -W)"
cd "$ROOT"
export PYTHONIOENCODING=utf-8
D="$ROOT/docs/experiments/weekend_F"; LOG="$D/logs"; mkdir -p "$LOG"
step() { echo; echo "=== $(date +%H:%M:%S)  $*" | tee -a "$LOG/steps.log"; }

step "R1 freeze the fixed gold"
[ -f "$D/gold.csv" ] || cp "Gold Data/kinneret_gold_features.csv" "$D/gold.csv"
python -c "import pandas as pd;g=pd.read_csv(r'$D/gold.csv',index_col='date');print('rows',len(g),'last level day',g['level_m'].last_valid_index(),'| 2009-04-11 temp_max',g.loc['2009-04-11','temp_max_C'])" | tee -a "$LOG/steps.log"
GOLD_D="$D/gold.csv"

YEARS=2011,2012,2013,2014,2015,2016,2017,2018,2019,2020,2021,2022,2023,2024,2025
OUT="$ROOT/docs/experiments/cfc_monthly_F"; mkdir -p "$OUT"
run() { local name=$1; shift
  step "R2 $name"
  ( cd Automation && CFC_GOLD="$GOLD_D" CFC_HORIZONS=monthly CFC_YEARS=$YEARS CFC_OUT="$OUT" python cfc_tournament.py "$@" ) \
    > "$LOG/R2_$name.log" 2>&1
}
run gru --table ims --method B --enc-len 14 --cell gru --ensemble --seas5 --seeds 3
run gbr --table ims --method G --seas5 --seeds 3
run cfc --table ims --method B --enc-len 14 --cell cfc --ensemble --seas5 --seeds 3
ls -la "$OUT" | tee -a "$LOG/steps.log"

step "R3 fan eval + track record (6 Nov outputs backed up to cfc_fan_eval_1106)"
[ -d docs/experiments/cfc_fan_eval_1106 ] || cp -r docs/experiments/cfc_fan_eval docs/experiments/cfc_fan_eval_1106
CFC_GOLD="$GOLD_D" python Automation/cfc_fan_eval.py "$OUT" --out docs/experiments/cfc_fan_eval/fan_monthly.json > "$LOG/R3_fan_eval.log" 2>&1
python Automation/cfc_track_record.py > "$LOG/R3_track.log" 2>&1
step "STAGE A DONE"
