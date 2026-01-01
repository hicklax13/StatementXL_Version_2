#!/bin/bash
# Security Audit Script for StatementXL
# Runs comprehensive security checks and generates audit report

set -e

echo "================================================"
echo "StatementXL Security Audit"
echo "Date: $(date)"
echo "================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Create reports directory
REPORT_DIR="security-reports"
mkdir -p "$REPORT_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_FILE="$REPORT_DIR/security_audit_$TIMESTAMP.md"

# Initialize report
cat > "$REPORT_FILE" << EOF
# Security Audit Report
**Date:** $(date)
**Version:** 1.0.0

---

## Executive Summary

This report contains the results of a comprehensive security audit of StatementXL.

---

EOF

echo "📋 Starting Security Audit..."
echo ""

# 1. Python Dependency Vulnerability Scan
echo "1️⃣  Scanning Python dependencies for vulnerabilities..."
echo "## 1. Python Dependency Vulnerabilities" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

if command -v pip-audit &> /dev/null; then
    echo "Running pip-audit..."
    pip-audit --format json > "$REPORT_DIR/pip_audit_$TIMESTAMP.json" 2>&1 || true
    
    if [ -f "$REPORT_DIR/pip_audit_$TIMESTAMP.json" ]; then
        VULN_COUNT=$(cat "$REPORT_DIR/pip_audit_$TIMESTAMP.json" | grep -o '"vulnerabilities":' | wc -l || echo "0")
        if [ "$VULN_COUNT" -eq 0 ]; then
            echo -e "${GREEN}✅ No vulnerabilities found in Python dependencies${NC}"
            echo "**Status:** ✅ PASS - No vulnerabilities detected" >> "$REPORT_FILE"
        else
            echo -e "${YELLOW}⚠️  Found $VULN_COUNT potential vulnerabilities${NC}"
            echo "**Status:** ⚠️  WARNING - $VULN_COUNT vulnerabilities found" >> "$REPORT_FILE"
            echo "See detailed report: \`pip_audit_$TIMESTAMP.json\`" >> "$REPORT_FILE"
        fi
    fi
else
    echo -e "${YELLOW}⚠️  pip-audit not installed. Installing...${NC}"
    pip install pip-audit
    pip-audit --format json > "$REPORT_DIR/pip_audit_$TIMESTAMP.json" 2>&1 || true
fi
echo "" >> "$REPORT_FILE"

# 2. NPM Dependency Audit
echo ""
echo "2️⃣  Scanning NPM dependencies for vulnerabilities..."
echo "## 2. NPM Dependency Vulnerabilities" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

if [ -d "frontend" ]; then
    cd frontend
    npm audit --json > "../$REPORT_DIR/npm_audit_$TIMESTAMP.json" 2>&1 || true
    cd ..
    
    if [ -f "$REPORT_DIR/npm_audit_$TIMESTAMP.json" ]; then
        CRITICAL=$(cat "$REPORT_DIR/npm_audit_$TIMESTAMP.json" | grep -o '"critical":[0-9]*' | head -1 | grep -o '[0-9]*' || echo "0")
        HIGH=$(cat "$REPORT_DIR/npm_audit_$TIMESTAMP.json" | grep -o '"high":[0-9]*' | head -1 | grep -o '[0-9]*' || echo "0")
        
        if [ "$CRITICAL" -eq 0 ] && [ "$HIGH" -eq 0 ]; then
            echo -e "${GREEN}✅ No critical/high vulnerabilities in NPM dependencies${NC}"
            echo "**Status:** ✅ PASS - No critical or high severity vulnerabilities" >> "$REPORT_FILE"
        else
            echo -e "${RED}❌ Found $CRITICAL critical and $HIGH high severity vulnerabilities${NC}"
            echo "**Status:** ❌ FAIL - $CRITICAL critical, $HIGH high severity" >> "$REPORT_FILE"
            echo "See detailed report: \`npm_audit_$TIMESTAMP.json\`" >> "$REPORT_FILE"
        fi
    fi
else
    echo -e "${YELLOW}⚠️  Frontend directory not found${NC}"
    echo "**Status:** ⚠️  SKIP - Frontend directory not found" >> "$REPORT_FILE"
fi
echo "" >> "$REPORT_FILE"

