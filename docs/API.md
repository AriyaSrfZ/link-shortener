# API Reference

This is the integration surface for calling the link shortener from
another app, script, or service — no browser or dashboard login needed.
Interactive versions of this same reference are always available at
`/docs` (Swagger, lets you try requests in the browser) and `/redoc`
once the server is running.

## Authentication

Every `/api/...` route requires one of:
- **`X-API-Key` header** — set `API_KEY` in `.env`, then send that exact
  value as the header on every request. This is what an external app
  should use. Generate a key with:
  ```
  python3 -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- **Dashboard session cookie** — only relevant if you're calling the API
  from a browser that's already logged into `/dashboard`. Not usable
  from server-to-server code.

If `API_KEY` is left blank in `.env`, API key auth is disabled entirely
and only the session cookie works — meaning the API becomes unusable
from outside a browser. Set it if you intend to call this from an app.

Requests with a missing or wrong key get:
```json
{"detail": "Login required. Send a valid X-API-Key header, or log in via /login for a session."}
```
with HTTP status `401`.

## Base URL
Local: `http://127.0.0.1:8000`
With the Cloudflare Tunnel set up in `WSL_CLOUDFLARE_SETUP.md`: `https://aria-haross.ir`

---

## POST /api/links
Creates a short link.

**Required body fields:**
| Field | Type | Notes |
|---|---|---|
| `long_url` | string (URL) | Must include `http://` or `https://` |
| `utm_source` | string | e.g. `newsletter`, `instagram` |
| `utm_medium` | string | e.g. `sms`, `email`, `cpc` |
| `utm_campaign` | string | e.g. `summer_sale_2026` |

**Optional body fields:**
| Field | Type | Notes |
|---|---|---|
| `utm_term` | string | paid search keyword, if used |
| `utm_content` | string | distinguishes variants (A/B test, ad copy) |
| `custom_code` | string | 3-64 chars, letters/digits/`_`/`-` only. Omit to auto-generate a 6-char code. Returns `400` if already taken. |

**Request:**
```bash
curl -X POST https://aria-haross.ir/api/links \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "long_url": "https://amooot.com/product",
    "utm_source": "app",
    "utm_medium": "push_notification",
    "utm_campaign": "flash_sale",
    "custom_code": "flash01"
  }'
```

**Response `200`:**
```json
{
  "id": 1,
  "short_code": "flash01",
  "short_url": "https://aria-haross.ir/r/flash01",
  "long_url": "https://amooot.com/product",
  "final_url": "https://amooot.com/product?utm_source=app&utm_medium=push_notification&utm_campaign=flash_sale",
  "utm_source": "app",
  "utm_medium": "push_notification",
  "utm_campaign": "flash_sale",
  "utm_term": null,
  "utm_content": null,
  "is_active": true,
  "created_at": "2026-09-06T09:12:16.552149",
  "click_count": 0
}
```

