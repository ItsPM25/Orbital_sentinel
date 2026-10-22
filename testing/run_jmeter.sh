#!/usr/bin/env bash
# Runs the non-functional test scenarios (NFT-01..05) headless and writes an HTML
# dashboard per scenario under testing/results/<name>/. Needs the production build
# on :3001 and the API on :8000. Usage: bash testing/run_jmeter.sh [scenario...]
set -u
cd "$(dirname "$0")"
JMETER=${JMETER:-/c/jmeter/apache-jmeter-5.6.3/bin/jmeter.bat}
OUT=results
mkdir -p "$OUT"

run() {
  local name=$1; shift
  rm -rf "$OUT/$name" "$OUT/$name.jtl"
  curl -s http://localhost:3001/api/reset > /dev/null
  echo "== $name start $(date '+%Y-%m-%d %H:%M:%S') args: $*"
  "$JMETER" -n -t OrbitalSentinel.jmx "$@" -l "$OUT/$name.jtl" -e -o "$OUT/$name" > "$OUT/$name.log" 2>&1
  echo "== $name end   $(date '+%Y-%m-%d %H:%M:%S') exit $?"
  grep -E "summary =" "$OUT/$name.log" | tail -1
}

# Backend memory (MB) every 30 s while the soak runs.
watch_memory() {
  local pid
  pid=$(netstat -ano | grep -E "127.0.0.1:8000 .*LISTENING" | awk '{print $NF}' | head -1)
  while [ -f "$OUT/.soak_running" ]; do
    echo "$(date '+%H:%M:%S') $(powershell -NoProfile -Command "[math]::Round((Get-Process -Id $pid).WorkingSet64/1MB,1)")" >> "$OUT/soak_memory.txt"
    sleep 30
  done
}

scenarios=${*:-"load readonly stress100 stress200 spike soak"}
for s in $scenarios; do
  case $s in
    load)      run load      -Jusers=50  -Jrampup=10 -Jloops=10 ;;
    readonly)  run readonly  -Jusers=0   -Jro_users=50 -Jrampup=10 -Jro_loops=20 ;;
    stress100) run stress100 -Jusers=100 -Jrampup=30 -Jloops=5 ;;
    stress200) run stress200 -Jusers=200 -Jrampup=30 -Jloops=3 ;;
    spike)     run spike     -Jusers=200 -Jrampup=1  -Jloops=1 ;;
    soak)
      : > "$OUT/soak_memory.txt"; touch "$OUT/.soak_running"
      watch_memory &
      run soak -Jusers=0 -Jro_users=20 -Jrampup=10 -Jro_loops=-1 -Jro_duration=600
      rm -f "$OUT/.soak_running"; wait ;;
  esac
done
curl -s http://localhost:3001/api/reset > /dev/null
echo "all done $(date '+%Y-%m-%d %H:%M:%S')"
