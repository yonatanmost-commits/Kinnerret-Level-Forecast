#!/usr/bin/env bash
# Weekend runs, stage B (R4-R7 of docs/talk/update_5nov_plan.md), data day 6 Nov 2026 (gold to 5 Nov).
# One step at a time. Run:  "C:\Program Files\Git\bin\bash.exe" docs/talk/weekend_runs_b.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd -W)"   # C:/... form: Windows Python can't open /c/... paths
cd "$ROOT"
export PYTHONIOENCODING=utf-8
D="$ROOT/docs/experiments/weekend_D"; LOG="$D/logs"; GOLD_D="$D/gold.csv"
E=docs/experiments
L=2026-11-05                                   # last measured level day in the frozen gold
step() { echo; echo "=== $(date +%H:%M:%S)  $*" | tee -a "$LOG/steps.log"; }

step "R4 swap the backtest in"
if [ -d $E/cfc_monthly_D ]; then
  [ -d $E/cfc_monthly_1017 ] && { echo "cfc_monthly_1017 exists already, stopping"; exit 3; }
  mv $E/cfc_monthly $E/cfc_monthly_1017 && mv $E/cfc_monthly_D $E/cfc_monthly
fi
ls $E/cfc_monthly | tee -a "$LOG/steps.log"

step "R5 today's fan from $L"
rm -rf "$D/today"; mkdir -p "$D/today"
( cd Automation && CFC_GOLD="$GOLD_D" CFC_HORIZONS=monthly CFC_FUTURE=1 CFC_YEARS=2026 CFC_OUT="$D/today" CFC_ANCHOR=$L \
  python cfc_tournament.py --table ims --method B --enc-len 14 --cell gru --ensemble --seeds 3 ) > "$LOG/R5.log" 2>&1
[ -d $E/cfc_today_monthly_1105 ] || cp -r $E/cfc_today_monthly $E/cfc_today_monthly_1105
cp "$D/today/B14gru_s3_ens.json" "$D/today/references.json" $E/cfc_today_monthly/
( cd Automation && python fan_today.py ) > "$LOG/R5_fan_today.log" 2>&1
python -c "import json;d=json.load(open('Models/longrange_fan.json'));print({k:d[k] for k in ('made_on','start','level0')})" | tee -a "$LOG/steps.log"

step "R6 slide-10 data"
python docs/talk/data/slide11_fan_build.py > "$LOG/R6.log" 2>&1
python -c "import csv;r=[x for x in csv.DictReader(open('docs/talk/data/slide11_fan.csv')) if x['H']=='365'][0];print('365 d median',r['median'],'p_red',r['p_red'],'80%',r['lo_80'],r['hi_80'])" | tee -a "$LOG/steps.log"

step "R7 slide-1 talk-day forecast"
python docs/talk/data/slide1_week_forecast.py --dry > "$LOG/R7_dry.log" 2>&1
python docs/talk/data/slide1_week_forecast.py > "$LOG/R7.log" 2>&1
tail -5 "$LOG/R7.log" | tee -a "$LOG/steps.log"
step "STAGE B DONE. Tell Claude: 'stage B done'."
