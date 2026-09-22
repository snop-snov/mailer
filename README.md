# Anonymous Telegram Relay Bot

A Telegram bot that relays messages anonymously: a user DMs the bot, a moderator
approves or rejects the message in a private moderation chat, and approved
messages are published to a target chat or channel with no sender attribution.

## How it works

1. A user sends the bot a message in a private chat (text, photo, video,
   document, voice, sticker, animation — anything).
2. The bot uses `copyMessage` to place a **copy** of it into the moderation
   chat. A copy carries no "forwarded from" header, so the sender stays
   anonymous. The bot attaches an inline keyboard: ✅ Approve / ❌ Reject.
3. The user gets a short `✅ Sent.` confirmation.
4. A moderator taps a button:
   - **Approve** → the bot copies the message from the moderation chat into the
     target chat and removes the buttons.
   - **Reject** → the buttons are removed and nothing is published.

### No storage

The bot keeps no database, no files, and logs no message content or sender
identity. The only place a message exists is Telegram's own copies in the
moderation and target chats. Approval works by copying the moderation-chat
message itself, so no mapping between users and messages is ever needed.

Because of that, anyone who can see the moderation chat can act on submissions,
and the callback handler additionally refuses any button press that did not come
from the configured `MODERATION_CHAT_ID`.

## Setup

### 1. Create the bot

