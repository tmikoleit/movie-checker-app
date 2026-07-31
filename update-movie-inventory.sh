#!/bin/bash
# Update movie inventory by scanning NAS Plex Media folder
# Generates Movie Inventory.md on the NAS with all owned movies
# Run from Mini PC - no Mac dependency

INVENTORY_PATH="/volume1/Obsidian/Data Hoarding/Movie Inventory.md"
PLEX_FOLDER="/volume1/Plex Media/Movies"
BACKUP_DIR="$HOME/movie-checker-app/logs/backups"

mkdir -p "$BACKUP_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting movie inventory update from NAS..."

# Backup existing file before modification
if ssh nas "test -f '$INVENTORY_PATH'"; then
    TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
    BACKUP_FILE="$BACKUP_DIR/Movie\ Inventory.md.update.$TIMESTAMP.backup"
    ssh nas "cat '$INVENTORY_PATH'" > "$BACKUP_FILE"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backup: $INVENTORY_PATH → $BACKUP_FILE"
fi

# Get list of movies from Plex folder, sort alphabetically
MOVIES=$(ssh nas "ls -1 '$PLEX_FOLDER' 2>/dev/null | grep -v '^@' | grep -v '^\.' | sort" 2>&1)

if [ -z "$MOVIES" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Could not read Plex Media folder"
    exit 1
fi

# Count total movies
TOTAL=$(echo "$MOVIES" | wc -l)
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

# Remove old file and write with proper permissions (set umask on NAS side)
ssh nas "rm -f '$INVENTORY_PATH' && umask 0002 && cat > '$INVENTORY_PATH'" <<< "$INVENTORY_CONTENT"

if [ $? -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✓ Inventory updated successfully ($TOTAL movies)"
    exit 0
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✗ ERROR: Failed to write inventory to NAS"
    exit 1
fi
