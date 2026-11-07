#!/usr/bin/env bash
# Stage B again (R4-R7 of docs/talk/update_5nov_plan.md) on the FIXED gold (weekend_F, 8 Nov 2026).
# Same start as the 6 Nov fan (L = 2026-11-05, the frozen gold's last level day), so the change
# on the slides is the data fix alone. Everything replaced is kept under a _1106 name.
# Run:  "C:\Program Files\Git\bin\bash.exe" docs/talk/rerun_fixed_gold_b.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd -W)"
cd "$ROOT"
export PYTHONIOENCODING=utf-8
D="$ROOT/docs/experiments/weekend_F"; LOG="$D/logs"; GOLD_D="$D/gold.csv"
E=docs/experiments
L=2026-11-05
step() { echo; echo "=== $(date +%H:%M:%S)  $*" | tee -a "$LOG/steps.log"; }

step "R4 swap the fixed backtest in (6 Nov one kept as cfc_monthly_1106)"
if [ -d $E/cfc_monthly_F ]; then
  [ -d $E/cfc_monthly_1106 ] && { echo "cfc_monthly_1106 exists already, stopping"; exit 3; }
  mv $E/cfc_monthly $E/cfc_monthly_1106 && mv $E/cfc_monthly_F $E/cfc_monthly
fi
ls $E/cfc_monthly | tee -a "$LOG/steps.log"

step "R5 today's fan from $L"
rm -rf "$D/today"; mkdir -p "$D/today"
( cd Automation && CFC_GOLD="$GOLD_D" CFC_HORIZONS=monthly CFC_FUTURE=1 CFC_YEARS=2026 CFC_OUT="$D/today" CFC_ANCHOR=$L \
  python cfc_tournament.py --table ims --method B --enc-len 14 --cell gru --ensemble --seeds 3 ) > "$LOG/R5.log" 2>&1
[ -d $E/cfc_today_monthly_1106 ] || cp -r $E/cfc_today_monthly $E/cfc_today_monthly_1106
cp "$D/today/B14gru_s3_ens.json" "$D/today/references.json" $E/cfc_today_monthly/
cp Models/longrange_fan.json "$D/longrange_fan_1106.json"
( cd Automation && python fan_today.py ) > "$LOG/R5_fan_today.log" 2>&1
python -c "import json;d=json.load(open('Models/longrange_fan.json'));print({k:d[k] for k in ('made_on','start','level0')})" | tee -a "$LOG/steps.log"

step "R6 slide-11 data (6 Nov copies kept in weekend_F/slide11_1106)"
mkdir -p "$D/slide11_1106"; cp docs/talk/data/slide11_* "$D/slide11_1106/"
python docs/talk/data/slide11_fan_build.py > "$LOG/R6.log" 2>&1
python -c "import csv;r=[x for x in csv.DictReader(open('docs/talk/data/slide11_fan.csv')) if x['H']=='365'][0];print('365 d median',r['median'],'p_red',r['p_red'],'80%',r['lo_80'],r['hi_80'])" | tee -a "$LOG/steps.log"

step "R7 slide-1 talk-day forecast (week model retrained on the fixed gold, 6ff8008)"
cp docs/talk/data/slide1_week_forecast.json "$D/slide1_week_forecast_1106.json"
python docs/talk/data/slide1_week_forecast.py > "$LOG/R7.log" 2>&1
tail -3 "$LOG/R7.log" | tee -a "$LOG/steps.log"
step "STAGE B DONE"
