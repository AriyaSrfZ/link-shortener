# Deployment Guide (VPS / Production)

This guide covers moving the app from your local machine to a real
server with a domain. For pushing the repo to GitHub, see
[GITHUB_SETUP.md](GITHUB_SETUP.md) instead.

The app itself needs no code changes to deploy — only configuration.

## 1. Provision a server
Any small VPS works (1 vCPU / 1GB RAM is enough for a personal link
shortener). Ubuntu 22.04/24.04 is a safe default.

## 2. Install prerequisites on the server
```
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx git
```

## 3. Clone your repo and set up the app
```
git clone https://github.com/AriyaSrfZ/link-shortener.git
cd link-shortener
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env   # set BASE_URL to your real domain, a strong SECRET_KEY, real admin password
```

## 4. Run the app as a background service (systemd)

First, find your Linux username on the server:
```
whoami
```
Note the output (e.g. `ariya`) — you'll use it below.

Generate the service file directly with one command. Replace `ariya`
on the first line with your actual `whoami` output, then run the whole
block as-is:
```
export LU=ariya
sudo bash -c "cat > /etc/systemd/system/linkshortener.service" << EOF
[Unit]
Description=Link Shortener FastAPI app
After=network.target

[Service]
User=$LU
WorkingDirectory=/home/$LU/link-shortener
Environment="PATH=/home/$LU/link-shortener/venv/bin"
ExecStart=/home/$LU/link-shortener/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF
```

Then start it:
```
sudo systemctl daemon-reload
sudo systemctl enable linkshortener
sudo systemctl start linkshortener
sudo systemctl status linkshortener
```

## 5. Put nginx in front (reverse proxy + your domain)
Create `/etc/nginx/sites-available/linkshortener`. Replace
`yourdomain.com` with your actual domain name:
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

## 6. Add HTTPS (Let's Encrypt, free)
Replace `yourdomain.com` with your actual domain:
```
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```
Certbot edits the nginx config to add TLS and sets up auto-renewal.

## 7. Redeploying after changes
On the server:
```
cd link-shortener
git pull
source venv/bin/activate
pip install -r requirements.txt   # only if dependencies changed
sudo systemctl restart linkshortener
```

## 8. Moving from SQLite to PostgreSQL (optional, for higher traffic)
Only needed if click volume grows enough that SQLite's single-writer
model becomes a bottleneck. Change `DATABASE_URL` in `.env`:
```
DATABASE_URL=postgresql://user:password@localhost:5432/linkshortener
```
Add `psycopg2-binary` to `requirements.txt` and reinstall. No other code
changes — `app/database.py` was written to be database-agnostic.
