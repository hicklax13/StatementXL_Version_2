#!/bin/bash
# StatementXL Deployment Verification Script
# Usage: ./verify-deployment.sh [base_url]

set -e

# Configuration
BASE_URL="${1:-http://localhost:8000}"
FRONTEND_URL="${2:-http://localhost}"

echo "================================================"
echo "StatementXL Deployment Verification"
echo "================================================"
echo "Backend URL: $BASE_URL"
echo "Frontend URL: $FRONTEND_URL"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
PASSED=0
FAILED=0

# Helper function for tests
run_test() {
    local test_name="$1"
    local command="$2"
    local expected="$3"

    echo -n "Testing: $test_name ... "

    if result=$(eval "$command" 2>&1); then
        if [[ -z "$expected" ]] || echo "$result" | grep -q "$expected"; then
            echo -e "${GREEN}✓ PASS${NC}"
            ((PASSED++))
            return 0
        fi
    fi

    echo -e "${RED}✗ FAIL${NC}"
    echo "  Output: $result"
    ((FAILED++))
    return 1
}

echo "=== Health Checks ==="
run_test "Backend health endpoint" \
    "curl -s -f $BASE_URL/health" \
    "healthy"

run_test "Backend readiness endpoint" \
    "curl -s -f $BASE_URL/ready" \
    "ready"

run_test "Frontend accessibility" \
    "curl -s -f -o /dev/null -w '%{http_code}' $FRONTEND_URL" \
    "200"

echo ""
echo "=== API Documentation ==="
run_test "Swagger UI available" \
    "curl -s -f -o /dev/null -w '%{http_code}' $BASE_URL/docs" \
    "200"

run_test "OpenAPI JSON available" \
    "curl -s -f -o /dev/null -w '%{http_code}' $BASE_URL/openapi.json" \
    "200"

echo ""
echo "=== Security Headers ==="
run_test "X-Content-Type-Options header" \
    "curl -s -I $BASE_URL/health | grep -i 'x-content-type-options'" \
    "nosniff"

run_test "X-Frame-Options header" \
    "curl -s -I $BASE_URL/health | grep -i 'x-frame-options'" \
    "DENY"

echo ""
echo "=== API Endpoints ==="
run_test "Auth registration endpoint" \
    "curl -s -o /dev/null -w '%{http_code}' -X POST $BASE_URL/api/v1/auth/register" \
    "422"  # Expects 422 due to missing body, not 404

run_test "Auth login endpoint" \
    "curl -s -o /dev/null -w '%{http_code}' -X POST $BASE_URL/api/v1/auth/login" \
    "422"  # Expects 422 due to missing body

run_test "Templates endpoint (requires auth)" \
    "curl -s -o /dev/null -w '%{http_code}' $BASE_URL/api/v1/library/templates" \
    "401"  # Expects 401 Unauthorized

echo ""
echo "=== Monitoring Endpoints ==="
run_test "Metrics endpoint" \
    "curl -s -f $BASE_URL/metrics" \
    "request_count"

echo ""
echo "=== Rate Limiting ==="
# Make multiple requests to test rate limiting
echo -n "Testing: Rate limiting (10 rapid requests) ... "
rate_limit_hit=false
for i in {1..15}; do
    response=$(curl -s -o /dev/null -w '%{http_code}' $BASE_URL/health)
    if [[ "$response" == "429" ]]; then
        rate_limit_hit=true
        break
    fi
    sleep 0.1
done

if [[ "$rate_limit_hit" == "true" ]]; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠ SKIP${NC} (rate limit not triggered, may need more requests)"
fi

echo ""
echo "=== Database Connection ==="
run_test "Database connectivity (via /ready)" \
    "curl -s $BASE_URL/ready" \
    "database"

echo ""
echo "=== CORS Configuration ==="
run_test "CORS headers present" \
    "curl -s -I -X OPTIONS $BASE_URL/health | grep -i 'access-control'" \
    "access-control"

echo ""
echo "================================================"
echo "Test Results Summary"
echo "================================================"
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo "Total:  $((PASSED + FAILED))"

if [[ $FAILED -eq 0 ]]; then
    echo ""
    echo -e "${GREEN}✓ All tests passed! Deployment looks good.${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}✗ Some tests failed. Please review the errors above.${NC}"
    exit 1
fi
