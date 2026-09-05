# WSL + Cloudflare Tunnel Setup (aria-haross.ir)

This guide gets the app running on your own WSL machine and reachable
by anyone on the internet at `https://aria-haross.ir`, using Cloudflare
Tunnel. No router configuration, no port forwarding, no public IP
needed. Your domain currently has no nameservers set, which makes this
easier since there is nothing to undo first.

## Phase 1: Run the app in WSL

If WSL is not installed yet, open PowerShell as Administrator on Windows:
```
wsl --install
```
Reboot if prompted, then open "Ubuntu" from the Start menu and finish
the first-run username/password setup.

Inside the Ubuntu (WSL) terminal:
```
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip git curl
git clone https://github.com/AriyaSrfZ/link-shortener.git
cd link-shortener
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:
```
nano .env
```
Set:
- `SECRET_KEY` — generate one: `python3 -c "import secrets; print(secrets.token_hex(32))"`
- `ADMIN_USERNAME` / `ADMIN_PASSWORD` — pick a real password, not the default
- `BASE_URL=https://aria-haross.ir`

Save (`Ctrl+O`, `Enter`, `Ctrl+X`), then start the app:
```
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Confirm it works locally first: open `http://localhost:8000/dashboard`
in your Windows browser. WSL2 forwards `localhost` to Windows
automatically, so this should load without extra setup. Leave this
terminal running and open a second WSL terminal tab for the next steps.

## Phase 2: Point the domain at Cloudflare

1. Create a free account at https://dash.cloudflare.com/sign-up
2. Click "Add a Site", enter `aria-haross.ir`, choose the **Free** plan.
3. Cloudflare scans for existing DNS records (there should be none) and
   shows you two nameservers, something like:
   ```
   aida.ns.cloudflare.com
   walt.ns.cloudflare.com
   ```
   Yours will be different — copy the exact two shown to you.
4. Go to https://new.nic.ir/panel/dashboard/domains/my_domains, open
   `aria-haross.ir`, find the nameserver (NS) settings, and replace
   whatever is there with the two Cloudflare nameservers from step 3.
5. Save. Back in Cloudflare, click "Check nameservers" (or just wait —
   it checks automatically). Propagation for `.ir` domains can take a
   few hours, sometimes up to a day. The Cloudflare dashboard shows
   "Active" once it's done — nothing else works until this finishes.

## Phase 3: Cloudflare Tunnel (makes WSL publicly reachable)

Install `cloudflared` in WSL:
```
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb
```

Log in and authorize your domain:
```
cloudflared tunnel login
```
This prints a URL. WSL usually can't open a GUI browser directly —
copy the full URL and paste it into your Windows browser, log into
Cloudflare, and select `aria-haross.ir` when prompted. This saves a
certificate to `~/.cloudflared/cert.pem`.

Create the tunnel:
```
cloudflared tunnel create linkshortener
```
This prints a Tunnel ID (a long UUID) and saves a credentials file at
`~/.cloudflared/<TUNNEL_ID>.json`. Copy the Tunnel ID somewhere — you
need it next.

Create the tunnel config. Run this as one block, replacing
`YOUR_TUNNEL_ID` with the ID from the previous step:
```
export TID=YOUR_TUNNEL_ID
mkdir -p ~/.cloudflared
cat > ~/.cloudflared/config.yml << EOF
tunnel: $TID
credentials-file: /home/$(whoami)/.cloudflared/$TID.json

ingress:
  - hostname: aria-haross.ir
    service: http://localhost:8000
  - service: http_status:404
EOF
```

Point the domain at the tunnel (creates the DNS record in Cloudflare
automatically):
```
cloudflared tunnel route dns linkshortener aria-haross.ir
```

Run the tunnel:
```
cloudflared tunnel run linkshortener
```
Leave this running in its own terminal tab, alongside the `uvicorn`
tab from Phase 1. Both need to stay running for the site to work.

## Phase 4: Test it like a real visitor

1. In your browser, go to `https://aria-haross.ir/dashboard` and log in
   with the admin credentials you set in `.env`.
2. Create a link. Its short URL now shows as `https://aria-haross.ir/r/<code>`.
3. Send that link to your phone (over cellular data, not your home
   WiFi, so it's a genuinely external request) and open it.
4. It should redirect to your destination URL with the UTM parameters
   attached.
5. Back in the dashboard, open that link's detail page — the click
   should appear with a real country (from your phone's carrier IP),
   browser, OS, and device type.

If step 3 doesn't redirect: check that both the `uvicorn` and
`cloudflared tunnel run` terminals are still open and show no errors,
and confirm Phase 2's nameserver change has finished propagating
(check status at Cloudflare's dashboard).

## Phase 5: Keeping it running

WSL and the two terminal processes stop when you close the terminal
windows, restart WSL, or shut down Windows. For casual personal use,
the simplest fix is running both inside `tmux` so closing a terminal
window doesn't kill them:
```
sudo apt install -y tmux
tmux new -s linkshortener
# inside this session: source venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000
# Ctrl+B then D to detach, leaving it running
tmux new -s tunnel
# inside this session: cloudflared tunnel run linkshortener
# Ctrl+B then D to detach
```
Reattach anytime with `tmux attach -t linkshortener` or
`tmux attach -t tunnel`.

This still requires your PC to be on and WSL running. For something
that stays up permanently regardless of your PC, move to a real VPS —
see [DEPLOYMENT.md](DEPLOYMENT.md), which covers systemd services (so
nothing depends on a terminal staying open) and reuses everything set
up here except the tunnel, since a VPS has its own public IP.
