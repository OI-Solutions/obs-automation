# AIF Stream Automation

Automates Friday Jumu'ah livestreaming on this machine (aif-stream): starts/stops
OBS's stream and local recording, and drives the actual YouTube broadcast
lifecycle via the YouTube Data API (not YouTube's dashboard auto-start, which
turned out to require a browser tab open at all times and was unreliable).

## What happens on a Friday

Windows Task Scheduler fires these:

| Task | Time | Action |
|---|---|---|
| `AIF Stream - Launch OBS` | 12:55 PM | Launches OBS if not already running (guarded against double-launch - see below) |
| `AIF Stream - Session1 Start` | 1:05 PM | `reconcile.py` |
| `AIF Stream - Session1 Stop` | 2:00 PM | `reconcile.py` |
| `AIF Stream - Session2 Start` | 2:05 PM | `reconcile.py` |
| `AIF Stream - Session2 Stop` | 3:00 PM | `reconcile.py` |
| `AIF Stream - Reconcile AtLogOn` | every logon | `reconcile.py` |

All five session-related triggers run the same `reconcile.py`, not a
hardcoded start-or-stop - see "Idempotent reconciliation" below for why
that matters. Under the hood, `reconcile.py` calls the same `do_start()` /
`do_stop()` functions (in `stream_actions.py`) that each do all of the
following:

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

## Idempotent reconciliation (why the scheduled tasks call `reconcile.py`)

**The problem:** every scheduled task is registered with `-StartWhenAvailable`
(see `register_tasks.ps1`), so a trigger missed while the machine is off gets
queued and fires the moment the machine comes back — *whatever time that
turns out to be*, not the time it was supposed to fire. A short outage (one
missed trigger) self-heals fine. But a longer outage spanning several
trigger boundaries used to mean a stale burst of start/stop actions firing
hours late — this actually happened on 2026-07-03/07-05 (see Incident
history) and, harmlessly by luck, again on 2026-07-06 when a broadcast
(`cgCGqf-Ai5U`) got left marked LIVE on YouTube for ~26 hours after a
mid-test restart skipped the stop call. Left unfixed, the dangerous version
of this bug is a missed Session2 Start firing hours late and briefly taking
the live camera/mic feed public to real viewers at the wrong time.

**The fix:** `reconcile.py` replaces "always do X" with "make the current
state match what the wall clock says it should be." Every trigger — the 4
fixed Friday times plus a new `AtLogOn` trigger for immediate post-reboot
recovery — runs the same `reconcile()` function. It:

1. Computes the *desired* state purely from `datetime.now()`: idle, session
   1 live, or session 2 live (Fridays only, based on the same time windows
   as the table above).
