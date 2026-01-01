#!/usr/bin/env bash
# Build the anonymous single-commit snapshot of the current HEAD and print the
# push command.  It never pushes by itself.
#
#   bash tools/publish_snapshot.sh            # build and check
#   bash tools/publish_snapshot.sh --push     # build, check, then push
#
# The snapshot reuses HEAD's tree object, so its content is identical to the
# working repo by construction: no file can be missed.  It has no parent, so
# the real commit history and the author identity never reach the public copy.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
REMOTE=${REMOTE:-origin}
BRANCH=${BRANCH:-main}

if [ -n "$(git status --porcelain)" ]; then
  echo "working tree is dirty; commit first" >&2; exit 1
fi

TREE=$(git rev-parse HEAD^{tree})
SNAP=$(GIT_AUTHOR_NAME=anonymous GIT_AUTHOR_EMAIL=anon@example.org \
       GIT_COMMITTER_NAME=anonymous GIT_COMMITTER_EMAIL=anon@example.org \
       GIT_AUTHOR_DATE="2026-01-01T00:00:00 +0000" \
       GIT_COMMITTER_DATE="2026-01-01T00:00:00 +0000" \
       git commit-tree "$TREE" -m "project page")

echo "snapshot   $SNAP"
echo "files      $(git ls-tree -r --name-only "$SNAP" | wc -l)"
git diff --quiet HEAD "$SNAP" && echo "content    identical to HEAD" || { echo "content DIFFERS from HEAD" >&2; exit 1; }

HITS=$(git grep -I -l -iE "[r]ongxuan|[n]ortheastern|/[h]ome/" "$SNAP" -- . || true)
if [ -n "$HITS" ]; then
  echo "IDENTITY STRINGS in the snapshot, refusing:" >&2; echo "$HITS" >&2; exit 1
fi
echo "identity   0 text hits"

# git grep -I skips binaries, so a PDF or an image can carry a name past the
# check above.  Export the snapshot and run the real gate over it, which reads
# PDFs, archives and NUL-padded blobs.  Skip with SKIP_BINARY_SCAN=1 only when
# the snapshot has no new binary since the last full scan.
GATE=${IDENTITY_GATE:-../../idea/lewm-f/wm-horizon/tools/merge_gates/identity_gate.py}
GATE=$(readlink -f "$GATE" 2>/dev/null || echo "$GATE")   # absolute: the scan runs from a temp dir
if [ "${SKIP_BINARY_SCAN:-0}" = "1" ]; then
  echo "identity   binary scan SKIPPED by request"
elif [ ! -f "$GATE" ]; then
  echo "identity gate not found at $GATE; set IDENTITY_GATE or SKIP_BINARY_SCAN=1" >&2; exit 1
else
  TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
  git archive "$SNAP" | tar -x -C "$TMP"
  WAIVERS=$(readlink -f tools/identity_waivers_page.tsv 2>/dev/null || true)
  GATE_ARGS=(.); [ -n "$WAIVERS" ] && [ -f "$WAIVERS" ] && GATE_ARGS+=(--waivers "$WAIVERS")
  if ! (cd "$TMP" && python3 "$GATE" "${GATE_ARGS[@]}" >"$TMP/.gate.log" 2>&1); then
    echo "IDENTITY GATE FAILED on the snapshot contents, refusing:" >&2
    grep -E "identity hits|^\s*\[" "$TMP/.gate.log" >&2 || cat "$TMP/.gate.log" >&2
    exit 1
  fi
  echo "identity   $(grep -m1 'files and archive members scanned' "$TMP/.gate.log" | sed 's/.*scanned: //; s/;.*//') blobs scanned, 0 hits"
fi

if [ "${1:-}" = "--push" ]; then
  git push --force "$REMOTE" "$SNAP":refs/heads/$BRANCH
  echo "pushed to $REMOTE/$BRANCH"
else
  echo
  echo "to publish:  git push --force $REMOTE $SNAP:refs/heads/$BRANCH"
  echo "or re-run:   bash tools/publish_snapshot.sh --push"
fi
