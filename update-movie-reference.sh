#!/bin/bash
# Update movie inventory and auto-remove 95%+ matches from wishlist
# Run via cron on Mini PC: 0 2 * * * /home/plexadmin/movie-checker-app/update-movie-reference.sh

set -e

LOG_FILE="/tmp/movie-checker-update.log"
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

echo "[$TIMESTAMP] Starting movie reference update..." >> "$LOG_FILE"

# Call the auto-check-wishlist endpoint
RESULT=$(curl -s -X POST http://localhost:5000/api/auto-check-wishlist)
echo "[$TIMESTAMP] Auto-check result: $RESULT" >> "$LOG_FILE"

# Extract success status
if echo "$RESULT" | grep -q '"success"'; then
  echo "[$TIMESTAMP] ✓ Successfully updated wishlist" >> "$LOG_FILE"
else
  echo "[$TIMESTAMP] ✗ Auto-check may have encountered an issue" >> "$LOG_FILE"
fi

echo "[$TIMESTAMP] Update complete" >> "$LOG_FILE"
