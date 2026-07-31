#!/bin/bash
# Update movie inventory by scanning NAS Plex Media folder
# Generates Movie Inventory.md on the NAS with all owned movies
# Run from Mini PC - no Mac dependency

INVENTORY_PATH="/volume1/Obsidian/Data Hoarding/Movie Inventory.md"
PLEX_FOLDER="/volume1/Plex Media/Movies"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting movie inventory update from NAS..."
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Note: Source data in $PLEX_FOLDER is the backup"

# Find all movie folders recursively (one level deep in category folders)
# Plex structure: Movies/[Category]/[Movie Folder]
MOVIES=$(ssh nas "find '$PLEX_FOLDER' -maxdepth 2 -mindepth 2 -type d ! -name '@eaDir' ! -name '.*' -exec basename {} \; | sort" 2>&1)

if [ -z "$MOVIES" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Could not read Plex Media folder"
    exit 1
fi

# Count total movies
TOTAL=$(echo "$MOVIES" | grep -v '^$' | wc -l)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Found $TOTAL movies in Plex Media folder"

# Build the inventory markdown file
INVENTORY_CONTENT="# Movie Inventory

Last updated: $(date '+%Y-%m-%d %H:%M:%S')
Total movies: $TOTAL

## All Owned Movies

"

while IFS= read -r movie; do
    # Skip empty lines and system folders
    [ -z "$movie" ] && continue
    [[ "$movie" =~ ^[\.\@] ]] && continue

    # Remove trailing/leading whitespace
    movie=$(echo "$movie" | xargs)

    # Add to inventory (folder name is the title)
    INVENTORY_CONTENT+="- $movie"$'\n'
done <<< "$MOVIES"

# Write to temp file in /tmp (not synced), then atomically move
TEMP_PATH="/tmp/Movie_Inventory.md.tmp.$$"
ssh nas "umask 0002 && cat > '$TEMP_PATH'" <<< "$INVENTORY_CONTENT"

if [ $? -ne 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✗ ERROR: Failed to write temporary file"
    exit 1
fi

# Atomically move temp file to final location (single filesystem operation)
ssh nas "mv -f '$TEMP_PATH' '$INVENTORY_PATH'"

if [ $? -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✓ Inventory updated successfully ($TOTAL movies)"
    exit 0
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✗ ERROR: Failed to move inventory file"
    ssh nas "rm -f '$TEMP_PATH'"  # Cleanup temp file
    exit 1
fi
