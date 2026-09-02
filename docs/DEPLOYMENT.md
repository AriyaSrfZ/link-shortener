# Deployment Guide

## Part 1 — Push this repo to GitHub (from VS Code)

The repo is already git-initialized locally with commits tagged `v0.1`
through `v0.4`. To push it to your own GitHub account:

### Option A — GitHub CLI (fastest)
```
gh auth login
gh repo create link-shortener --private --source=. --remote=origin --push
```
This creates the GitHub repo and pushes all commits and tags in one step.
Add `--push` again or run `git push --tags` if tags don't come along.

### Option B — Manual
1. On github.com, create a new empty repository named `link-shortener`
   (do NOT initialize it with a README/gitignore — this repo already has them).
2. In VS Code's terminal, from the project root:
   ```
   git remote add origin https://github.com/<your-username>/link-shortener.git
   git branch -M main
   git push -u origin main
   git push origin --tags
   ```

### Option C — VS Code's built-in Git UI
1. Open the Source Control panel (`Ctrl+Shift+G`).
2. Click "Publish Branch" — VS Code will prompt you to sign in to GitHub
   and create the remote repo for you.
3. Push tags separately from the terminal: `git push origin --tags`

### Ongoing workflow
After this initial push, every further change follows the same pattern
used for phases 1–4 in this repo:
```
git add -A
git commit -m "Describe what changed"
git tag v0.5   # bump version if it's a meaningful milestone
git push && git push origin --tags
```

## Part 2 — Deploying beyond your machine (VPS / domain)

This section is a guide for when you're ready to move off local-only.
The app itself needs no code changes — only configuration.

### 1. Provision a server
Any small VPS works (1 vCPU / 1GB RAM is enough for a personal link
shortener). Ubuntu 22.04/24.04 is a safe default.

### 2. Install prerequisites on the server
```
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx git
```

### 3. Clone your repo and set up the app
```
git clone https://github.com/<your-username>/link-shortener.git
cd link-shortener
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env   # set BASE_URL to your real domain, a strong SECRET_KEY, real admin password
```

### 4. Run the app as a background service (systemd)
Create `/etc/systemd/system/linkshortener.service`:
```ini
[Unit]
Description=Link Shortener FastAPI app
After=network.target

[Service]
User=<your-linux-user>
WorkingDirectory=/home/<your-linux-user>/link-shortener
Environment="PATH=/home/<your-linux-user>/link-shortener/venv/bin"
ExecStart=/home/<your-linux-user>/link-shortener/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```
Then:
```
sudo systemctl daemon-reload
sudo systemctl enable linkshortener
sudo systemctl start linkshortener
sudo systemctl status linkshortener
```

### 5. Put nginx in front (reverse proxy + your domain)
Create `/etc/nginx/sites-available/linkshortener`:
```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
Enable it and reload nginx:
```
sudo ln -s /etc/nginx/sites-available/linkshortener /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```
The redirect router already reads `X-Forwarded-For` for the real visitor
IP when running behind a proxy like this — no code change needed.

### 6. Add HTTPS (Let's Encrypt, free)
```
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```
Certbot edits the nginx config to add TLS and sets up auto-renewal.

### 7. Redeploying after changes
On the server:
```
cd link-shortener
git pull
source venv/bin/activate
pip install -r requirements.txt   # only if dependencies changed
sudo systemctl restart linkshortener
```

### 8. Moving from SQLite to PostgreSQL (optional, for higher traffic)
Only needed if click volume grows enough that SQLite's single-writer
model becomes a bottleneck. Change `DATABASE_URL` in `.env`:
```
DATABASE_URL=postgresql://user:password@localhost:5432/linkshortener
```
Add `psycopg2-binary` to `requirements.txt` and reinstall. No other code
changes — `app/database.py` was written to be database-agnostic.
