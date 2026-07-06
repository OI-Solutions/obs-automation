# AIF Stream Automation

Automates Friday Jumu'ah livestreaming on this machine (aif-stream): starts/stops
OBS's stream and local recording, and drives the actual YouTube broadcast
lifecycle via the YouTube Data API (not YouTube's dashboard auto-start, which
turned out to require a browser tab open at all times and was unreliable).

## What happens on a Friday

Windows Task Scheduler fires these, in order, every Friday:

| Task | Time | Action |
|---|---|---|
| `AIF Stream - Launch OBS` | 12:55 PM | Launches OBS if not already running |
| `AIF Stream - Session1 Start` | 1:05 PM | `obs_stream_ctl.py start` |
| `AIF Stream - Session1 Stop` | 2:00 PM | `obs_stream_ctl.py stop` |
| `AIF Stream - Session2 Start` | 2:05 PM | `obs_stream_ctl.py start` |
| `AIF Stream - Session2 Stop` | 3:00 PM | `obs_stream_ctl.py stop` |

Each `start`/`stop` call does all of the following:

**start:**
1. Creates a new YouTube live broadcast (title `First Jumu'ah Khutbah - YYYY-MM-DD` for session 1, `Second Jumu'ah Khutbah - YYYY-MM-DD` for session 2; public, not made for kids)
2. Binds it to the channel's existing persistent stream key (found by matching OBS's configured RTMP key against the channel's `liveStreams` list)
3. Starts OBS's stream output (pushes RTMPS to YouTube)
4. Starts OBS's local recording (failsafe copy, in case wifi/RTMPS drops)
5. Polls YouTube until it detects the incoming stream data as `active`, then transitions the broadcast to `live`

**stop:**
1. Stops OBS's stream output
2. Stops OBS's local recording
3. Transitions the YouTube broadcast to `complete` (this is what finalizes it into its own separate, playable video — RTMP disconnecting alone does NOT do this)

Because each session creates a brand-new broadcast and properly closes it out,
session 1 and session 2 end up as two separate YouTube videos, as intended.

## Files (`C:\Users\AIF\obs-automation\`)

- `obs_stream_ctl.py` — the main entry point; `python obs_stream_ctl.py [start|stop]`
- `yt_broadcast.py` — YouTube Data API helpers (auth, create/bind broadcast, transitions, state file)
- `authorize_youtube.py` — one-time interactive OAuth flow; run manually only when re-authorizing
- `client_secret.json` — Google Cloud OAuth client credentials (Desktop app type). **Secret, do not share.**
- `token.json` — saved OAuth refresh token from the last successful authorization. **Secret, do not share.**
- `current_broadcast.json` — transient state file linking a `start` call to its `stop` call (holds the in-progress broadcast ID). Should not exist between sessions; if it does, something didn't shut down cleanly (see Troubleshooting).
- `register_tasks.ps1` — (re)registers all 5 recurring Friday scheduled tasks. Safe to re-run any time; it unregisters and recreates each task.
- `logs\stream.log` — append-only log of every start/stop action, one line per event with a timestamp.

## Google Cloud / YouTube API setup (for reference, already done)

- Google Cloud project: `aif-stream`
- OAuth consent screen: **published to Production** (not "Testing") — this matters because Testing-status apps get refresh tokens that expire after 7 days, which would have silently broken the automation weekly. Production apps don't have that cap. The consent screen shows an "unverified app" warning during login (click Advanced → proceed) since we haven't gone through Google's full verification review — that's fine for this single-channel internal use.
- OAuth client: Desktop app type, credentials in `client_secret.json`
- Authorized as: the **channel owner** Google account (not `media@azhar`, which is only a Manager on the channel). This matters a lot — see Troubleshooting below.
- Scope granted: `https://www.googleapis.com/auth/youtube`

### Why it has to be the owner account, not a manager account

