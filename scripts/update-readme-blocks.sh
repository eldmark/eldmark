#!/usr/bin/env bash
# update-readme-blocks.sh
# Usage: ./scripts/update-readme-blocks.sh <readme-file> <block-name> <content>
#
# Replaces the content between <!-- <BLOCK>_START --> and <!-- <BLOCK>_END -->
# in the target file with the provided content, leaving the markers intact.

set -euo pipefail

README="${1:-README.md}"
BLOCK="${2}"     # e.g. CURRENTLY_WORKING or LATEST_COMMIT
CONTENT="${3}"   # New block content (may be multi-line)

START_MARKER="<!-- ${BLOCK}_START -->"
END_MARKER="<!-- ${BLOCK}_END -->"

if [[ ! -f "$README" ]]; then
  echo "ERROR: File '$README' not found." >&2
  exit 1
fi

if ! grep -qF "$START_MARKER" "$README"; then
  echo "ERROR: Marker '$START_MARKER' not found in '$README'." >&2
  exit 1
fi

if ! grep -qF "$END_MARKER" "$README"; then
  echo "ERROR: Marker '$END_MARKER' not found in '$README'." >&2
  exit 1
fi

# Use awk to replace everything between the two markers.
awk -v start="$START_MARKER" \
    -v end="$END_MARKER" \
    -v content="$CONTENT" '
  $0 == start { print; print content; skip=1; next }
  $0 == end   { skip=0 }
  !skip        { print }
' "$README" > "${README}.tmp"

mv "${README}.tmp" "$README"
echo "Updated block '$BLOCK' in '$README'."
