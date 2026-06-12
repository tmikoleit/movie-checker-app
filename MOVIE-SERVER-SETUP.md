# Movie Checker Web Server - Setup Guide

Web app hosted on Mini PC. Upload Blu-ray photos → get instant results on your phone.
**Access only via Tailscale** (no network exposure).

## Prerequisites

✅ SSH from Mini PC to NAS works (`ssh nas`)
✅ Docker running on Mini PC
✅ ANTHROPIC_API_KEY set on Mini PC

## Setup on Mini PC

### 1. Create app directory

```bash
ssh plexadmin@100.99.108.45

mkdir -p ~/docker/movie-server
cd ~/docker/movie-server
```

### 2. Copy files from Mac to Mini PC

On your Mac, copy these files to the Mini PC:

```bash
scp ~/Documents/obsidian-vault/Scripts/flask-movie-server.py plexadmin@100.99.108.45:~/docker/movie-server/
scp ~/Documents/obsidian-vault/Scripts/movie-server-template.html plexadmin@100.99.108.45:~/docker/movie-server/
scp ~/Documents/obsidian-vault/Scripts/Dockerfile.movie-server plexadmin@100.99.108.45:~/docker/movie-server/
scp ~/Documents/obsidian-vault/Scripts/requirements-movie-server.txt plexadmin@100.99.108.45:~/docker/movie-server/
scp ~/Documents/obsidian-vault/Scripts/docker-compose-movie-server.yml plexadmin@100.99.108.45:~/docker/movie-server/docker-compose.yml
```

### 3. Set up templates directory

On Mini PC:

```bash
cd ~/docker/movie-server
mkdir -p templates
mv movie-server-template.html templates/index.html
```

### 4. Verify .ssh/config on Mini PC

Make sure the SSH config has the `nas` host configured:

```bash
cat ~/.ssh/config | grep -A3 "Host nas"
```

Should show:
```
Host nas
    HostName 192.168.0.185
    User tmikoleit
    StrictHostKeyChecking accept-new
```

### 5. Start the container

```bash
cd ~/docker/movie-server
docker-compose up -d
```

Verify it's running:
```bash
docker-compose ps
docker-compose logs movie-server
```

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

## Features

### Photo Mode
Upload a photo of movie cases. Claude vision extracts titles and checks against your inventory.

### Type Mode
Manually enter movie titles one at a time. Perfect for quick checks while shopping.
- Add titles to a list with Edit/Remove buttons
- Submit all at once to get matching results
- Same three-tier output: Confirmed / Likely / Not Found

### Wishlist Mode
Build a wishlist of movies you want to buy.
- Enter title + check "4K Worthy" box (defaults to unchecked)
- Add/Edit/Remove items from the list
- Submit to save to `Obsidian/Data Hoarding/Wishlist.md`
- Format: `- Movie Name (4K)` or `- Movie Name (Blu-ray)`
- Automatically ignores duplicate submissions

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

```bash
# View logs
ssh plexadmin@100.99.108.45 "cd ~/docker/movie-server && docker-compose logs -f"

# Test API
curl http://100.99.108.45:5000/health  # Won't work without Tailscale
ssh plexadmin@100.99.108.45 "curl http://localhost:5000/health"
```

### Stop/Restart

```bash
ssh plexadmin@100.99.108.45 "cd ~/docker/movie-server && docker-compose restart"
```

## Troubleshooting

**"Could not load movie inventory from NAS"**
- Verify SSH: `ssh plexadmin@100.99.108.45 "ssh nas 'ls /volume1/obsidian'"`
- Check path exists: `/volume1/obsidian/Data Hoarding/Movie Inventory.md`

**"No photo uploaded" or file doesn't save**
- Check Docker has write permissions in temp directory
- Verify ANTHROPIC_API_KEY is set: `ssh plexadmin@100.99.108.45 "echo $ANTHROPIC_API_KEY"`

**Tailscale can't reach it**
- Verify firewall allows: `sudo ufw status numbered | grep 5000`
- Test from Mini PC: `curl http://localhost:5000`

## Maintenance

### Update Workflow (GitHub-Only)

⚠️ **CRITICAL:** Always deploy via `git pull` on Mini PC. Never use SCP or manual file copying.

**All changes follow this workflow:**
1. Edit files on Mac
2. `git add` → `git commit` → `git push` to GitHub
3. On Mini PC, pull and redeploy:
```bash
ssh plexadmin@100.99.108.45 "cd ~/movie-checker-app && git pull && docker-compose down && docker-compose up -d --build"
```

**Important:** 
- Template changes (HTML/CSS/JS) take effect after rebuild but update instantly in the container (volume-mounted)
- Python server changes require rebuild
- Docker config changes require rebuild

**Update movie inventory from NAS:**
```bash
~/Documents/obsidian-vault/Scripts/update-movie-inventory.sh
```

**View logs:**
```bash
ssh plexadmin@100.99.108.45 "cd ~/docker/movie-server && docker-compose logs -f"
```

## Automated Updates & Wishlist Management

### Auto-Remove from Wishlist (95%+ Matches)

The app can automatically detect when a wishlist item matches an owned movie at 95%+ confidence and remove it from the wishlist.

#### Set Up Cron Job on Mini PC

1. The update script is in the GitHub repo at `update-movie-reference.sh`. It will be pulled via `git pull`.

2. Add to crontab on Mini PC (runs daily at 2 AM):
```bash
ssh plexadmin@100.99.108.45 "crontab -e"
```

Add this line:
```
0 2 * * * /home/plexadmin/movie-checker-app/update-movie-reference.sh >> /tmp/movie-checker-cron.log 2>&1
```

3. Verify cron job:
```bash
ssh plexadmin@100.99.108.45 "crontab -l | grep update-movie"
```

4. Check logs:
```bash
ssh plexadmin@100.99.108.45 "tail -f /tmp/movie-checker-update.log"
```

#### Manual Trigger

To manually run the wishlist check:
```bash
curl -X POST http://100.99.108.45:5000/api/auto-check-wishlist
```

Response includes:
- `removed`: List of movies removed (95%+ matches)
- `checked`: Total wishlist items checked
- `success`: Whether the update succeeded
