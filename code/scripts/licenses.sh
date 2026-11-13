#!/bin/sh
# Check the licenses of the Python dependencies or generate license notices.
#
#   scripts/licenses.sh check              fails on licenses that are not allowed
#   scripts/licenses.sh notices <file>     writes all license texts to <file>
#
# PYTHON points to the environment to inspect (default: the project's .venv,
# in the Docker image: /opt/venv).
set -eu

PYTHON="${PYTHON:-.venv/bin/python}"
PIP_LICENSES="uvx --from pip-licenses==5.5.5 pip-licenses --python $PYTHON"

# Allowed licenses (substring match). Copyleft licenses (GPL, AGPL, LGPL …) are
# deliberately missing – packages using them need explicit approval first.
ALLOWED="MIT;BSD;Apache;ISC;PSF;Python Software Foundation;MPL-2.0;Mozilla Public License 2.0;Unlicense"

# Explicitly approved exceptions:
#   psycopg, psycopg-binary – LGPL-3.0, used unmodified (approved 2026-11-13)
APPROVED_EXCEPTIONS="psycopg psycopg-binary"

case "${1:-}" in
  check)
    # shellcheck disable=SC2086
    $PIP_LICENSES --partial-match --allow-only "$ALLOWED" \
      --ignore-packages domus-backend $APPROVED_EXCEPTIONS > /dev/null
    echo "Backend licenses OK"
    ;;
  notices)
    out="${2:?output file missing}"
    {
      echo "Domus – license notices for bundled Python packages"
      echo "==================================================="
      echo
      echo "psycopg and psycopg-binary are licensed under the LGPL-3.0 and are used"
      echo "unmodified. Source code: https://github.com/psycopg/psycopg"
      echo
      # pip-licenses prints "UNKNOWN" when a package has no NOTICE file
      $PIP_LICENSES --format=plain-vertical --with-license-file --with-notice-file \
        --no-license-path --ignore-packages domus-backend | grep -vx "UNKNOWN"
    } > "$out"
    echo "License notices written to $out"
    ;;
  *)
    echo "Usage: $0 check | notices <file>" >&2
    exit 2
    ;;
esac
