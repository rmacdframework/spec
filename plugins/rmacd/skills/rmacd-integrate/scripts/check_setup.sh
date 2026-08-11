#!/usr/bin/env bash
# check_setup.sh — verify an RMACD integration is wired correctly.
#
# Checks (in order, continues past failures, exits non-zero if any failed):
#   1. rmacd is importable                (pip install "rmacd-framework>=0.14")
#   2. SDK version >= RMACD_MIN_VERSION  (default 0.14)
#   3. RMACD_AGENT_ID is set
#   4. RMACD_PROFILE_PATH is set, the file exists, and `rmacd validate` passes
#
# Usage:
#   bash check_setup.sh [profile.json]
#     With an argument, that profile is checked instead of $RMACD_PROFILE_PATH
#     (the env-var binding checks still run and still count).
#   PYTHON=.venv/bin/python bash check_setup.sh   # pick the interpreter

set -u

PY="${PYTHON:-python3}"
MIN_VERSION="${RMACD_MIN_VERSION:-0.14}"
FAILURES=0

pass() { printf 'ok:   %s\n' "$1"; }
fail() { printf 'FAIL: %s\n      fix: %s\n' "$1" "$2" >&2; FAILURES=$((FAILURES + 1)); }

# --- 1. interpreter + import ------------------------------------------------
if ! command -v "$PY" >/dev/null 2>&1; then
    fail "python interpreter '$PY' not found" \
         "install Python 3.10+, or set PYTHON=/path/to/venv/bin/python"
    echo "check_setup: $FAILURES check(s) failed." >&2
    exit 1
fi

if ! "$PY" -c "import rmacd" >/dev/null 2>&1; then
    fail "the 'rmacd' package is not importable by $PY" \
         "pip install \"rmacd-framework>=${MIN_VERSION}\"  (PyPI name is rmacd-framework; the import name is rmacd — do NOT pip install rmacd)"
    echo "check_setup: $FAILURES check(s) failed." >&2
    exit 1
fi
pass "rmacd is importable ($("$PY" -c 'import rmacd, sys; print(getattr(rmacd, "__version__", "unknown"))'))"

# --- 2. version -------------------------------------------------------------
if "$PY" - "$MIN_VERSION" <<'EOF' >/dev/null 2>&1
import sys
import rmacd

def parse(v):
    parts = []
    for chunk in v.split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits or 0))
    return tuple(parts)

sys.exit(0 if parse(rmacd.__version__) >= parse(sys.argv[1]) else 1)
EOF
then
    pass "rmacd-framework version >= ${MIN_VERSION}"
else
    fail "rmacd-framework version is older than ${MIN_VERSION}" \
         "pip install --upgrade \"rmacd-framework>=${MIN_VERSION}\""
fi

# --- 3. agent identity ------------------------------------------------------
if [ -n "${RMACD_AGENT_ID:-}" ]; then
    pass "RMACD_AGENT_ID is set (${RMACD_AGENT_ID})"
else
    fail "RMACD_AGENT_ID is not set" \
         "export RMACD_AGENT_ID=<agent-name>  (required by PolicyEnforcer.from_env())"
fi

# --- 4. profile binding + validation ---------------------------------------
PROFILE="${1:-${RMACD_PROFILE_PATH:-}}"

if [ -z "${RMACD_PROFILE_PATH:-}" ]; then
    fail "RMACD_PROFILE_PATH is not set" \
         "export RMACD_PROFILE_PATH=./rmacd/profiles/<agent>.json  (required by PolicyEnforcer.from_env())"
else
    pass "RMACD_PROFILE_PATH is set (${RMACD_PROFILE_PATH})"
fi

if [ -z "$PROFILE" ]; then
    fail "no profile to validate" \
         "set RMACD_PROFILE_PATH or pass a profile path as the first argument"
elif [ ! -f "$PROFILE" ]; then
    fail "profile file not found: $PROFILE" \
         "create it (copy the nearest schemas/examples/ profile, or run /rmacd:init)"
else
    if "$PY" -m rmacd.cli validate "$PROFILE" >/dev/null 2>&1; then
        pass "profile validates against the RMACD schema ($PROFILE)"
    else
        fail "profile failed schema validation: $PROFILE" \
             "run: $PY -m rmacd.cli validate \"$PROFILE\"  and fix the reported errors (check profile_id pattern and permissions — C/D on restricted is always rejected)"
    fi
fi

# --- 5. optional environment binding (informational) ------------------------
if [ -n "${RMACD_ENVIRONMENT:-}" ]; then
    pass "RMACD_ENVIRONMENT is set (${RMACD_ENVIRONMENT})"
else
    printf 'note: RMACD_ENVIRONMENT is not set (optional; e.g. export RMACD_ENVIRONMENT=production)\n'
fi

# --- summary ----------------------------------------------------------------
if [ "$FAILURES" -gt 0 ]; then
    echo "check_setup: $FAILURES check(s) failed." >&2
    exit 1
fi
echo "check_setup: all checks passed."