The YouTube Data API's `mine=true` parameter (used to find "your" channel) only
ever resolves to a channel the authenticated Google account **directly owns**.
It does **not** see channels where that account is merely a Brand Account
Manager, no matter what's selected in Studio's channel switcher. We burned a
lot of time on this — `media@azhar` (a manager-only account) either resolved
to the wrong channel (a now-deleted empty one it happened to own) or, after
that channel was deleted, resolved to zero channels at all. Re-authorizing
with the actual owner account fixed it immediately.

If access to the owner account ever needs to be handed to someone else, either:
- keep using the owner account's login for re-authorization, or
- have the current owner promote another account to **Owner** (not Manager) on the channel's Brand Account permissions, then authorize with that account instead.

## Manual testing

Run either command directly any time to test outside the schedule:

```
C:\Users\AIF\AppData\Local\Programs\Python\Python312\python.exe C:\Users\AIF\obs-automation\obs_stream_ctl.py start 1
C:\Users\AIF\AppData\Local\Programs\Python\Python312\python.exe C:\Users\AIF\obs-automation\obs_stream_ctl.py start 2
C:\Users\AIF\AppData\Local\Programs\Python\Python312\python.exe C:\Users\AIF\obs-automation\obs_stream_ctl.py stop
```

`start` requires a session number (`1` or `2`) to pick the title; `stop` doesn't need one — it just completes whatever broadcast is currently tracked in `current_broadcast.json`.

Check `logs\stream.log` afterward, or tail it live while testing.

## Troubleshooting

**`current_broadcast.json` exists but nothing is streaming** — a previous
`stop` didn't run (e.g. task failure, or manual `start` never matched with a
`stop`). Next `start` will refuse to create a new broadcast because it thinks
one is still tracked. Fix: check the broadcast ID inside that file in YouTube
Studio — if it's stuck in `ready`/`testing` and never went live, delete it via
Studio or the API, then delete `current_broadcast.json` to clear the stale
state.

**Re-authorization needed** (token revoked, Google account password changed,
scope changes, etc.) — delete `token.json` and re-run `authorize_youtube.py`
interactively (it opens a browser). Must be done as the channel owner account,
per above.

**System clock/timezone** — this machine had its system timezone wrong
(Pacific instead of Central) which was fixed by setting it properly and
turning on Windows Time service (`w32time`, pointed at `time.windows.com`,
auto-start). If tasks ever fire at a wall-clock time that looks off by a fixed
number of hours again, check `Get-TimeZone` and `w32tm /query /status` first
before assuming it's a bug in this automation. Also: whenever the system
timezone is changed, all Task Scheduler triggers must be re-registered
(`register_tasks.ps1`) — Windows bakes a fixed UTC offset into each trigger at
creation time and does not recompute it automatically.

