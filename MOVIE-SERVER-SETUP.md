# Movie Checker Web Server - Setup Guide

Web app hosted on Mini PC. Upload Blu-ray photos → get instant results on your phone.
**Access only via Tailscale** (no network exposure).

## Prerequisites

✅ SSH from Mini PC to NAS works (`ssh nas`)
✅ Docker running on Mini PC
✅ ANTHROPIC_API_KEY set on Mini PC

## Setup on Mini PC

### Initial Setup (One Time)

```bash
ssh plexadmin@100.99.108.45

# Clone the GitHub repo
git clone https://github.com/tmikoleit/movie-checker-app.git ~/movie-checker-app
cd ~/movie-checker-app

# Create .env file with API key
echo "ANTHROPIC_API_KEY=your-key-here" > .env

# Start the container
docker-compose up -d --build
```

Verify it's running:
```bash
docker-compose ps
docker-compose logs movie-server | tail -20
```

### Verify SSH to NAS Works

```bash
ssh plexadmin@100.99.108.45 "ssh nas 'cat /volume1/Obsidian/Data\ Hoarding/Movie\ Inventory.md' | head -5"
```

Should show the beginning of your movie list.

## Configure Tailscale Firewall

Restrict port 5000 to Tailscale only (no direct network access).

### Via Tailscale Admin Console

1. Go to https://login.tailscale.com/admin/acls
2. Add a rule:

```json
{
  "acls": [
    {
      "action": "accept",
      "src": ["tag:home"],
      "dst": ["100.99.108.45:5000"]
    }
  ]
}
```

This allows all home devices via Tailscale to access the service.

### Via UFW on Mini PC (Backup)

```bash
sudo ufw allow in on tailscale0 to 127.0.0.1 port 5000
sudo ufw deny in to any port 5000
sudo ufw reload
```

## Features & Endpoints

### Photo Mode (`POST /api/compare`)
Upload a photo of movie cases. Claude vision extracts titles and checks against your inventory.
- **Output:** Three-tier matching (Confirmed / Likely / Not Found)
- **Confirmed:** 85%+ match confidence
- **Likely:** 50-85% match (review carefully)
- **Not Found:** Below 50% match

### Type Mode (`POST /api/compare-text`)
Manually enter movie titles one at a time. Perfect for quick checks while shopping.
- Add titles to a list with Edit/Remove buttons
- Submit all at once to get matching results
- Same three-tier output as Photo Mode

### Wishlist Mode (`POST /api/save-wishlist`)
Build a wishlist of movies you want to buy.
- Enter title + check "4K Worthy" box (defaults to unchecked)
- Add/Edit/Remove items from the list
- Submit to save to `/volume1/Obsidian/Data Hoarding/Wishlist.md`
- Format: `- Movie Name (4K)` or `- Movie Name (Blu-ray)`
- Automatically ignores duplicate submissions

### Auto-Check Wishlist (`POST /api/auto-check-wishlist`)
Automatically removes wishlist items that match owned movies at 95%+ confidence.
- Runs daily at 7 AM (scheduled via cron)
- Can be triggered manually anytime
- Logs all activity with timestamps
- See "Automated Updates & Wishlist Management" section below

## Usage

### From Your Phone

1. Connect to Tailscale on phone
2. Open browser: `http://100.99.108.45:5000`
3. Choose mode:
   - **Photo:** Take a photo of Blu-rays
   - **Type:** Enter titles manually
   - **Wishlist:** Build your wishlist
4. Get instant results or save wishlist

### Check Status

**View live logs:**
```bash
ssh plexadmin@100.99.108.45 "cd ~/movie-checker-app && docker-compose logs -f movie-server"
```

**View last 50 lines:**
```bash
ssh plexadmin@100.99.108.45 "cd ~/movie-checker-app && docker-compose logs movie-server | tail -50"
```

**Filter for timestamped events (auto-check runs):**
```bash
ssh plexadmin@100.99.108.45 "cd ~/movie-checker-app && docker-compose logs movie-server | grep '\['"
```