**Errors:** `400` if `custom_code` is taken or reserved (`api`, `dashboard`,
`login`, `logout`, `static`, `health`, `new` are reserved words and
can't be used as codes). `401` if auth is missing/wrong.

`short_url` is what you distribute. `final_url` is what it actually
redirects to (the destination with UTM params attached) — useful if you
want to show the user where a link leads before they click it.

---

## GET /api/links
Lists links, newest first.

**Query params (optional):** `skip` (default 0), `limit` (default 100, max 500)

```bash
curl https://aria-haross.ir/api/links?limit=20 -H "X-API-Key: YOUR_KEY"
```
Returns an array of the same object shape as the create response.

---

## GET /api/links/{id}
Fetches one link by its numeric ID.

```bash
curl https://aria-haross.ir/api/links/1 -H "X-API-Key: YOUR_KEY"
```
`404` if the ID doesn't exist.

---

## DELETE /api/links/{id}
Deletes a link and all of its click history. Cannot be undone.

```bash
curl -X DELETE https://aria-haross.ir/api/links/1 -H "X-API-Key: YOUR_KEY"
```
Returns `{"ok": true}` on success, `404` if not found.

---

## GET /api/links/{id}/clicks
Returns individual click records for one link, newest first — the full
backtrace data per click.

**Query params (optional):** `skip`, `limit` (max 500)

```bash
curl https://aria-haross.ir/api/links/1/clicks -H "X-API-Key: YOUR_KEY"
```

**Response `200`:**
```json
[
  {
    "id": 5,
    "clicked_at": "2026-09-06T14:22:10.000Z",
    "ip_address": "203.0.113.42",
    "referrer": "https://t.me/somechannel",
    "browser": "Chrome 120.0",
    "os": "Android 14",
    "device_type": "mobile",
    "country": "Iran",
    "city": null
  }
]
```
`city` is always `null` currently — the offline geolocation database used
(`geoip2fast`) only resolves country reliably. `device_type` is one of
`desktop`, `mobile`, `tablet`, `bot`, `unknown`.

---

## GET /api/links/{id}/stats
Aggregate analytics for one link: totals, a daily click series, top
referrers, device breakdown, top countries.

**Query params (optional):** `days` (default 14, max 90) — length of the daily series.

```bash
curl "https://aria-haross.ir/api/links/1/stats?days=30" -H "X-API-Key: YOUR_KEY"
```

**Response `200`:**
```json
{
  "summary": {"total": 42, "last_24h": 5},
  "daily": [{"day": "2026-08-24", "count": 3}, {"day": "2026-08-25", "count": 0}],
  "top_referrers": [{"referrer": "https://t.me/somechannel", "count": 20}],
  "devices": [{"device_type": "mobile", "count": 30}],
  "top_countries": [{"country": "Iran", "count": 35}]
}
```
`daily` always includes every day in the range, even zero-click days —
safe to plot directly without gap-filling on your end.

---

## GET /api/stats
Same shape as the per-link stats endpoint, combined across every link
site-wide. Same `days` query param.

```bash
curl https://aria-haross.ir/api/stats -H "X-API-Key: YOUR_KEY"
```

---

## Integration examples

**Python (requests):**
```python
import requests

BASE = "https://aria-haross.ir"
HEADERS = {"X-API-Key": "YOUR_KEY"}

r = requests.post(f"{BASE}/api/links", headers=HEADERS, json={
    "long_url": "https://amooot.com/product",
    "utm_source": "app",
    "utm_medium": "sms",
    "utm_campaign": "reminder",
})
short_url = r.json()["short_url"]
```

**PHP (for a WordPress plugin):**
```php
$response = wp_remote_post('https://aria-haross.ir/api/links', [
    'headers' => [
        'X-API-Key'    => 'YOUR_KEY',
        'Content-Type' => 'application/json',
    ],
    'body' => json_encode([
        'long_url'     => 'https://amooot.com/product',
        'utm_source'   => 'app',
        'utm_medium'   => 'sms',
        'utm_campaign' => 'reminder',
    ]),
]);
$data = json_decode(wp_remote_retrieve_body($response), true);
$short_url = $data['short_url'];
```

**JavaScript (fetch, for a mobile or web app):**
```javascript
const res = await fetch("https://aria-haross.ir/api/links", {
  method: "POST",
  headers: {
    "X-API-Key": "YOUR_KEY",
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    long_url: "https://amooot.com/product",
    utm_source: "app",
    utm_medium: "sms",
    utm_campaign: "reminder",
  }),
});
const { short_url } = await res.json();
```

## Running headless (no dashboard, API only)
The dashboard and the API are fully independent — you never need to
open `/dashboard` for the API to work. To run this purely as an
API-serving gateway with nothing interactive:

```bash
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > app.log 2>&1 &
```
This detaches from the terminal and keeps running after you log out of
the WSL session (until WSL itself is shut down — see
`WSL_CLOUDFLARE_SETUP.md` Phase 5 for a `tmux`-based alternative that
survives closing terminal windows more predictably, or `DEPLOYMENT.md`
for a systemd service that survives everything except a reboot).

Set `ADMIN_USERNAME`/`ADMIN_PASSWORD` to something real regardless —
`/dashboard` and `/login` still exist and are still reachable at your
domain even if you never plan to use them, so they need real
credentials, not the `.env.example` defaults.
