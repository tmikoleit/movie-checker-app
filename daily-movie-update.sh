#!/bin/bash
# Daily movie maintenance: update inventory, then auto-check wishlist
# Runs via cron at 7 AM on Mini PC
# Logs to: /var/log/movie-checker-daily.log (auto-rotated)

LOG_FILE="/var/log/movie-checker-daily.log"

# Function to log with timestamp
log_msg() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log_msg "=== Starting daily movie maintenance ==="

# Step 1: Update movie inventory from Plex Media folders
log_msg "Updating movie inventory from Plex Media folders on Mac..."
if ~/Documents/obsidian-vault/Scripts/update-movie-inventory.sh >> "$LOG_FILE" 2>&1; then
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