**Test health endpoint:**
```bash
ssh plexadmin@100.99.108.45 "curl http://localhost:5000/health"
```

### Stop/Restart

```bash
ssh plexadmin@100.99.108.45 "cd ~/movie-checker-app && docker-compose restart"
```

## Troubleshooting

**"Could not load movie inventory from NAS"**
- Check logs for details: `docker-compose logs movie-server | grep ERROR`
- Verify SSH works: `ssh plexadmin@100.99.108.45 "ssh nas 'ls /volume1/Obsidian/Data\ Hoarding/Movie\ Inventory.md'"`
- Verify file path is correct (case-sensitive): `/volume1/Obsidian/Data Hoarding/Movie Inventory.md`

**"No photo uploaded" or API errors**
- Check Docker container is running: `docker-compose ps`
- Verify ANTHROPIC_API_KEY is set: `ssh plexadmin@100.99.108.45 "echo $ANTHROPIC_API_KEY"`
- View error logs: `docker-compose logs movie-server | grep -E '(ERROR|Exception)'`

**Auto-check didn't run at scheduled time**
- Verify cron job exists: `ssh plexadmin@100.99.108.45 "crontab -l"`
- Check if Flask container is running: `docker-compose ps`
- Manually trigger to test: `curl -X POST http://localhost:5000/api/auto-check-wishlist`
- View cron logs (if available): system logs on Mini PC

**Wishlist not updating**
- Verify NAS SSH access: `ssh plexadmin@100.99.108.45 "ssh nas 'cat /volume1/Obsidian/Data\ Hoarding/Wishlist.md'"`
- Check logs for SSH write errors: `docker-compose logs movie-server | grep -i "write\|ssh"`
- Verify `/volume1/Obsidian/Data Hoarding/` directory exists and is writable

**Tailscale can't reach the app**
- Test from Mini PC: `curl http://localhost:5000`
- Verify firewall: `sudo ufw status numbered | grep 5000`
- Check Tailscale connection on phone: Settings → Connected?

## Maintenance

### Update Workflow (GitHub-Only)

⚠️ **CRITICAL:** Always deploy via `git pull` on Mini PC. **Never use SCP or manual file copying.**

**All code changes follow this workflow:**
1. Edit files on Mac in `~/Documents/movie-checker-app/`
2. Run: `git add`, `git commit`, `git push` to GitHub
3. On Mini PC, deploy with:
```bash
ssh plexadmin@100.99.108.45 "cd ~/movie-checker-app && git pull && docker-compose down && docker-compose up -d --build"
```

**What requires rebuild:**
- ✅ Python server changes (`flask-movie-server.py`) → **requires rebuild**
- ✅ Docker config changes (`Dockerfile.movie-server`, `docker-compose.yml`) → **requires rebuild**
- ✅ Dependencies changes (`requirements-movie-server.txt`) → **requires rebuild**
- ✅ Template changes (`templates/index.html`) → **no rebuild needed** (volume-mounted, updates instantly after docker-compose restart)

**Typical deployment:**
```bash
ssh plexadmin@100.99.108.45 "cd ~/movie-checker-app && git pull && docker-compose down && docker-compose up -d --build"
```

## Automated Updates & Wishlist Management

### Auto-Check Wishlist Feature

The `/api/auto-check-wishlist` endpoint automatically removes wishlist items that match owned movies at 95%+ confidence. This runs on a scheduled cron job daily at **7 AM** but can also be triggered manually anytime.

#### How It Works

1. **Load inventory**: Reads `/volume1/Obsidian/Data Hoarding/Movie Inventory.md` from NAS
2. **Check wishlist**: Reads `/volume1/Obsidian/Data Hoarding/Wishlist.md` from NAS
3. **Compare**: Fuzzy-matches each wishlist item against owned movies
4. **Remove matches**: Any wishlist item with 95%+ match confidence is removed
5. **Update file**: Writes the updated wishlist back to NAS (keeps unmatched items)
6. **Log result**: Records the entire operation with timestamps and details

