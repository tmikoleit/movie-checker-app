#!/bin/bash
# Daily movie maintenance: update inventory, then auto-check wishlist
# Runs via cron at 7 AM on Mini PC
# Logs to: ~/movie-checker-app/logs/daily.log

LOG_DIR="$HOME/movie-checker-app/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/daily.log"
MAX_LOG_SIZE=$((10 * 1024 * 1024))  # 10MB
ARCHIVE_THRESHOLD=$((50 * 1024 * 1024))  # 50MB for archives

# Function to log with timestamp
log_msg() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to rotate logs if they get too large
rotate_logs() {
    if [ -f "$LOG_FILE" ] && [ $(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE") -gt $MAX_LOG_SIZE ]; then
        TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
        mv "$LOG_FILE" "$LOG_DIR/daily.$TIMESTAMP.log"
        log_msg "Log rotated: daily.$TIMESTAMP.log"

        # Clean up old archives (keep only 5 most recent)
        cd "$LOG_DIR"
        ls -t daily.*.log 2>/dev/null | tail -n +6 | xargs -r rm
    fi
}

rotate_logs

log_msg "=== Starting daily movie maintenance ==="

# Step 1: Update movie inventory from NAS Plex Media folder
log_msg "Updating movie inventory from NAS Plex Media folder..."
if ~/movie-checker-app/update-movie-inventory.sh >> "$LOG_FILE" 2>&1; then
    log_msg "✓ Inventory updated successfully"
else
    log_msg "✗ ERROR: Inventory update failed"
    exit 1
fi

# Step 2: Auto-check wishlist against updated inventory
log_msg "Checking wishlist for newly acquired movies..."
RESPONSE=$(curl -s -X POST http://localhost:5000/api/auto-check-wishlist)
if echo "$RESPONSE" | grep -q '"success"'; then
    log_msg "✓ Wishlist auto-check complete"
    # Log the result details
    REMOVED=$(echo "$RESPONSE" | grep -o '"removed":\[\([^]]*\)\]' | grep -c '"title"' || echo "0")
    CHECKED=$(echo "$RESPONSE" | grep -o '"checked":[0-9]*' | grep -o '[0-9]*')
    log_msg "  Checked $CHECKED items, removed $REMOVED matches"
else
    log_msg "✗ ERROR: Wishlist auto-check failed"
    log_msg "  Response: $RESPONSE"
    exit 1
fi

log_msg "=== Daily movie maintenance finished successfully ==="