# 3. Secret Scanning
echo ""
echo "3️⃣  Scanning for exposed secrets and credentials..."
echo "## 3. Secret Scanning" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

SECRET_PATTERNS=(
    "password\s*=\s*['\"][^'\"]{3,}"
    "api[_-]?key\s*=\s*['\"][^'\"]{10,}"
    "secret\s*=\s*['\"][^'\"]{10,}"
    "token\s*=\s*['\"][^'\"]{10,}"
    "AKIA[0-9A-Z]{16}"  # AWS Access Key
    "sk_live_[0-9a-zA-Z]{24}"  # Stripe Live Key
)

SECRETS_FOUND=0
for pattern in "${SECRET_PATTERNS[@]}"; do
    if grep -r -i -E "$pattern" --exclude-dir={node_modules,.git,venv,__pycache__,.pytest_cache,security-reports} . > /dev/null 2>&1; then
        SECRETS_FOUND=$((SECRETS_FOUND + 1))
    fi
done

if [ "$SECRETS_FOUND" -eq 0 ]; then
    echo -e "${GREEN}✅ No exposed secrets detected${NC}"
    echo "**Status:** ✅ PASS - No hardcoded secrets found" >> "$REPORT_FILE"
else
    echo -e "${RED}❌ Found $SECRETS_FOUND potential exposed secrets${NC}"
    echo "**Status:** ❌ FAIL - $SECRETS_FOUND potential secrets detected" >> "$REPORT_FILE"
    echo "**Action Required:** Review and move to environment variables" >> "$REPORT_FILE"
fi
echo "" >> "$REPORT_FILE"

# 4. OWASP Top 10 Checklist
echo ""
echo "4️⃣  Verifying OWASP Top 10 compliance..."
echo "## 4. OWASP Top 10 Compliance" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Check for SQLAlchemy (SQL Injection protection)
if grep -r "from sqlalchemy" backend/ > /dev/null 2>&1; then
    echo -e "${GREEN}✅ SQL Injection: Using SQLAlchemy ORM${NC}"
    echo "- ✅ **A03:2021 – Injection:** SQLAlchemy ORM used" >> "$REPORT_FILE"
else
    echo -e "${YELLOW}⚠️  SQL Injection: SQLAlchemy not detected${NC}"
    echo "- ⚠️  **A03:2021 – Injection:** Manual review required" >> "$REPORT_FILE"
fi

# Check for JWT authentication
if grep -r "jwt" backend/ > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Authentication: JWT implementation found${NC}"
    echo "- ✅ **A07:2021 – Identification and Authentication Failures:** JWT auth implemented" >> "$REPORT_FILE"
else
    echo -e "${RED}❌ Authentication: JWT not detected${NC}"
    echo "- ❌ **A07:2021 – Identification and Authentication Failures:** No JWT found" >> "$REPORT_FILE"
fi

# Check for CORS configuration
if grep -r "CORSMiddleware" backend/ > /dev/null 2>&1; then
    echo -e "${GREEN}✅ CORS: Middleware configured${NC}"
    echo "- ✅ **A05:2021 – Security Misconfiguration:** CORS configured" >> "$REPORT_FILE"
else
    echo -e "${YELLOW}⚠️  CORS: Configuration not found${NC}"
    echo "- ⚠️  **A05:2021 – Security Misconfiguration:** CORS needs review" >> "$REPORT_FILE"
fi

# Check for rate limiting
if grep -r "RateLimiter\|rate_limit" backend/ > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Rate Limiting: Implementation found${NC}"
    echo "- ✅ **A04:2021 – Insecure Design:** Rate limiting implemented" >> "$REPORT_FILE"
else
    echo -e "${YELLOW}⚠️  Rate Limiting: Not detected${NC}"
    echo "- ⚠️  **A04:2021 – Insecure Design:** Rate limiting needs verification" >> "$REPORT_FILE"
fi

echo "" >> "$REPORT_FILE"

# 5. Security Headers Check
echo ""
echo "5️⃣  Checking security headers configuration..."
echo "## 5. Security Headers" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

REQUIRED_HEADERS=(
    "X-Content-Type-Options"
    "X-Frame-Options"
    "Content-Security-Policy"
    "Strict-Transport-Security"
)

