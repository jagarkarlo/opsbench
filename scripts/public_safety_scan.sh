#!/usr/bin/env bash
set -euo pipefail

# Scan tracked text files only; ignored local environments are not release inputs.
files=$(git grep -Il . -- ':!*.png' ':!*.jpg' ':!*.jpeg' ':!*.gif' ':!*.webp' ':!tests/**' ':!scripts/public_safety_scan.sh' || true)
if [[ -z "$files" ]]; then
  exit 0
fi

patterns='(BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9_]{20,}|glpat-[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{20,}|accountKey[[:space:]]*:[[:space:]]*[^"{[:space:]]{20,}|(client_secret|api[_-]?key|password|token)[[:space:]]*[:=][[:space:]]*["'"'"'][^"'"'"']{12,}["'"'"'])'
if git grep -nE "$patterns" -- $files; then
  echo "Public safety scan failed: credential-like content found in tracked text." >&2
  exit 1
fi

disallowed='(sick\.com|sickcn\.net|dlearner|mosaicrest|waki\.de|zscaler|cloudproxy|deagx)'
if git grep -nEi "$disallowed" -- $files; then
  echo "Public safety scan failed: employer-specific identifier found in tracked text." >&2
  exit 1
fi

echo "Public safety scan passed."