**Stream key mismatch** — if a broadcast never finds a matching persistent
stream, `get_persistent_stream_id()` falls back to using the channel's only
`liveStreams` entry if there's exactly one. If the channel ever has more than
one stream key resource, this will need updating to match more precisely (it
already tries exact match against OBS's configured key first).

## Incident history

### 2026-07-03 — power loss mid-stream, delayed recovery

Session 1 went live normally Friday 2026-07-03 at 1:05 PM (broadcast
`R9Wzf7ycWY0`), but the machine lost power before its 2:00 PM Stop task could
run, leaving that broadcast dangling and `current_broadcast.json` stuck
pointing at it. The machine then stayed off until 2026-07-05 (Sunday), when it
was manually powered back on.

**What actually fixed it, and why it looked messy:** this was not a person or
an AI session running recovery commands — it was Windows Task Scheduler's own
catch-up behavior. Every task here is registered with
`-StartWhenAvailable` (see `register_tasks.ps1`), so a trigger missed while
the machine is off gets queued and fires later instead of being skipped. Three
triggers had been missed — Session1 Stop (2:00 PM), Session2 Start (2:05 PM),
Session2 Stop (3:00 PM) — and all three fired in a near-simultaneous burst the
moment the machine booted back up on 2026-07-05. (This was able to happen with
zero manual login step because `AutoAdminLogon` is already configured for the
`AIF` account in `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon`,
and every task's principal is `LogonType=Interactive`, which requires an
actual interactive session to exist before it can fire.)

The burst of three unsynchronized processes racing each other is exactly what
produced the ugly patch of `logs\stream.log` around 2026-07-05T16:52 —
duplicate/interleaved log lines (multiple processes appending to the same
file with no locking), repeated `403 Redundant transition` errors (more than
one process tried to finalize the same already-finalized broadcast), and
multiple redundant OBS-launch attempts. Nothing was actually damaged: the
`start`/`stop` gating logic (checking `stream_active`/`record_active` and
`current_broadcast.json` before acting) meant the racing processes mostly
no-op'd against each other rather than creating duplicate broadcasts, and the
`finally: clear_state()` fallback in `obs_stream_ctl.py`'s stop path is what
actually cleared the stale tracked broadcast, regardless of the repeated API
errors. But this worked out safely more by the state-gating design than by
any real handling of concurrent racing — see the reconciliation proposal
below for a cleaner fix.

Cleanup performed after this incident: `current_broadcast.json` was already
cleared by the time this was investigated (2026-07-05), and eight leftover
one-off `AIF Stream - TEST` / `TEST2`...`TEST7` scheduled tasks (created
during ad-hoc debugging on 2026-07-02 and 2026-07-05) were unregistered,
leaving only the canonical 5 tasks from `register_tasks.ps1`.

**Planned BIOS change:** the physical machine is being configured to
auto-power-on after an AC power loss (BIOS setting typically named "Restore
on AC Power Loss" / "AC Power Recovery" — set to "Power On"), so that future
outages self-heal within moments instead of sitting off for days. Given
`AutoAdminLogon` is already configured, this should work without any other
change: BIOS powers the box on, Windows boots straight to an interactive `AIF`
session with no manual login needed, and `StartWhenAvailable` catch-up can
fire immediately. The one caveat: if a future outage still spans more than
one scheduled trigger boundary (e.g. knocks out both the 2:00 and 2:05
marks), the same multi-task race described above will still happen — just
resolved in seconds instead of days rather than eliminated outright.

## Open questions / possible future enhancements

- **Thumbnail upload** — feasible. YouTube's API has `thumbnails().set(videoId=..., media_body=<image file>)`, callable right after a broadcast is created, using the same scope we already have. Needs the channel to have custom thumbnails enabled (requires phone verification, which most channels already have) and a static image file to use each week.
- **Simultaneous stream to Facebook** — feasible but bigger scope. OBS doesn't natively support multiple simultaneous stream destinations out of the box; would need either a plugin (e.g. `obs-multi-rtmp`) to push a second RTMP output to Facebook alongside YouTube, plus Facebook's own Graph API live-video calls (create/end) mirroring what `yt_broadcast.py` does for YouTube. Not yet implemented.
- **Idempotent boot-time reconciliation** — proposed fix for the race condition described above. Instead of three independent scheduled tasks each blindly firing one hardcoded action at a fixed wall-clock time, replace them with a single `reconcile()` function that (1) computes what *should* be true right now purely from the wall clock (idle / session 1 live / session 2 live), (2) checks what's *actually* true (`stream_active`, `record_active`, `current_broadcast.json`), and (3) takes only the action needed to close the gap, or nothing if they already match. This is naturally idempotent — running it concurrently or repeatedly converges to the same end state instead of piling up actions. Add an `-AtStartup` (or `-AtLogOn`) trigger calling the same function so a delayed reboot self-heals immediately rather than waiting for the next fixed-time trigger. Would still need a simple lock file to guarantee only one reconciliation runs at a time (the fixed-time triggers and the boot trigger could otherwise still collide). Not yet implemented — discussed 2026-07-05, on hold pending decision to build it.
