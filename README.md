# Anonymous Telegram Relay Bot

A Telegram bot that relays messages anonymously: a user DMs the bot, a moderator
approves or rejects the message in a private moderation chat, and approved
messages are published to a target chat or channel with no sender attribution.

## How it works

1. A user sends the bot a message in a private chat (text, photo, video,
   document, voice, sticker, animation — anything).
2. The bot replies asking for confirmation. For content that can carry a
   caption (photo, video, animation, audio, document, voice) it offers three
   buttons: `без тега` / `#моё` / `#не_моё`. For everything else — text,
   stickers, video notes — a tag is impossible or meaningless, so it offers a
   single `✅ Отправляем!` button. Both prompts also carry `❌ Стоп Отмена!!`,
   which discards the submission and replaces the prompt with a "not sent"
   notice. Nothing is forwarded until a send button is tapped.
   Both prompts also have `↩️ Ответить на сообщение` — see
   [Replying to a message](#replying-to-a-message).
3. On tap, the bot places a **copy** of the message into the moderation chat,
   appending the chosen tag on a new line. A copy carries no "forwarded from"
   header, so the sender stays anonymous. The moderation-chat copy is
   uncovered — moderators need to see the actual content to judge it. The bot
   attaches an inline keyboard: ✅ Approve / ❌ Reject. The prompt in the
   user's chat becomes `✅ Отправлено!`.
4. A moderator taps a button:
   - **Approve** → the bot publishes the message from the moderation chat into
     the target chat, covering photos/videos/animations with a spoiler.
   - **Reject** → nothing is published.

   Either way, the Approve/Reject buttons are replaced with a single inert
   status button recording the outcome and who decided it, e.g.
   `✅ Approved by Jane Doe` or `❌ Rejected by Jane Doe`.

### Replying to a message

A sender can make the published message a reply to an existing message in the
target chat:

1. Tap `↩️ Ответить на сообщение`. The bot sends a short message asking for a
   link, as a `ForceReply`, so the Telegram client opens straight in reply mode
   aimed at it. The original prompt stays as it is.
2. Paste the message link (Telegram: long-press → *Copy link*) and send. If the
   link is sent without replying to the ask, it is treated as a new submission.
3. The bot checks that the link is a message in `TARGET_CHAT_ID` (accepted:
   `t.me/c/<id>/<msg>`, `t.me/<username>/<msg>`, and their topic forms), then
   edits the original prompt to show `↩️ Ответ на: <link>` and deletes the ask.
   Tag/send buttons now carry the message id. `↩️ Другое сообщение` picks
   another one.

   A `ForceReply` cannot carry buttons, and Telegram strips nested replies, so
   the user's reply shows the bot only the ask message, not the prompt behind
   it. The prompt's `message_id` and whether it takes a tag therefore ride on a
   text link (the leading `↩️`, `t.me/<bot>?p=<prompt_id>&r=t|p`) inside the ask.
   It is the bot's own profile with query parameters, not a `t.me/<bot>/<n>`
   path, which Telegram would read as a message link.
4. The moderation copy gets an `↩️ Replying to message` link button to the
   target message, so moderators see what it answers.
5. On approval the bot publishes with `reply_parameters`. If the target message
   no longer exists, the message is still posted, just not as a reply.

Links to other chats and channel comment links (`?comment=`) are refused. The
bot cannot check that the message exists when the link is sent (there is no
`getMessage`), so a deleted target is only discovered at approval — and then
handled by posting without the reply.

### Spoilers

Photos, videos and animations are delivered covered by a spoiler in the target
chat only — the moderation-chat copy stays uncovered so moderators can review
the actual content.

`copyMessage` has no `has_spoiler` parameter, so covered media cannot be
copied — on approval the bot re-sends it by `file_id` (taken from the
moderation chat's own copy, so this doesn't reintroduce any attribution) with
`sendPhoto` / `sendVideo` / `sendAnimation` instead of copying it.

Telegram supports spoilers on those three types only. Documents, audio and
voice notes travel uncovered, so a photo sent as an uncompressed file is *not*
hidden.

### Tagging

The tag is appended as a new line, in the copy placed into the moderation
chat. How depends on the content type:

- **Photo, video, animation, audio, document, voice** — copied with an
  overridden `caption`.
- **Text** — not offered a tag, but the code still handles one (resent with
  `sendMessage` as `text + "\n" + tag`, because `copyMessage` cannot rewrite
  text) so that prompts created before this rule can still be tapped.
- **Stickers, video notes** — Telegram allows no caption on these, so they are
  always sent untagged.

`без тега` always takes the plain `copyMessage` path, byte-identical to the
original. The tag is already baked into the caption by the time a moderator
approves, so publishing to the target chat carries it over unchanged.

### No storage

The bot keeps no database, no files, and logs no message content or sender
identity. The only place a message exists is Telegram's own copies in the
moderation and target chats. Approval works directly off the moderation-chat
message itself — its own `message_id`, caption and (for spoilered media)
`file_id` are all publishing needs — so no mapping between users and messages
is ever needed.

The one dynamic piece — the id of the message being replied to — is appended to
the buttons' `callback_data` (`mod:approve:<id>`, `snd:mine:<id>`), so it
travels with the Telegram messages themselves. Buttons without an id (sent
before this feature) still work and simply don't reply.

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

### 3. Configure

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

### 4. Install

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
2. From a test account, DM the bot a text message and a photo. Each should get
   a `Готово, отправляем в чат?` prompt with three tag buttons. Tap `#моё` on
   the photo and `без тега` on the text. Both should then appear in the
   moderation chat with Approve/Reject buttons and **no** "forwarded from"
   line, the photo carrying `#моё` on a new line in its caption, and the
   prompts should change to `Отправлено ✅`.
3. Approve the photo, reject the text. The photo should appear in the target
   chat covered by a spoiler (tap to reveal) and with no attribution; the text
   should not appear anywhere else; both moderation-chat messages should lose
   their buttons.

## Layout

```
bot/
├── main.py                 # entrypoint: webhook server / polling fallback
├── config.py               # env-based settings, fail-fast validation
├── keyboards.py            # Tag/send/moderation/status inline keyboards
├── links.py                # t.me message link parsing/building (pure)
├── relay.py                # relay() into moderation, publish() into target w/ spoiler
├── handlers/
    ├── user.py             # /start + private messages → moderation chat
    └── moderation.py       # Approve/Reject callback handling
tests/                      # offline tests: python -m unittest discover -s tests -t .
Dockerfile                  # runs the bot in polling mode
render.yaml                 # Render Blueprint: always-on background worker
```

## Out of scope

- Any persistence of message content or sender identity.
- Rate limiting / anti-spam.
- Moderator permission checks beyond "the press came from the moderation chat";
  restrict who is in that chat instead.