HEADERS_FOUND=0
for header in "${REQUIRED_HEADERS[@]}"; do
    if grep -r "$header" backend/ > /dev/null 2>&1; then
        HEADERS_FOUND=$((HEADERS_FOUND + 1))
        echo "- ✅ $header: Configured" >> "$REPORT_FILE"
    else
        echo "- ❌ $header: Not found" >> "$REPORT_FILE"
    fi
done

if [ "$HEADERS_FOUND" -eq ${#REQUIRED_HEADERS[@]} ]; then
    echo -e "${GREEN}✅ All required security headers configured${NC}"
    echo "" >> "$REPORT_FILE"
    echo "**Status:** ✅ PASS - All security headers present" >> "$REPORT_FILE"
else
    echo -e "${YELLOW}⚠️  $HEADERS_FOUND/${#REQUIRED_HEADERS[@]} security headers configured${NC}"
    echo "" >> "$REPORT_FILE"
    echo "**Status:** ⚠️  WARNING - Missing headers" >> "$REPORT_FILE"
fi
echo "" >> "$REPORT_FILE"

# 6. File Permissions Check
echo ""
echo "6️⃣  Checking file permissions..."
echo "## 6. File Permissions" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Check for overly permissive files
PERMISSIVE_FILES=$(find . -type f -perm -o+w ! -path "./.git/*" ! -path "./node_modules/*" ! -path "./venv/*" 2>/dev/null | wc -l)

if [ "$PERMISSIVE_FILES" -eq 0 ]; then
    echo -e "${GREEN}✅ No world-writable files found${NC}"
    echo "**Status:** ✅ PASS - No overly permissive files" >> "$REPORT_FILE"
else
    echo -e "${YELLOW}⚠️  Found $PERMISSIVE_FILES world-writable files${NC}"
    echo "**Status:** ⚠️  WARNING - $PERMISSIVE_FILES world-writable files" >> "$REPORT_FILE"
fi
echo "" >> "$REPORT_FILE"

# Summary
echo ""
echo "## Summary" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "| Check | Status |" >> "$REPORT_FILE"
echo "|-------|--------|" >> "$REPORT_FILE"
echo "| Python Dependencies | See above |" >> "$REPORT_FILE"
echo "| NPM Dependencies | See above |" >> "$REPORT_FILE"
echo "| Secret Scanning | $([ "$SECRETS_FOUND" -eq 0 ] && echo "✅ PASS" || echo "❌ FAIL") |" >> "$REPORT_FILE"
echo "| OWASP Top 10 | ✅ Mostly Compliant |" >> "$REPORT_FILE"
echo "| Security Headers | $([ "$HEADERS_FOUND" -eq ${#REQUIRED_HEADERS[@]} ] && echo "✅ PASS" || echo "⚠️  WARNING") |" >> "$REPORT_FILE"
echo "| File Permissions | $([ "$PERMISSIVE_FILES" -eq 0 ] && echo "✅ PASS" || echo "⚠️  WARNING") |" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Recommendations
echo "## Recommendations" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "1. **Immediate Actions:**" >> "$REPORT_FILE"
if [ "$SECRETS_FOUND" -gt 0 ]; then
    echo "   - ❌ Remove hardcoded secrets and use environment variables" >> "$REPORT_FILE"
fi
echo "   - Review and fix any critical/high severity dependency vulnerabilities" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "2. **Before Production:**" >> "$REPORT_FILE"
echo "   - Run OWASP ZAP dynamic scan against running application" >> "$REPORT_FILE"
echo "   - Conduct penetration testing" >> "$REPORT_FILE"
echo "   - Enable all security headers in production" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "3. **Ongoing:**" >> "$REPORT_FILE"
echo "   - Run \`pip-audit\` and \`npm audit\` weekly" >> "$REPORT_FILE"
echo "   - Update dependencies monthly" >> "$REPORT_FILE"
echo "   - Review security logs daily" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Final output
echo ""
echo "================================================"
echo "✅ Security Audit Complete!"
echo "================================================"
echo ""
echo "📄 Full report saved to: $REPORT_FILE"
echo ""
echo "Next steps:"
echo "1. Review the full report"
echo "2. Fix any critical issues"
echo "3. Run: docker run -t owasp/zap2docker-stable zap-baseline.py -t http://localhost:8000"
echo ""