#### Trigger Manually (Anytime)

Test the endpoint or run it on-demand:
```bash
curl -X POST http://100.99.108.45:5000/api/auto-check-wishlist
```

Or from Mini PC:
```bash
ssh plexadmin@100.99.108.45 "curl -X POST http://localhost:5000/api/auto-check-wishlist"
```

Response example:
```json
{
  "success": true,
  "message": "Removed 2 movies from wishlist",
  "removed": [
    {"title": "Argo", "matched": "Argo", "confidence": 100},
    {"title": "The Matrix", "matched": "The Matrix (1999)", "confidence": 98}
  ],
  "checked": 6
}
```

#### Current Cron Schedule

Runs **daily at 7 AM** on Mini PC:
```bash
ssh plexadmin@100.99.108.45 "crontab -l"
```

Should show:
```
0 7 * * * curl -s -X POST http://localhost:5000/api/auto-check-wishlist
```

#### Understanding the Logs

Every auto-check run logs events with timestamps. Watch for:

**Successful run:**
```
[2026-06-12 07:00:02] === Starting wishlist auto-check ===
[2026-06-12 07:00:02] Loaded 158 movies from inventory
[2026-06-12 07:00:02] Checking 6 wishlist items for 95%+ matches
[2026-06-12 07:00:02] REMOVE: 'Argo' → 'Argo' (100%)
[2026-06-12 07:00:02] SUCCESS: Removed 1 movies. 5 items remain in wishlist.
```

**No matches found:**
```
[2026-06-12 07:00:02] === Starting wishlist auto-check ===
[2026-06-12 07:00:02] Loaded 158 movies from inventory
[2026-06-12 07:00:02] Checking 6 wishlist items for 95%+ matches
[2026-06-12 07:00:02] No 95%+ matches found. All 6 items kept.
```

**Error cases:**
```
[2026-06-12 07:00:02] ERROR: Could not load movie inventory from NAS
[2026-06-12 07:00:02] ERROR: Failed to read wishlist: Connection timed out
[2026-06-12 07:00:02] ERROR: SSH write failed: Permission denied
```

#### View Recent Auto-Check Runs

**Show last 10 auto-check operations:**
```bash
ssh plexadmin@100.99.108.45 "cd ~/movie-checker-app && docker-compose logs movie-server | grep '\[' | tail -10"
```

**Show only errors:**
```bash
ssh plexadmin@100.99.108.45 "cd ~/movie-checker-app && docker-compose logs movie-server | grep ERROR"
```

**Watch logs in real-time (wait for 7 AM run):**
```bash
ssh plexadmin@100.99.108.45 "cd ~/movie-checker-app && docker-compose logs -f movie-server | grep '\['"
```

#### Log Storage & Rotation

- Logs are stored by Docker's JSON file driver
- **Max size per file:** 10 MB
- **Keeps:** 3 rotated files (30 MB total)
- Oldest logs auto-delete when size limit is exceeded
- Daily runs generate ~2 KB of logs (thousands of runs per 10 MB)

#### Troubleshooting Auto-Check

**If a scheduled run didn't happen:**
1. Check if cron job exists: `crontab -l`
2. Verify Flask is running: `docker-compose ps`
3. Check for errors: `docker-compose logs movie-server | grep ERROR`
4. Test manually: `curl -X POST http://localhost:5000/api/auto-check-wishlist`

**If wishlist wasn't updated:**
- Check NAS write permissions: `ssh nas ls -la /volume1/Obsidian/Data\ Hoarding/`
- Look for SSH errors in logs: `docker-compose logs movie-server | grep -i ssh`
- Verify SSH key works: `ssh nas 'echo OK'`

**If you want to change the schedule:**
```bash
ssh plexadmin@100.99.108.45 "crontab -e"
# Edit the cron line (currently "0 7 * * *" = 7 AM daily)
# Save and exit
```
