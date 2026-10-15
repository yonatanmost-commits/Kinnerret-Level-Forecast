#!/bin/bash
# Night queue for cfc_tournament.py, meant to run detached from any Claude session.
# Every run skips test years already saved, so a retry resumes where it stopped.
# Retries the whole queue up to 8 times; finished methods cost seconds to skip.
cd "$(dirname "$0")"
export PYTHONIOENCODING=utf-8
LOG="../docs/experiments/cfc_tournament/night.log"
mkdir -p "$(dirname "$LOG")"
for attempt in 1 2 3 4 5 6 7 8; do
  echo "##### attempt $attempt  $(date)" >> "$LOG"
  ok=1
  for m in "A" "A1" "B --enc-len 14" "B --enc-len 60" "C --enc-len 60"; do
    echo "=== $m  $(date)" >> "$LOG"
    python -X utf8 cfc_tournament.py --method $m --seeds 3 2>&1 \
      | grep --line-buffered -v "rounds\]\|Bathy\|Coeff\|Mean of empty\|nanmean" >> "$LOG"
    [ "${PIPESTATUS[0]}" -ne 0 ] && { ok=0; echo "!!! $m exited non-zero" >> "$LOG"; break; }
  done
  if [ $ok -eq 1 ]; then
    python -X utf8 cfc_tournament.py --summary >> "$LOG" 2>&1
    echo "=== QUEUE DONE $(date)" >> "$LOG"
    exit 0
  fi
  sleep 120
done
echo "=== GAVE UP after 8 attempts $(date)" >> "$LOG"
