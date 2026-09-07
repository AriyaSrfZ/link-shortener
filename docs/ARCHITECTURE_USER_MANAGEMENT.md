# User Management: Current Design and Future Extraction

## Why this doc exists
You asked for user management built so it can become a standalone,
reusable system other projects (the QR tool, the SMS panel, whatever
comes next) plug into as a central account manager. Building that
service now would be speculative - there's only one consumer (this
repo) so far, and a real central auth service needs to know its actual
second and third consumers to get the API shape right. What's done
instead: the auth code here is already cleanly separated, and this doc
is the concrete plan for lifting it out once there's a second project
that needs it.

## What's already isolated (no rework needed later)
- `app/models.py` - `User` model: username, email, password_hash, role, is_active
- `app/routers/auth.py` - all auth logic: password hashing, session
  cookies, `CurrentUser` (the single abstraction every route checks -
  "who is asking, are they admin"), and `require_login` / `require_admin_or_api_key`
  dependencies
- `app/routers/users.py` - `POST /api/users`, account provisioning by a
  trusted caller (admin or API key), not by the user themselves. This
  is already shaped like what a central auth service's "create account"
  endpoint would look like.
- `app/crud.py` - the `create_user` / `username_taken` / `email_taken`
  functions are pure DB operations, no HTTP concerns mixed in.

Nothing else in the app reaches into `User` directly except through
`CurrentUser` and the functions above - link ownership is just an
integer `owner_id`, not a foreign key relationship the rest of the code
depends on structurally.

## The extraction, when it's time
1. **New repo**: `identity-service`. Same stack (FastAPI + SQLAlchemy +
   SQLite/Postgres) - copy `models.User`, `routers/auth.py`,
   `routers/users.py`, and the relevant `crud.py` functions in as the
   whole app.
2. **Swap cookies for tokens**: a central service serving multiple
   separate apps can't share session cookies across domains. Replace
   the session cookie with a JWT: `identity-service` issues one at
   login (`POST /login` returns `{"token": "..."}` instead of setting a
   cookie), and every consuming app verifies it locally (JWT signature
   check, no network call needed per-request) using a shared secret or
   the service's public key.
3. **Each app keeps a local `owner_id`, nothing else**: this repo (and
   the QR project, and anything else) doesn't need its own `users`
   table anymore - just store the `user_id` from the verified JWT
   wherever `owner_id` is used today. No schema change to `Link` or
   `QRCode` at all, since `owner_id` is already just an integer.
4. **Provisioning stays the same shape**: `POST /api/users` on the
   identity service is exactly the `users.py` endpoint already built
   here, unchanged. Any app (this one, the SMS panel, etc.) calls it
   with its own API key to create an account, same as today.
5. **Migrate existing users once**: export the `users` table from this
   repo's database, import into `identity-service`'s database, keep the
   same IDs so existing `owner_id` values in `links`/`qr_codes` stay
   valid.

## What NOT to do
Don't build this until a second project actually needs shared accounts.
A speculative auth service with one consumer just adds a network hop
and a second deployment to maintain, for zero benefit over what exists
now. The moment the QR project (or anything else) needs "log in with
the same account as the link shortener," steps 1-5 above are the plan.
