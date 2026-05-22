#!/usr/bin/env bash
# ==============================================================================
# VecminDB LTSM End-to-End Demo — curl only, zero Python dependency
# Usage: VECMIN_URL=http://localhost:5520 bash examples/demo_ltsm_lifecycle.sh
# ==============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
pass=0; fail=0
check() { local desc="$1"; shift; printf "  %-55s " "$desc..."; if "$@" > /dev/null 2>&1; then echo -e "${GREEN}PASS${NC}"; ((pass++)); else echo -e "${RED}FAIL${NC}"; ((fail++)); fi; }

BASE="${VECMIN_URL:-http://localhost:5520}"

echo -e "${BOLD}VecminDB LTSM Lifecycle Demo${NC}"
echo "Server: $BASE"
echo ""

# ── 1. Health ───────────────────────────────────────────────────────────────
echo -e "${CYAN}[1] Health Check${NC}"
check "Liveness probe"      curl -sf --max-time 3 "$BASE/healthz/live"

# ── 2. License ──────────────────────────────────────────────────────────────
echo -e "${CYAN}[2] License Status${NC}"
LICENSE=$(curl -sf --max-time 3 "$BASE/license/status")
check "License returns valid JSON"  echo "$LICENSE" | grep -q '"state"'
check "License is trial or active"  echo "$LICENSE" | grep -qE '"trial"|"active"'
check "max_agents field present"    echo "$LICENSE" | grep -q 'max_agents'

# ── 3. Store Memories via MCP ───────────────────────────────────────────────
echo -e "${CYAN}[3] Store Episodic Memories${NC}"

mcp_store() {
    curl -sf --max-time 15 -X POST "$BASE/api/v1/mcp/message" \
        -H "Content-Type: application/json" \
        -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"store_memory\",\"arguments\":{\"text\":\"$1\",\"agent_id\":\"$2\",\"sovereignty_token\":\"$2\"}}}"
}

R1=$(mcp_store "Enterprise customer refund policy: 30 days full refund; after 30 days store credit only" "billing_agent_1")
R2=$(mcp_store "Subscription renewals auto-process on 1st of each month; send reminder 3 days before" "billing_agent_1")
R3=$(mcp_store "Enterprise tier pricing: \$999/mo for up to 500 agents; annual contract required" "billing_agent_1")
R4=$(mcp_store "Escalation path: tier-1 → tier-2 → engineering; SLA is 2 hours for P1 issues" "support_agent_1")
R5=$(mcp_store "Common issue: login fails when user has both personal and enterprise accounts linked" "support_agent_1")

check "Store 3 billing memories"   echo "$R1$R2$R3" | grep -q "anchored\|result"
check "Store 2 support memories"   echo "$R4$R5" | grep -q "anchored\|result"

# ── 4. Search via MCP ───────────────────────────────────────────────────────
echo -e "${CYAN}[4] Search Semantically${NC}"

mcp_search() {
    curl -sf --max-time 15 -X POST "$BASE/api/v1/mcp/message" \
        -H "Content-Type: application/json" \
        -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"search_memory\",\"arguments\":{\"query\":\"$1\",\"agent_id\":\"$2\",\"sovereignty_token\":\"$2\",\"top_k\":3}}}"
}

S1=$(mcp_search "refund policy" "billing_agent_1")
S2=$(mcp_search "login password issue" "support_agent_1")

check "Search returns results (billing)"   echo "$S1" | grep -q "result"
check "Search returns results (support)"   echo "$S2" | grep -q "result"

# ── 5. Promotion ────────────────────────────────────────────────────────────
echo -e "${CYAN}[5] LTSM Promotion (Fast-Path + Decide)${NC}"

PENDING=$(curl -sf --max-time 3 "$BASE/agents/billing_agent_1/promotion/pending")
check "Pending pool API accessible"  echo "$PENDING" | grep -q "candidates"

# Trigger slow-path decide on each pending candidate
CIDS=$(echo "$PENDING" | grep -o '"id":"[^"]*"' | head -5 | sed 's/"id":"//g;s/"//g')
for cid in $CIDS; do
    DECISION=$(curl -sf --max-time 3 -X POST "$BASE/agents/billing_agent_1/promotion/decide" \
        -H "Content-Type: application/json" \
        -d "{\"candidate_id\":\"$cid\"}")
    echo "    Candidate $(echo $cid | cut -c1-20)... → $(echo $DECISION | grep -o '"decision":"[^"]*"' | sed 's/"decision":"//g;s/"//g')"
done

check "Decide API responds"  echo "${DECISION:-}" | grep -q "decision"

# Promotion thresholds
THRESHOLDS=$(curl -sf --max-time 3 "$BASE/agents/billing_agent_1/promotion/thresholds")
check "Thresholds API accessible"  echo "$THRESHOLDS" | grep -q "min_access_count"

# ── 6. Agent Quota ──────────────────────────────────────────────────────────
echo -e "${CYAN}[6] Agent Resource Quota${NC}"

Q_GET=$(curl -sf --max-time 3 "$BASE/agents/billing_agent_1/quota")
check "Default quota exists"  echo "$Q_GET" | grep -q "max_qps"

Q_UPDATE=$(curl -sf --max-time 3 -X PUT "$BASE/agents/billing_agent_1/quota" \
    -H "Content-Type: application/json" \
    -d '{"max_qps":5000,"max_memory_bytes":2147483648}')
check "Update quota succeeds"  echo "$Q_UPDATE" | grep -q "5000"

Q_AFTER=$(curl -sf --max-time 3 "$BASE/agents/billing_agent_1/quota")
check "Updated quota persisted"  echo "$Q_AFTER" | grep -q "5000"

# ── 7. Centroids ────────────────────────────────────────────────────────────
echo -e "${CYAN}[7] LTSM Centroid Query${NC}"

CENTROIDS=$(curl -sf --max-time 3 "$BASE/api/v1/centroids/default")
check "Centroid API responds"  echo "$CENTROIDS" | grep -q "collection_name\|centroids"

ALLIANCE=$(curl -sf --max-time 3 "$BASE/api/v1/alliance/demo_federation/centroids")
check "Alliance centroid API responds"  echo "$ALLIANCE" | grep -q "federation_id\|centroids"

# ── 8. Metrics ──────────────────────────────────────────────────────────────
echo -e "${CYAN}[8] Prometheus Metrics${NC}"
METRICS=$(curl -sf --max-time 3 "$BASE/metrics")

check "vecmindb metrics exported"       echo "$METRICS" | grep -q "vecmindb"
check "license_remaining_days gauge"    echo "$METRICS" | grep -q "license_remaining_days"
check "promotion metrics present"       echo "$METRICS" | grep -q "promotion_"

echo "$METRICS" | grep -E "^# (HELP|TYPE)|^vecmindb_" | head -20 | while read line; do
    echo "    $line"
done

# ── 9. Sovereignty Isolation ────────────────────────────────────────────────
echo -e "${CYAN}[9] Sovereignty Isolation${NC}"
# Agent A should NOT see Agent B's private memories
CROSS=$(mcp_search "refund policy" "support_agent_1")
check "Sovereignty isolation enforced"  echo "$CROSS" | grep -qv "billing"

# ── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}═══════════════════════════════════════${NC}"
echo -e "${BOLD}  Results: ${GREEN}$pass passed${NC}, ${RED}$fail failed${NC}"
echo -e "${BOLD}═══════════════════════════════════════${NC}"
[ "$fail" -eq 0 ] || exit 1
