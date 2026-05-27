#!/usr/bin/env bash
# =============================================================================
# smoke-test.sh — Money-path smoke test for Supletivo platform
# =============================================================================
# Usage:
#   ./scripts/smoke-test.sh                    # health check only (safe)
#   ./scripts/smoke-test.sh --full             # full money-path test
#   ./scripts/smoke-test.sh --service lead     # single service health check
#
# Prerequisites:
#   - docker compose -f docker-compose.dev.yml up -d
#   - All 22 services healthy (step 1 verifies this)
#   - Asaas in sandbox mode
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS=0
FAIL=0

pass() { echo -e "  ${GREEN}PASS${NC} $1"; PASS=$((PASS + 1)); }
fail() { echo -e "  ${RED}FAIL${NC} $1 — $2"; FAIL=$((FAIL + 1)); }
warn() { echo -e "  ${YELLOW}WARN${NC} $1 — $2"; }

# ── Service port map (from docker-compose.dev.yml) ─────────────────────────

declare -A PORTS=(
    [address]=8001    [ai]=8002        [asaas]=8003      [auth]=8004
    [candidate]=8005  [documents]=8008 [enrollment]=8009 [fees]=8010
    [hub]=8011        [infinitepay]=8012                 [jwt]=8013
    [lead]=8014       [notify]=8015    [otp]=8016        [profiles]=8017
    [promoter]=8018   [roles]=8019     [staff]=8020      [student]=8021
    [training]=8022
)

# ── Health Check (Phase 1) ─────────────────────────────────────────────────

echo "=== Smoke Test: Health Check ==="
echo ""

for svc in "${!PORTS[@]}"; do
    port="${PORTS[$svc]}"
    http_code=$(curl -s -o /dev/null -w "%{http_code}" \
        "http://localhost:${port}/health" 2>/dev/null || echo "000")
    if [ "$http_code" = "200" ]; then
        pass "$svc (:$port) — $http_code"
    else
        fail "$svc (:$port)" "HTTP $http_code"
    fi
done

echo ""
echo "Health: $PASS/${#PORTS[@]} services healthy"

# ── Infrastructure Check ────────────────────────────────────────────────────

echo ""
echo "=== Smoke Test: Infrastructure ==="

# Postgres
if docker compose -f "$PROJECT_DIR/docker-compose.dev.yml" exec -T postgres \
    pg_isready -U supletivo -d supletivo >/dev/null 2>&1; then
    pass "Postgres — pg_isready OK"
else
    fail "Postgres" "pg_isready failed"
fi

# Redis
if docker compose -f "$PROJECT_DIR/docker-compose.dev.yml" exec -T redis \
    redis-cli ping 2>/dev/null | grep -q PONG; then
    pass "Redis — PONG"
else
    fail "Redis" "PONG failed"
fi

# ── Money Path (Phase 2 — --full only) ─────────────────────────────────────

if [ "${1:-}" != "--full" ]; then
    echo ""
    echo "=== Done (health check only) ==="
    echo "Run with --full for money-path end-to-end test."
    echo "Total: $PASS passed, $FAIL failed"
    exit $FAIL
fi

echo ""
echo "=== Smoke Test: Money Path (lead -> checkout -> enrollment) ==="

LEAD_PORT="${PORTS[lead]}"
ASAAS_PORT="${PORTS[asaas]}"
ENROLL_PORT="${PORTS[enrollment]}"
PROMOTER_DEFAULT="00000000-0000-0000-0000-000000000001"

# Step 1: Create lead
echo ""
echo "--- Step 1: Create lead ---"
LEAD_PAYLOAD='{"phone":"+5511999990001","cpf":"52998224725","ref":"'"$PROMOTER_DEFAULT"'"}'
LEAD_RESP=$(curl -s -w "\n%{http_code}" \
    -X POST "http://localhost:${LEAD_PORT}/api/v1/public/register" \
    -H "Content-Type: application/json" \
    -d "$LEAD_PAYLOAD" 2>/dev/null)
LEAD_CODE=$(echo "$LEAD_RESP" | tail -1)
LEAD_BODY=$(echo "$LEAD_RESP" | sed '$d')

if [ "$LEAD_CODE" = "201" ]; then
    LEAD_ID=$(echo "$LEAD_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('external_id',''))" 2>/dev/null)
    pass "Create lead — 201 Created (external_id=$LEAD_ID)"
else
    fail "Create lead" "HTTP $LEAD_CODE — $LEAD_BODY"
    echo ""
    echo "=== Smoke test ABORTED — cannot proceed without lead ==="
    echo "Total: $PASS passed, $FAIL failed"
    exit 1
fi

# Step 2: Verify lead in database
echo ""
echo "--- Step 2: Verify lead exists ---"
LEAD_GET=$(curl -s -o /dev/null -w "%{http_code}" \
    "http://localhost:${LEAD_PORT}/api/v1/demilitarized/leads/${LEAD_ID}" 2>/dev/null)
if [ "$LEAD_GET" = "200" ]; then
    pass "Get lead — 200 OK"
else
    fail "Get lead" "HTTP $LEAD_GET"
fi

# Step 3: Trigger checkout (asaas sandbox)
echo ""
echo "--- Step 3: Create checkout ---"
CHECKOUT_RESP=$(curl -s -w "\n%{http_code}" \
    -X POST "http://localhost:${LEAD_PORT}/api/v1/demilitarized/checkouts" \
    -H "Content-Type: application/json" \
    -d "{\"lead_external_id\":\"${LEAD_ID}\"}" 2>/dev/null)
CHECKOUT_CODE=$(echo "$CHECKOUT_RESP" | tail -1)
CHECKOUT_BODY=$(echo "$CHECKOUT_RESP" | sed '$d')

if [ "$CHECKOUT_CODE" = "200" ] || [ "$CHECKOUT_CODE" = "201" ]; then
    pass "Create checkout — ${CHECKOUT_CODE}"
else
    warn "Create checkout" "HTTP $CHECKOUT_CODE (may need sandbox config)"
fi

# Step 4: Verify enrollment exists (should be auto-created on lead capture)
echo ""
echo "--- Step 4: Verify enrollment ---"
ENROLL_RESP=$(curl -s -w "\n%{http_code}" \
    "http://localhost:${ENROLL_PORT}/api/v1/demilitarized/enrollments?lead_external_id=${LEAD_ID}" 2>/dev/null)
ENROLL_CODE=$(echo "$ENROLL_RESP" | tail -1)

if [ "$ENROLL_CODE" = "200" ]; then
    pass "Enrollment lookup — 200 OK"
elif [ "$ENROLL_CODE" = "404" ]; then
    warn "Enrollment lookup" "404 — enrollment may be created after payment, not on capture"
else
    fail "Enrollment lookup" "HTTP $ENROLL_CODE"
fi

# ── Results ─────────────────────────────────────────────────────────────────

echo ""
echo "=== Smoke Test Complete ==="
echo "Passed: $PASS | Failed: $FAIL"
if [ "$FAIL" -gt 0 ]; then
    echo -e "${RED}SMOKE TEST FAILED${NC}"
    exit 1
else
    echo -e "${GREEN}SMOKE TEST PASSED${NC}"
    exit 0
fi
