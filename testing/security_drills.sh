#!/usr/bin/env bash
# NFT-09 and NFT-10 security drills against the running backend (default :8000).
# Uses the seeded demo accounts. Writes testing/results/security_drills.txt.
set -u
API=${API:-http://localhost:8000/api}
OUT=testing/results/security_drills.txt
TMP=$(mktemp -d)
pass=0; fail=0

check() { # name expected actual
  if [ "$2" = "$3" ]; then echo "PASS  $1 (got $3)"; pass=$((pass+1)); else echo "FAIL  $1 (expected $2, got $3)"; fail=$((fail+1)); fi
}

login() { # email password jar headers
  curl -s -o "$TMP/$3.body" -D "$4" -c "$TMP/$3" -H 'Content-Type: application/json' \
    -d "{\"email\":\"$1\",\"password\":\"$2\"}" "$API/login" -w '%{http_code}'
}

{
  echo "Security drills, $(date '+%Y-%m-%d %H:%M:%S %Z'), API $API"
  echo
  echo "NFT-09 role enforcement"
  check "analyst login" 200 "$(login analyst@orbitalsentinel.test sentinel123 analyst "$TMP/analyst.h")"
  check "evaluator login" 200 "$(login evaluator@orbitalsentinel.test evaluator123 evaluator "$TMP/evaluator.h")"
  check "admin login" 200 "$(login admin@orbitalsentinel.test admin123 admin "$TMP/admin.h")"
  start='{"satelliteId":"SAT-003"}'
  check "no cookie: POST /sessions" 401 "$(curl -s -o /dev/null -w '%{http_code}' -H 'Content-Type: application/json' -d "$start" "$API/sessions")"
  check "analyst: POST /sessions" 403 "$(curl -s -o /dev/null -w '%{http_code}' -b "$TMP/analyst" -H 'Content-Type: application/json' -d "$start" "$API/sessions")"
  check "evaluator: POST /sessions" 403 "$(curl -s -o /dev/null -w '%{http_code}' -b "$TMP/evaluator" -H 'Content-Type: application/json' -d "$start" "$API/sessions")"
  check "analyst: GET /sessions" 403 "$(curl -s -o /dev/null -w '%{http_code}' -b "$TMP/analyst" "$API/sessions")"
  check "forged cookie: GET /alerts" 401 "$(curl -s -o /dev/null -w '%{http_code}' -H 'Cookie: os_session=forged.value' "$API/alerts")"
  check "wrong password" 401 "$(curl -s -o /dev/null -w '%{http_code}' -H 'Content-Type: application/json' -d '{"email":"admin@orbitalsentinel.test","password":"wrong"}' "$API/login")"
  echo
  echo "NFT-10 session cookie and secrets"
  cookie=$(grep -i '^set-cookie' "$TMP/admin.h" | tr -d '\r')
  echo "      Set-Cookie: $(echo "$cookie" | sed -E 's/=[^;]+;/=<redacted>;/')"
  check "cookie is HttpOnly" yes "$(echo "$cookie" | grep -qi httponly && echo yes || echo no)"
  check "cookie is SameSite=Lax" yes "$(echo "$cookie" | grep -qi 'samesite=lax' && echo yes || echo no)"
  for path in me alerts satellites ranking sessions; do
    curl -s -b "$TMP/admin" "$API/$path" > "$TMP/$path.json"
  done
  cat "$TMP"/*.body "$TMP"/*.json > "$TMP/all.txt"
  check "no argon2 hash in login, me, alerts, satellites, ranking, sessions" 0 "$(grep -c '\$argon2' "$TMP/all.txt")"
  check "no password field in those responses" 0 "$(grep -ci 'password' "$TMP/all.txt")"
  echo
  echo "Passed $pass, failed $fail"
} | tee "$OUT"
rm -rf "$TMP"
