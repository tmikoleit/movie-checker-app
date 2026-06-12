#!/bin/bash
# Daily movie maintenance: update inventory, then auto-check wishlist
# Runs via cron at 7 AM

set -e

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === Starting daily movie maintenance ==="

# Step 1: Update movie inventory from Plex Media folders
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Updating movie inventory from Plex..."
~/Documents/obsidian-vault/Scripts/update-movie-inventory.sh
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✓ Inventory updated"

# Step 2: Auto-check wishlist against updated inventory
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Checking wishlist for newly acquired movies..."
curl -s -X POST http://localhost:5000/api/auto-check-wishlist > /dev/null
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✓ Wishlist auto-check complete"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === Daily movie maintenance finished ==="