2. Reads the *actual* state: is a broadcast currently tracked
   (`current_broadcast.json`), for which session, and — critically — is OBS's
   stream output genuinely active right now (not just "was a broadcast
   created at some point").
3. Takes only the one action needed to close the gap, or does nothing if
   they already match:
   - Outside any window but something's tracked → stale, finalize it (the
     `cgCGqf-Ai5U` scenario).
   - Inside a window, nothing tracked → start fresh.
   - Inside a window, the *wrong* session tracked (e.g. session 1 never
     stopped and the clock has rolled into session 2's window) → finalize
     the wrong one, then start the right one.
   - Inside a window, the right session tracked but OBS's stream isn't
     actually active (e.g. a mid-session power loss restarted OBS with
     outputs stopped while the state file survived on disk) → resume it.
     `do_start()` is safe to call again here — it sees a broadcast is
     already tracked and won't recreate it, but will still (re)issue
     `start_stream()`/`start_record()` since those are genuinely inactive.
   - Inside a window, right session tracked and genuinely live → no-op.

Running `reconcile()` concurrently, repeatedly, or hours late all converge
to the same correct end state — that's what "idempotent" means here. A
short-lived exclusive-create lock file (`reconcile.lock`, auto-reclaimed if
older than 12 minutes — a stale lock means a previous run got killed by the
task's `ExecutionTimeLimit`) stops two overlapping reconcile runs from
acting at the same time, which matters most right after a delayed reboot
when several missed triggers plus `AtLogOn` can all fire within seconds of
each other.

**Known limitation:** the session window times are hardcoded in
`SESSION_WINDOWS` at the top of `reconcile.py` and must be kept in sync by
hand with the trigger times in `register_tasks.ps1` — there's no single
shared source of truth for both today. If you ever change the Friday
schedule, update both files. Also, like the old fixed-time triggers, this
is only as correct as the system clock/timezone — see the clock/timezone
note under Troubleshooting.

## Files (`C:\Users\AIF\obs-automation\`)

- `obs_stream_ctl.py` — manual one-shot CLI; `python obs_stream_ctl.py [start 1|2|stop]`. Always does exactly what you tell it — this is the tool for manual testing (see "Manual testing" below).
- `reconcile.py` — the idempotent, wall-clock-driven entry point every scheduled task actually calls. See "Idempotent reconciliation" above. Not meant for ad-hoc manual testing outside a real session window, since outside a window it will always just no-op or finalize a stale broadcast.
- `stream_actions.py` — shared engine (`do_start()`, `do_stop()`, OBS websocket connect/launch, logging) used by both `obs_stream_ctl.py` and `reconcile.py`, so manual and scheduled runs behave identically.
- `yt_broadcast.py` — YouTube Data API helpers (auth, create/bind broadcast, transitions, state file)
- `authorize_youtube.py` — one-time interactive OAuth flow; run manually only when re-authorizing
- `client_secret.json` — Google Cloud OAuth client credentials (Desktop app type). **Secret, do not share.** Not tracked in git (`.gitignore`).
- `token.json` — saved OAuth refresh token from the last successful authorization. **Secret, do not share.** Not tracked in git.
- `current_broadcast.json` — transient state file linking a `start` call to its `stop` call (holds the in-progress broadcast ID, YouTube stream ID, and which session number is live). Should not exist between sessions; if it does and `reconcile.py`/scheduled tasks aren't running, something didn't shut down cleanly (see Troubleshooting). Not tracked in git.
- `reconcile.lock` — transient lock file held only for the duration of a single `reconcile()` run; should not persist between runs. Not tracked in git.
- `register_tasks.ps1` — (re)registers all 6 recurring scheduled tasks (5 Friday fixed-time + 1 AtLogOn). Safe to re-run any time; it unregisters and recreates each task.
- `logs\stream.log` — append-only log of every start/stop/reconcile action, one line per event with a timestamp.

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

To test `reconcile.py` itself (rather than the underlying start/stop
actions), run `python reconcile.py` directly — but note it only takes
action if the real wall clock is currently inside a session window (or a
stale broadcast is tracked); outside that it will just log a no-op. You can
also fire it exactly the way Task Scheduler would with
`Start-ScheduledTask -TaskName "AIF Stream - Reconcile AtLogOn"`.

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

**`reconcile.lock` exists and reconcile seems to be silently skipping** — a
lock younger than 12 minutes means another reconcile run is genuinely in
progress (expected right after a delayed reboot when several triggers fire
close together — just wait). Older than that, it's a leftover from a run
that got killed (e.g. by the task's 10-minute `ExecutionTimeLimit`) before
it could clean up; the next `reconcile()` run reclaims it automatically, or
delete it by hand to force that immediately.

**OBS shows a stuck "already running" dialog after a boot** — this would
block every scheduled action silently on an unattended machine (nobody's
there to click it). `AIF Stream - Launch OBS`'s action now checks
`Get-Process obs64` before launching, specifically to prevent this when
`reconcile.py` already launched OBS moments earlier during a catch-up
burst. If you ever see this dialog, something bypassed that guard (e.g. OBS
launched manually while a scheduled launch was also in flight) — close the
dialog and check `Get-Process obs64` for duplicates.

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

**Planned BIOS change (now done):** the physical machine is being configured to
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

### 2026-07-06 — stuck live broadcast after ad-hoc testing, audio routing fix, reconciliation built

During manual testing (mixer/capture-card audio troubleshooting, unrelated
to a scheduled Friday run), a `start` was issued, went LIVE
(`cgCGqf-Ai5U`), and then the machine was restarted several times without
the matching `stop` ever running — leaving that broadcast marked LIVE on
YouTube for roughly 26 hours with no signal. No process was actually
hung (`current_broadcast.json` was just stale and OBS wasn't running) —
running `obs_stream_ctl.py stop` by hand transitioned it to `complete` and
cleared the state file. This is the same class of bug the reconciliation
work below now handles automatically going forward.

Also found and fixed: the OBS scene had two audio sources both mixed onto
the same output track — the mixer's Line In (the intended source) and the
capture card's own embedded audio pin (`Video Capture Device`,
`audio_output_mode: 0`), which was unnecessary since audio comes from the
mixer, not the capture card. Muted it and removed it from all tracks via
the OBS websocket (`set_input_mute` / `set_input_audio_tracks`) so only Line
In feeds the stream/recording. A live test after this (broadcast
`npS8drcn068`) confirmed the automation, OBS, and websocket path all work
correctly end-to-end — the earlier "no audio on stream" symptom traced back
to a mixer routing mistake upstream of OBS, not a bug in this repo.

Separately, `reconcile.py` was built this session to close the "stale
action fires hours late after a long outage" gap discussed on 2026-07-05 —
see "Idempotent reconciliation" above. Git version control
(`C:\Users\AIF\obs-automation\.git`) was also set up for the first time as
part of this change, with a baseline commit taken before any of the
refactor.

## Open questions / possible future enhancements

- **Thumbnail upload** — feasible. YouTube's API has `thumbnails().set(videoId=..., media_body=<image file>)`, callable right after a broadcast is created, using the same scope we already have. Needs the channel to have custom thumbnails enabled (requires phone verification, which most channels already have) and a static image file to use each week.
- **Simultaneous stream to Facebook** — feasible but bigger scope. OBS doesn't natively support multiple simultaneous stream destinations out of the box; would need either a plugin (e.g. `obs-multi-rtmp`) to push a second RTMP output to Facebook alongside YouTube, plus Facebook's own Graph API live-video calls (create/end) mirroring what `yt_broadcast.py` does for YouTube. Not yet implemented. Worth doing as a layer on top of the current setup rather than in parallel with it, now that the reconciliation piece below is in place.
- **Session window times duplicated across two files** — `reconcile.py`'s `SESSION_WINDOWS` and `register_tasks.ps1`'s trigger times encode the same 1:05/2:00/2:05/3:00 schedule independently and must be kept in sync by hand. Could be collapsed into one source of truth (e.g. `register_tasks.ps1` reads the windows from a small JSON/Python config file that `reconcile.py` also imports) if the schedule starts changing often enough for the duplication to bite. Not worth it while the schedule is fixed and rarely touched.

## Idempotent boot-time reconciliation — implemented 2026-07-06

This was previously an open proposal (see git history / older revisions of
this file for the original writeup); it's now built. Full design,
rationale, and the specific incidents that motivated it are documented in
"Idempotent reconciliation" above rather than duplicated here.
