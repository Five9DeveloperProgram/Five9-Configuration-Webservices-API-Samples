#!/usr/bin/env bash
# Portable (mac + linux) coverage + unittest runner mirroring unittest_coverage.ps1
# Run from any dir; it will cd to the script's directory (five9/) so that "tests" resolves.
#
# Usage:
#   ./unittest_coverage.sh [options]
# Options:
#   --no-open          Do not auto-open HTML report
#   --no-html          Do not generate HTML report
#   --xml              Also generate coverage.xml (Cobertura)
#   --erase            Erase previous coverage data before run
#   --branch           Enable branch coverage
#   --fail-under=N     Fail (exit 2) if total coverage < N
#   -v / --verbose     Verbose unittest output
#   --pattern=PAT      Test file pattern (default: test*.py)
#   --tests-dir=DIR    Start dir for discovery (default: tests)
#   --html-dir=DIR     HTML output dir (default: htmlcov)
#   --report           Print terminal coverage report
#   --help             Show help
#
# Examples:
#   ./unittest_coverage.sh                 # run, create + open HTML
#   ./unittest_coverage.sh --no-open --report --fail-under=80
#   ./unittest_coverage.sh --pattern='testSessions.py'
#
# Exits:
#   0 success; 2 coverage below threshold; other non-zero = error.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

NO_OPEN=false
NO_HTML=false
DO_XML=false
DO_ERASE=false
DO_BRANCH=false
FAIL_UNDER=""
VERBOSE=false
PATTERN="test*.py"
TESTS_DIR="tests"   # tests live in five9/tests relative to this script
HTML_DIR="htmlcov"
DO_REPORT=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-open) NO_OPEN=true; shift ;;
    --no-html) NO_HTML=true; shift ;;
    --xml) DO_XML=true; shift ;;
    --erase) DO_ERASE=true; shift ;;
    --branch) DO_BRANCH=true; shift ;;
    --fail-under=*) FAIL_UNDER="${1#*=}"; shift ;;
    --fail-under) FAIL_UNDER="$2"; shift 2 ;;
    -v|--verbose) VERBOSE=true; shift ;;
    --pattern=*) PATTERN="${1#*=}"; shift ;;
    --pattern) PATTERN="$2"; shift 2 ;;
    --tests-dir=*) TESTS_DIR="${1#*=}"; shift ;;
    --tests-dir) TESTS_DIR="$2"; shift 2 ;;
    --html-dir=*) HTML_DIR="${1#*=}"; shift ;;
    --html-dir) HTML_DIR="$2"; shift 2 ;;
    --report) DO_REPORT=true; shift ;;
    --help|-h)
      grep '^# ' "$0" | sed 's/^# //'
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

if ! command -v coverage >/dev/null 2>&1; then
  echo "coverage command not found. Install with: pip install coverage" >&2
  exit 1
fi

COVERAGE_ARGS=(run -m unittest discover -s "$TESTS_DIR" -p "$PATTERN")
$VERBOSE && COVERAGE_ARGS+=( -v ) || true
$DO_BRANCH && COVERAGE_ARGS=(run --branch -m unittest discover -s "$TESTS_DIR" -p "$PATTERN")

$DO_ERASE && coverage erase

echo "==> Running tests with coverage (${COVERAGE_ARGS[*]})"
set +e
coverage "${COVERAGE_ARGS[@]}"
TEST_STATUS=$?
set -e

if [[ $TEST_STATUS -ne 0 ]]; then
  echo "Unit tests failed (exit $TEST_STATUS)." >&2
  exit $TEST_STATUS
fi

# Terminal report & threshold
if $DO_REPORT || [[ -n "$FAIL_UNDER" ]]; then
  if [[ -n "$FAIL_UNDER" ]]; then
    coverage report --fail-under="$FAIL_UNDER" || {
      STATUS=$?
      # coverage uses exit 2 for threshold failure
      if [[ $STATUS -eq 2 ]]; then
        echo "Coverage below threshold ($FAIL_UNDER%)." >&2
      fi
      exit $STATUS
    }
  else
    coverage report
  fi
fi

# XML report
$DO_XML && coverage xml

# HTML report
if ! $NO_HTML; then
  coverage html -d "$HTML_DIR"
  if ! $NO_OPEN; then
    if command -v open >/dev/null 2>&1; then
      open "$HTML_DIR/index.html" >/dev/null 2>&1 || true
    elif command -v xdg-open >/dev/null 2>&1; then
      xdg-open "$HTML_DIR/index.html" >/dev/null 2>&1 || true
    else
      echo "Report: $HTML_DIR/index.html"
    fi
  else
    echo "HTML report generated at $HTML_DIR/index.html (not opened)"
  fi
fi

echo "Done."
