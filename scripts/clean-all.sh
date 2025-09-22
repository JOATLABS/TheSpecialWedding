#!/usr/bin/env bash
set -euo pipefail

echo "[clean-all] Starting full project cache clean" 

# Node / Next.js artifacts
rm -rf .next || true
rm -rf node_modules/.cache || true
rm -rf node_modules/.vite || true
rm -rf node_modules/.turbo || true

# Playwright & test artifacts
rm -rf playwright-report || true
rm -rf test-results || true
rm -rf coverage || true

# TypeScript build info
find . -type f -name '*.tsbuildinfo' -delete || true

# Log files (keep directory structure)
find logs -type f -maxdepth 1 -name '*.log' -exec truncate -s 0 {} + 2>/dev/null || true

# Python caches (ignore permission errors)
find . -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
find . -type f -name '*.pyc' -delete 2>/dev/null || true

# Misc caches
rm -rf .turbo || true
rm -rf .cache || true

# Optional npm cache (uncomment if needed)
# npm cache clean --force

# VSCode TS server cache hint (not destructive)
mkdir -p .vscode 2>/dev/null || true
echo "// TS server restart hint $(date -u +%Y-%m-%dT%H:%M:%SZ)" > .vscode/.ts-restart-trigger 2>/dev/null || true

if [[ "${1:-}" == "--deep" ]]; then
  echo "[clean-all] Performing deep clean (node_modules + npm cache)"
  rm -rf node_modules || true
  npm cache clean --force || true
fi

# Git clean suggestion (not auto-run for safety)
cat <<EOF
[clean-all] Done.
If you also want to remove untracked files run: git clean -fdx (DANGEROUS)
Deep clean (include node_modules + npm cache): ./scripts/clean-all.sh --deep
Next steps:
  npm ci
  npm run dev (or npm run rebuild:fresh for production build)
EOF
