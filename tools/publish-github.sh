#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Run locally, after reviewing source. Requires gh CLI authenticated as speccy88.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
REPO="speccy88/microblocks-zephyr"
VISIBILITY="${1:-}"
if [[ "$VISIBILITY" != "public" && "$VISIBILITY" != "private" ]]; then
  echo "Usage: tools/publish-github.sh public|private" >&2
  echo "Requires gh auth login and git user.name/user.email to be set." >&2
  exit 2
fi
command -v git >/dev/null || { echo 'git not found' >&2; exit 1; }
command -v gh >/dev/null || { echo 'GitHub CLI (gh) not found; see https://cli.github.com/' >&2; exit 1; }
gh auth status >/dev/null || { echo 'Authenticate using gh auth login' >&2; exit 1; }
ACCOUNT="$(gh api user -q .login)"
[[ "$ACCOUNT" == 'speccy88' ]] || { echo "Authenticated as $ACCOUNT, not speccy88" >&2; exit 1; }
python3 tools/validate.py
if [[ ! -d .git ]]; then
  git init -b main
fi
if ! git rev-parse HEAD >/dev/null 2>&1; then
  git add .
  git commit -m 'Initial multi-board Zephyr and MicroBlocks framework scaffolding'
fi
if [[ -n "$(git status --porcelain)" ]]; then
  echo 'Uncommitted changes found. Commit or stash them before publishing.' >&2
  exit 1
fi
if gh repo view "$REPO" >/dev/null 2>&1; then
  # Only push to a truly empty repository: never overwrite user work.
  if [[ -n "$(git ls-remote --heads "https://github.com/$REPO.git")" ]]; then
    echo "Repository $REPO already has commits. No push attempted; merge manually." >&2
    exit 1
  fi
  if ! git remote get-url origin >/dev/null 2>&1; then
    git remote add origin "https://github.com/$REPO.git"
  fi
  git push -u origin main
else
  # Creating a new repository is a privileged action carried out by the user.
  gh repo create "$REPO" --"$VISIBILITY" \
    --description 'Portable MicroBlocks SmallVM and Arduino API on Zephyr RTOS' \
    --source . --remote origin --push
fi
echo "Published https://github.com/$REPO"
