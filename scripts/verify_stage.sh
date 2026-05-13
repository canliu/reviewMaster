#!/usr/bin/env bash
# verify_stage.sh — Automated quality gate for each ReviewMaster build stage.
#
# Usage:
#   bash scripts/verify_stage.sh <stage_id>
#
#   <stage_id> is one of: init, 0, design, 1, 2, 3, 4, 5, polish, 6, 7
#
# Exit codes:
#   0  — all automated checks passed
#   1  — one or more checks failed
#   2  — usage error or missing prerequisites
#
# Design intent:
# - This script verifies what machines can verify. It is NOT a substitute for
#   the human Quality Gate (see CLAUDE.md). Some things (UI feel, error message
#   clarity, performance perception) require a human and are listed in each
#   stage's Handoff message under "What you should verify manually."
# - Each stage has its own function `verify_stage_<id>()`. They are kept short
#   and explicit so you can read what's being checked at a glance.
# - The script uses `docker compose` to run commands inside containers when
#   possible, mirroring how the app actually runs.

set -uo pipefail

# ---------- host endpoints ----------
# Host ports are shifted from the conventional 8000/3000 because other dev
# stacks on this machine occupy them. Override at the command line if needed:
#   REVIEWMASTER_BACKEND_URL=http://localhost:9000 bash scripts/verify_stage.sh 0
BACKEND_URL="${REVIEWMASTER_BACKEND_URL:-http://localhost:8088}"
FRONTEND_URL="${REVIEWMASTER_FRONTEND_URL:-http://localhost:3300}"

# ---------- color and logging helpers ----------

RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[0;33m'
BLUE=$'\033[0;34m'
BOLD=$'\033[1m'
RESET=$'\033[0m'

CHECK_TOTAL=0
CHECK_FAILED=0
FAILED_NAMES=()

pass() {
  CHECK_TOTAL=$((CHECK_TOTAL + 1))
  printf "  ${GREEN}✓${RESET} %s\n" "$1"
}

fail() {
  CHECK_TOTAL=$((CHECK_TOTAL + 1))
  CHECK_FAILED=$((CHECK_FAILED + 1))
  FAILED_NAMES+=("$1")
  printf "  ${RED}✗${RESET} %s\n" "$1"
  if [ -n "${2:-}" ]; then
    printf "    ${YELLOW}→${RESET} %s\n" "$2"
  fi
}

skip() {
  printf "  ${YELLOW}~${RESET} %s ${YELLOW}(skipped: %s)${RESET}\n" "$1" "$2"
}

section() {
  printf "\n${BOLD}${BLUE}━━━ %s ━━━${RESET}\n" "$1"
}

# Run a command and pass/fail based on exit code. Captures stderr for the failure message.
check() {
  local name="$1"
  shift
  local output
  output=$("$@" 2>&1)
  if [ $? -eq 0 ]; then
    pass "$name"
  else
    fail "$name" "$(echo "$output" | tail -3 | tr '\n' ' ')"
  fi
}

# Run a check that requires a specific string in the output.
check_grep() {
  local name="$1"
  local pattern="$2"
  shift 2
  local output
  output=$("$@" 2>&1)
  if echo "$output" | grep -q -- "$pattern"; then
    pass "$name"
  else
    fail "$name" "expected '$pattern' in output"
  fi
}

# ---------- common preflight ----------

require_repo_root() {
  if [ ! -f "CLAUDE.md" ] || [ ! -d "prompts" ]; then
    printf "${RED}This script must be run from the repo root (where CLAUDE.md lives).${RESET}\n" >&2
    exit 2
  fi
}

require_clean_git() {
  if [ -n "$(git status --porcelain)" ]; then
    fail "git working tree is clean" "uncommitted changes present; commit or stash first"
  else
    pass "git working tree is clean"
  fi
}

require_on_stage_branch() {
  local stage="$1"
  local branch
  branch=$(git branch --show-current)
  # Two valid formats:
  #   "stage-<id>-<slug>"  for numbered stages (e.g. stage-0-skeleton)
  #   "stage-<id>"         for named stages (e.g. stage-design, stage-polish)
  # Plus we accept "main" so post-merge verifies still pass.
  if [[ "$branch" == "stage-$stage" ]] || [[ "$branch" == stage-"$stage"-* ]] || [[ "$branch" == "main" ]]; then
    pass "on expected branch ($branch)"
  else
    fail "on expected branch" "current branch is '$branch', expected 'stage-$stage' or 'stage-$stage-*' or 'main'"
  fi
}

# ---------- generic checks reused across stages ----------

check_docker_compose_up() {
  check_grep "docker compose has running services" "Up\|running" docker compose ps
}

check_backend_health() {
  local response
  response=$(curl -sf ${BACKEND_URL}/health 2>&1)
  if echo "$response" | grep -q '"status":"ok"'; then
    pass "backend /health responds ok"
  else
    fail "backend /health responds ok" "got: $response"
  fi
}

check_frontend_renders() {
  local code
  code=$(curl -sf -o /dev/null -w "%{http_code}" ${FRONTEND_URL} 2>&1)
  if [ "$code" = "200" ]; then
    pass "frontend serves a 200 at /"
  else
    fail "frontend serves a 200 at /" "got HTTP $code"
  fi
}

check_backend_tests() {
  check "backend pytest passes" docker compose exec -T backend pytest -q
}

check_frontend_lint() {
  check "frontend lint passes" docker compose exec -T frontend npm run lint --silent
}

check_frontend_build() {
  check "frontend builds" docker compose exec -T frontend npm run build --silent
}

check_alembic_up_to_date() {
  local head_rev current_rev
  head_rev=$(docker compose exec -T backend alembic heads 2>/dev/null | awk '{print $1}')
  current_rev=$(docker compose exec -T backend alembic current 2>/dev/null | awk '{print $1}')
  if [ -n "$head_rev" ] && [ "$head_rev" = "$current_rev" ]; then
    pass "alembic at head ($head_rev)"
  else
    fail "alembic at head" "head=$head_rev current=$current_rev"
  fi
}

check_table_exists() {
  local table="$1"
  local result
  result=$(docker compose exec -T postgres psql -U postgres -d app -tAc \
    "SELECT to_regclass('public.$table');" 2>/dev/null)
  if [ "$result" = "$table" ]; then
    pass "table exists: $table"
  else
    fail "table exists: $table" "to_regclass returned '$result'"
  fi
}

# ---------- per-stage verification functions ----------

verify_stage_init() {
  section "Stage init — Dev environment & git setup"

  check "git is installed" git --version
  check "docker is installed" docker --version
  check "docker compose is available" docker compose version
  check "node 22 is active" bash -c 'node --version | grep -q "^v22"'
  check "python 3.11+ is available" python3.11 --version
  check "pre-commit is installed" pre-commit --version

  section "Repository structure"
  for f in .gitignore .gitattributes .editorconfig .pre-commit-config.yaml \
           CONTRIBUTING.md README.md .env.example CLAUDE.md; do
    if [ -f "$f" ]; then pass "exists: $f"; else fail "exists: $f"; fi
  done

  section "Operational files (must be present before stage_init runs)"
  for f in prompts/SUMMARY.md prompts/MASTER_PROMPT.md \
           prompts/stage_init.md prompts/stage_0_skeleton.md prompts/stage_design.md \
           prompts/stage_1_auth.md prompts/stage_2_upload.md prompts/stage_3_settings.md \
           prompts/stage_4_list.md prompts/stage_5_request.md prompts/stage_polish.md \
           prompts/stage_6_spapi.md prompts/stage_7_ops.md \
           scripts/verify_stage.sh; do
    if [ -f "$f" ]; then pass "exists: $f"; else fail "exists: $f"; fi
  done

  if [ -x "scripts/verify_stage.sh" ]; then
    pass "scripts/verify_stage.sh is executable"
  else
    fail "scripts/verify_stage.sh is executable" "run: chmod +x scripts/verify_stage.sh"
  fi

  section "Git state"
  local branch
  branch=$(git branch --show-current)
  if [ "$branch" = "main" ]; then pass "on main branch"; else fail "on main branch" "got '$branch'"; fi

  if git tag | grep -q "^v0.0-init$"; then
    pass "v0.0-init tag exists"
  else
    fail "v0.0-init tag exists"
  fi

  check "pre-commit runs clean" pre-commit run --all-files
}

verify_stage_0() {
  section "Stage 0 — Project skeleton & data model"

  require_on_stage_branch 0
  check_docker_compose_up
  check_backend_health
  check_frontend_renders
  check_alembic_up_to_date

  section "All 8 tables present"
  for t in users user_settings orders buyer_product_stats \
           review_requests review_request_notes upload_batches seller_credentials; do
    check_table_exists "$t"
  done

  section "Key constraints"
  check_grep "orders has UNIQUE(user_id, order_id)" "orders_user_id_order_id" \
    docker compose exec -T postgres psql -U postgres -d app -c "\d orders"
  check_grep "review_requests has UNIQUE(user_id, order_uuid)" "review_requests_user_id_order_uuid" \
    docker compose exec -T postgres psql -U postgres -d app -c "\d review_requests"
  check_grep "review_request_notes references orders" "order_uuid" \
    docker compose exec -T postgres psql -U postgres -d app -c "\d review_request_notes"

  section "Basic checks"
  check_backend_tests
  check_frontend_lint
}

verify_stage_design() {
  section "Stage design — Visual foundation"

  require_on_stage_branch design

  section "Brand and tokens"
  for f in frontend/tailwind.config.ts frontend/app/globals.css frontend/lib/fonts.ts; do
    if [ -f "$f" ]; then pass "exists: $f"; else fail "exists: $f"; fi
  done

  check_grep "tailwind config defines primary color" "primary" cat frontend/tailwind.config.ts

  section "Core components"
  for f in frontend/components/layout/AppShell.tsx \
           frontend/components/layout/PageHeader.tsx \
           frontend/components/layout/EmptyState.tsx \
           frontend/components/data/StatCard.tsx \
           frontend/components/data/StatusBadge.tsx \
           frontend/components/data/DataTableShell.tsx \
           frontend/components/feedback/Toaster.tsx \
           frontend/components/feedback/ConfirmDialog.tsx \
           frontend/components/brand/Logo.tsx \
           frontend/lib/format.ts; do
    if [ -f "$f" ]; then pass "exists: $f"; else fail "exists: $f"; fi
  done

  section "Error pages"
  for f in frontend/app/not-found.tsx frontend/app/error.tsx; do
    if [ -f "$f" ]; then pass "exists: $f"; else fail "exists: $f"; fi
  done

  section "Build and lint"
  check_frontend_lint
  check_frontend_build

  section "Component smoke tests"
  check "frontend tests pass" docker compose exec -T frontend npm test --silent
}

verify_stage_1() {
  section "Stage 1 — Auth"

  require_on_stage_branch 1
  check_backend_tests

  section "Auth endpoints respond"
  # Register a throwaway user, verify the flow
  local email="verify-$(date +%s)@example.com"
  local pwd="testpass1"

  local reg_response
  reg_response=$(curl -sf -X POST ${BACKEND_URL}/api/auth/register \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$email\",\"password\":\"$pwd\"}" 2>&1)
  if echo "$reg_response" | grep -q "access_token"; then
    pass "register returns tokens"
  else
    fail "register returns tokens" "$reg_response"
  fi

  local login_response
  login_response=$(curl -sf -X POST ${BACKEND_URL}/api/auth/login \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$email\",\"password\":\"$pwd\"}" 2>&1)
  if echo "$login_response" | grep -q "access_token"; then
    pass "login returns tokens"
  else
    fail "login returns tokens" "$login_response"
  fi

  local token
  token=$(echo "$login_response" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
  local me_response
  me_response=$(curl -sf -H "Authorization: Bearer $token" ${BACKEND_URL}/api/auth/me 2>&1)
  if echo "$me_response" | grep -q "$email"; then
    pass "/me returns the right user with valid token"
  else
    fail "/me returns the right user with valid token" "$me_response"
  fi

  local bad_response
  bad_response=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer invalid.token.here" ${BACKEND_URL}/api/auth/me)
  if [ "$bad_response" = "401" ]; then
    pass "/me rejects bad token with 401"
  else
    fail "/me rejects bad token with 401" "got HTTP $bad_response"
  fi

  section "Frontend pages exist"
  # Dashboard home is at app/(dashboard)/dashboard/page.tsx (URL /dashboard);
  # a sibling app/(dashboard)/page.tsx would collide with app/page.tsx since
  # route groups don't appear in the URL. See stage-design handoff notes.
  for f in frontend/app/\(auth\)/login/page.tsx \
           frontend/app/\(auth\)/register/page.tsx \
           frontend/app/\(dashboard\)/dashboard/page.tsx; do
    if [ -f "$f" ]; then pass "exists: $f"; else fail "exists: $f"; fi
  done

  check_frontend_lint
}

verify_stage_2() {
  section "Stage 2 — Excel upload"

  require_on_stage_branch 2
  check_alembic_up_to_date
  check_backend_tests

  section "Upload pipeline"
  if [ -f "backend/tests/fixtures/sample_orders.xlsx" ]; then
    pass "test fixture sample_orders.xlsx exists"
  else
    fail "test fixture sample_orders.xlsx exists" "expected at backend/tests/fixtures/"
  fi

  # Verify worker container is up and consuming the queue
  check_grep "RQ worker is running" "worker" docker compose ps

  section "Frontend page"
  if [ -f "frontend/app/(dashboard)/uploads/page.tsx" ]; then
    pass "uploads page exists"
  else
    fail "uploads page exists"
  fi

  check_frontend_lint
}

verify_stage_3() {
  section "Stage 3 — User settings"

  require_on_stage_branch 3
  check_backend_tests

  section "Endpoints"
  # Auth required — register + login to get token, then hit /settings
  local email="verify-$(date +%s)@example.com"
  local token
  token=$(curl -sf -X POST ${BACKEND_URL}/api/auth/register \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$email\",\"password\":\"testpass1\"}" 2>/dev/null \
    | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

  if [ -z "$token" ]; then
    fail "could not obtain auth token for settings test"
    return
  fi

  check_grep "GET /api/settings returns repeat_grain" "repeat_grain" \
    curl -sf -H "Authorization: Bearer $token" ${BACKEND_URL}/api/settings

  check_grep "GET /api/settings returns timezone" "timezone" \
    curl -sf -H "Authorization: Bearer $token" ${BACKEND_URL}/api/settings

  section "Frontend"
  if [ -f "frontend/app/(dashboard)/settings/page.tsx" ]; then
    pass "settings page exists"
  else
    fail "settings page exists"
  fi

  check_frontend_lint
}

verify_stage_4() {
  section "Stage 4 — Repeat orders list"

  require_on_stage_branch 4
  check_backend_tests
  check_alembic_up_to_date

  section "Endpoints"
  local email="verify-$(date +%s)@example.com"
  local token
  token=$(curl -sf -X POST ${BACKEND_URL}/api/auth/register \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$email\",\"password\":\"testpass1\"}" 2>/dev/null \
    | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

  if [ -z "$token" ]; then
    fail "could not obtain auth token"
    return
  fi

  # New user has no orders — endpoints should still return valid shape
  check_grep "repeat-orders list returns items array" "items" \
    curl -sf -H "Authorization: Bearer $token" "${BACKEND_URL}/api/repeat-orders?page=1&page_size=10"

  check_grep "repeat-orders summary returns KPI fields" "total_repeat_orders" \
    curl -sf -H "Authorization: Bearer $token" ${BACKEND_URL}/api/repeat-orders/summary

  section "Frontend"
  if [ -f "frontend/app/(dashboard)/repeat-orders/page.tsx" ]; then
    pass "repeat-orders page exists"
  else
    fail "repeat-orders page exists"
  fi

  check_frontend_lint
}

verify_stage_5() {
  section "Stage 5 — Request review (manual + link + CSV)"

  require_on_stage_branch 5
  check_backend_tests
  check_alembic_up_to_date

  section "Endpoints"
  local email="verify-$(date +%s)@example.com"
  local token
  token=$(curl -sf -X POST ${BACKEND_URL}/api/auth/register \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$email\",\"password\":\"testpass1\"}" 2>/dev/null \
    | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

  if [ -z "$token" ]; then
    fail "could not obtain auth token"
    return
  fi

  # Empty user — list endpoints should return valid shape
  check_grep "review-requests list endpoint responds" "items\|total" \
    curl -sf -H "Authorization: Bearer $token" "${BACKEND_URL}/api/review-requests?page=1&page_size=10"

  # CSV export should set Content-Disposition. Use GET (-D dumps headers,
  # -o discards body) rather than HEAD — FastAPI doesn't auto-register HEAD
  # handlers for GET routes, so HEAD would 405.
  local headers
  headers=$(curl -sf -D - -o /dev/null -H "Authorization: Bearer $token" \
    ${BACKEND_URL}/api/review-requests/export.csv 2>&1)
  if echo "$headers" | grep -qi "content-disposition.*attachment"; then
    pass "CSV export has Content-Disposition: attachment"
  else
    fail "CSV export has Content-Disposition: attachment"
  fi

  section "Frontend"
  if [ -f "frontend/app/(dashboard)/review-requests/page.tsx" ]; then
    pass "review-requests page exists"
  else
    fail "review-requests page exists"
  fi

  check_frontend_lint
  check_frontend_build
}

verify_stage_polish() {
  section "Stage polish — UX refinement"

  require_on_stage_branch polish

  section "Frontend quality"
  check_frontend_lint
  check_frontend_build
  check "frontend tests pass" docker compose exec -T frontend npm test --silent

  section "Onboarding components"
  # The exact filenames depend on implementation choice but onboarding
  # state should live somewhere queryable.
  if grep -rq "onboarding_complete" frontend/; then
    pass "onboarding flag referenced in frontend"
  else
    fail "onboarding flag referenced in frontend" "expected 'onboarding_complete' somewhere"
  fi

  section "Keyboard shortcuts"
  if grep -rq "useHotkeys\|react-hotkeys-hook\|key === '?'" frontend/; then
    pass "keyboard shortcut handling is present"
  else
    fail "keyboard shortcut handling is present"
  fi

  skip "Lighthouse performance ≥ 85" "human-driven; run lighthouse manually"
  skip "axe-core zero violations" "human-driven; run axe DevTools manually"
  skip "responsive at 375px" "human-driven; check in browser devtools"
}

verify_stage_6() {
  section "Stage 6 — SP-API integration"

  require_on_stage_branch 6
  check_backend_tests
  check_alembic_up_to_date

  section "Encryption module"
  check "crypto tests pass" docker compose exec -T backend pytest tests/test_crypto.py -q

  section "Endpoints exist"
  local email="verify-$(date +%s)@example.com"
  local token
  token=$(curl -sf -X POST ${BACKEND_URL}/api/auth/register \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$email\",\"password\":\"testpass1\"}" 2>/dev/null \
    | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

  if [ -z "$token" ]; then
    fail "could not obtain auth token"
    return
  fi

  check_grep "GET /api/sp-api/credentials returns configured field" "configured" \
    curl -sf -H "Authorization: Bearer $token" ${BACKEND_URL}/api/sp-api/credentials

  section "Worker for solicitations"
  if [ -f "backend/app/workers/solicitations.py" ]; then
    pass "solicitations worker exists"
  else
    fail "solicitations worker exists"
  fi

  skip "real SP-API smoke call" "human-driven; requires live credentials"
}

verify_stage_7() {
  section "Stage 7 — Production ops"

  require_on_stage_branch 7

  section "Production artifacts"
  for f in docker-compose.prod.yml Caddyfile .env.prod.example \
           scripts/backup.sh scripts/deploy.sh \
           OPERATIONS.md RESTORE.md SECURITY.md SERVER_SETUP.md INCIDENTS.md \
           .github/workflows/test.yml .github/workflows/release.yml .github/workflows/deploy.yml; do
    if [ -f "$f" ]; then pass "exists: $f"; else fail "exists: $f"; fi
  done

  section "CI configuration"
  check_grep "test workflow runs pytest" "pytest" cat .github/workflows/test.yml
  check_grep "test workflow runs npm test" "npm" cat .github/workflows/test.yml

  section "Security hygiene"
  check_grep "Caddyfile has HSTS" "Strict-Transport-Security" cat Caddyfile
  check_grep "Caddyfile has CSP" "Content-Security-Policy" cat Caddyfile

  section "Secrets are not committed"
  if grep -rE "^[A-Z_]+SECRET=|^.*REFRESH_TOKEN=|^.*ACCESS_KEY=" .env.prod 2>/dev/null; then
    fail ".env.prod is not committed" ".env.prod found in repo — must be gitignored"
  else
    pass ".env.prod is not committed"
  fi

  skip "Sentry receives events" "human-driven; trigger a test error after deploy"
  skip "backup runs and restores" "human-driven; perform the documented drill"
  skip "load test passes" "human-driven; run k6/locust on staging"
  skip "rate limiting works under load" "human-driven; run the rate-limit drill"
}

# ---------- main dispatcher ----------

main() {
  require_repo_root

  if [ $# -lt 1 ]; then
    printf "${RED}Usage:${RESET} bash scripts/verify_stage.sh <stage_id>\n" >&2
    printf "  stage_id: init | 0 | design | 1 | 2 | 3 | 4 | 5 | polish | 6 | 7\n" >&2
    exit 2
  fi

  local stage="$1"
  local start_time
  start_time=$(date +%s)

  printf "${BOLD}Verifying stage: %s${RESET}\n" "$stage"

  # All stages except init require a clean working tree before the verify can
  # be trusted. CLAUDE.md's Handoff Protocol requires "git status clean" as a
  # precondition. init runs on main and may legitimately have an uncommitted
  # state during initial setup.
  if [ "$stage" != "init" ]; then
    section "Git hygiene"
    require_clean_git
  fi

  case "$stage" in
    init)   verify_stage_init   ;;
    0)      verify_stage_0      ;;
    design) verify_stage_design ;;
    1)      verify_stage_1      ;;
    2)      verify_stage_2      ;;
    3)      verify_stage_3      ;;
    4)      verify_stage_4      ;;
    5)      verify_stage_5      ;;
    polish) verify_stage_polish ;;
    6)      verify_stage_6      ;;
    7)      verify_stage_7      ;;
    *)
      printf "${RED}Unknown stage: %s${RESET}\n" "$stage" >&2
      exit 2
      ;;
  esac

  local end_time elapsed
  end_time=$(date +%s)
  elapsed=$((end_time - start_time))

  section "Summary"
  if [ "$CHECK_FAILED" -eq 0 ]; then
    printf "${GREEN}${BOLD}PASS${RESET} — %d/%d checks passed (%ds)\n" \
      "$CHECK_TOTAL" "$CHECK_TOTAL" "$elapsed"
    exit 0
  else
    printf "${RED}${BOLD}FAIL${RESET} — %d/%d checks failed (%ds)\n" \
      "$CHECK_FAILED" "$CHECK_TOTAL" "$elapsed"
    printf "Failed checks:\n"
    for name in "${FAILED_NAMES[@]}"; do
      printf "  - %s\n" "$name"
    done
    exit 1
  fi
}

main "$@"