1. Talk to [@BotFather](https://t.me/BotFather), send `/newbot`, follow the
   prompts, and copy the token into `BOT_TOKEN`.
2. Send `/setprivacy` → select your bot → **Disable**, if the moderation chat is
   a group and you want the bot to receive all updates there. (Not required for
   the button flow, but harmless.)

### 2. Create the chats and add the bot

- **Moderation chat**: a private group with your moderators. Add the bot and
  make it an administrator (it needs to post messages and edit its own).
- **Target chat/channel**: where approved messages get published. Add the bot as
  an administrator with permission to post messages.

### 3. Get the chat IDs

With `BOT_TOKEN` already in `.env`, the bundled helper is the easiest way:

```bash
python scripts/get_chat_id.py
```

Leave it running, then post a message in each chat. It prints
`id  type  title` for every chat the bot gets an update from. Stop it with
Ctrl-C before starting the bot — both use `getUpdates`, and only one consumer
can read updates at a time.

Two gotchas:

- **Groups:** by default a bot only receives *commands* in groups (privacy
  mode). Either send `/start` in the group, or make the bot an admin, which
  turns privacy mode off for it.
- **Channels:** the bot must already be an administrator; then post anything and
  the `channel_post` update reveals the id.

Alternatives if you'd rather not run the script: forward a message from the chat
to [@userinfobot](https://t.me/userinfobot), add
[@getidsbot](https://t.me/getidsbot) to the chat temporarily, or read `chat.id`
straight from `https://api.telegram.org/bot<TOKEN>/getUpdates`.

Supergroup and channel IDs are negative and start with `-100`; a private chat id
is a positive user id.

### 4. Configure

```bash
cp .env.example .env
$EDITOR .env
```

| Variable | Required | Meaning |
| --- | --- | --- |
| `BOT_TOKEN` | yes | Token from BotFather |
| `MODERATION_CHAT_ID` | yes | Chat where moderators approve/reject |
| `TARGET_CHAT_ID` | yes | Chat/channel approved messages go to |
| `WEBHOOK_HOST` | webhook mode | Public HTTPS base URL, e.g. `https://bot.example.com` |
| `WEBHOOK_PATH` | no (default `/webhook`) | Path Telegram posts updates to |
| `WEBHOOK_SECRET_TOKEN` | webhook mode | Verified against `X-Telegram-Bot-Api-Secret-Token` |
| `WEB_SERVER_HOST` | no (default `0.0.0.0`) | Listen address behind the proxy |
| `WEB_SERVER_PORT` | no (default `8080`) | Listen port behind the proxy |

### 5. Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Running

### Webhook (optional)

```bash
python -m bot.main
```

The bot starts an aiohttp server on `WEB_SERVER_HOST:WEB_SERVER_PORT` and
registers `WEBHOOK_HOST + WEBHOOK_PATH` with Telegram on startup (and deletes
the webhook on shutdown).

Telegram only delivers updates over HTTPS on ports 443, 80, 88 or 8443, so put
an HTTPS-terminating reverse proxy (nginx, Caddy, Traefik) or a PaaS in front of
the server and point it at the listen address. Provisioning that endpoint is
outside the scope of this repo. A minimal nginx location block:

```nginx
location /webhook/ab12cd34ef56 {
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Telegram-Bot-Api-Secret-Token $http_x_telegram_bot_api_secret_token;
}
```

### Long polling (default for deploys, and for local testing)

No public endpoint needed. This is what the deployed worker runs, and it is
also the easiest way to test end to end from your laptop:

```bash
python -m bot.main --polling
```

In this mode `WEBHOOK_HOST` and `WEBHOOK_SECRET_TOKEN` are not required, and any
existing webhook is deleted on start.

Only one poller may run against a token at a time — stop your local instance
before the deployed one handles traffic, or Telegram returns 409 Conflict.

## Deploying (Render background worker)

The bot runs in **polling mode** in production. Polling needs only outbound
internet — no domain, no TLS certificate, no reverse proxy, no webhook secret.
Webhook mode stays supported (see above) but is not needed at this scale.

Two consequences worth knowing:

- Exactly **one** instance may run at a time. Two pollers sharing a token get
  HTTP 409 Conflict from Telegram. Never scale the worker above 1.
- Because the bot stores nothing, a redeploy mid-moderation is safe: pending
  Approve/Reject buttons keep working, since the state is Telegram's copy of
  the message, not anything in the process.

### Steps

1. Push this repo to GitHub (**private** — see the note on secrets below).
2. In Render: **New → Blueprint**, connect the repo. Render reads
   `render.yaml` and creates a Docker-based background worker.
3. Render prompts for the three variables marked `sync: false`:
   `BOT_TOKEN`, `MODERATION_CHAT_ID`, `TARGET_CHAT_ID`. Paste the values from
   your local `.env`.
4. Deploy. Logs should show `Run polling for bot @yourbot`.

Every push to the linked branch redeploys (`autoDeployTrigger: commit`).

### Cost and sizing

The `0.5c-512mb` Starter worker is $7/month and is always on — paid instances
do not spin down the way free web services do. The bot is idle almost all the
time, so the smallest plan is ample; you are paying for availability, not
compute. Change `region:` in `render.yaml` before the first deploy if
`frankfurt` isn't closest to you — region cannot be changed afterwards.

### Secrets

`.env` is gitignored and must never be committed; it holds a live bot token.
Nothing in `render.yaml` contains a secret — `sync: false` means the values are
entered in the Render dashboard and stored there.

Note that when you *update* an existing Blueprint, Render ignores `sync: false`
variables. Adding a new secret later means setting it by hand in the dashboard.

If a token ever leaks, revoke it with `/revoke` in @BotFather and issue a new
one.

### Other hosts

`Dockerfile` is plain Docker with no Render-specific pieces, so the same image
runs anywhere:

```bash
docker build -t mailer-bot .
docker run -d --restart=unless-stopped --env-file .env --name mailer-bot mailer-bot
```

That works on any VPS; add `--restart=unless-stopped` (as above) or a systemd
unit so it survives reboots.

## Manual end-to-end check

1. Run with `--polling`.
2. From a test account, DM the bot a text message and a photo. Both should
   appear in the moderation chat with Approve/Reject buttons and **no**
   "forwarded from" line, and the sender should see `✅ Sent.` each time.
3. Approve one, reject the other. The approved one should appear in the target
   chat with no attribution; both moderation-chat messages should lose their
   buttons.

## Layout

```
bot/
├── main.py                 # entrypoint: webhook server / polling fallback
├── config.py               # env-based settings, fail-fast validation
├── keyboards.py            # Approve/Reject inline keyboard
├── handlers/
    ├── user.py             # /start + private messages → moderation chat
    └── moderation.py       # Approve/Reject callback handling
scripts/
└── get_chat_id.py          # dev helper: print chat ids from getUpdates
Dockerfile                  # runs the bot in polling mode
render.yaml                 # Render Blueprint: always-on background worker
```

## Out of scope

- Any persistence of message content or sender identity.
- Rate limiting / anti-spam.
- Moderator permission checks beyond "the press came from the moderation chat";
  restrict who is in that chat instead.
