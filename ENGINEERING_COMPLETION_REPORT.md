# AIF Media Automation Platform

## Engineering Completion Report

## Table of Contents

1. [Project Summary](#project-summary)
2. [System Architecture](#system-architecture)
3. [Deliverables Overview](#deliverables-overview)
4. [Future Roadmap](#future-roadmap)
5. [System Details](#system-details)
   1. [Automated Live Streaming](#1-automated-live-streaming)
   2. [Remote Operations](#2-remote-operations)
   3. [Production Reliability](#3-production-reliability)
   4. [Audio & Video Integration](#4-audio--video-integration)
   5. [Facebook Streaming](#5-facebook-streaming)
6. [Documentation](#documentation)
7. [Maintenance Recommendations](#maintenance-recommendations)
8. [Professional Services](#professional-services)

------------------------------------------------------------------------

## Project Summary

Designed and deployed a custom media automation platform for AIF,
transforming a largely manual live production process into a reliable,
remotely managed system capable of scheduled recording, automated
streaming to multiple platforms, and future expansion into AI-assisted
media and communications.

This project combined AV integration, systems engineering, software
development, network administration, cloud services, and custom
automation into a single production platform designed for long-term
maintainability and future growth.

------------------------------------------------------------------------

## System Architecture

```
PTZ Camera ──── Capture Card ──┐
                                │
Audio Mixer ────────────────────┤
                                ▼
                       Automation PC
                    (Recording / Streaming)
                                │
        ┌──────────────┬────────┴────────┐
        ▼              ▼                 ▼
    YouTube      Facebook (manual)   WordPress (future)
        │
        ▼
  Custom Automation (future)
        │
        ▼
  Website • Email • Social Media (future)
```

The audio mixer feeds the Automation PC directly (not through the capture
card) — the capture card carries video only. This keeps the audio and
video signal paths independent, which is what allows each to be
upgraded or reconfigured without affecting the other (see Section 4,
Audio & Video Integration).

------------------------------------------------------------------------

# Deliverables Overview

The following capabilities have been completed and are now operational.

| Capability | Summary | Hours |
|---|---|---|
| **Automated Live Streaming** | Weekly livestreams run start to finish with no manual steps, and the system corrects itself automatically if something goes wrong mid-schedule. | **14** |
| **Remote Operations** | The system can be accessed, maintained, and fixed remotely — no on-site visit needed for routine work. | **5** |
| **Production Reliability** | Keeps running through common failures — power outages, software crashes, missed steps — without someone needing to catch and fix it manually. | **8** |
| **Audio & Video Integration** | Audio and video are handled independently for better quality and easier future upgrades, instead of being tangled together through the camera. | **6** |
| **Facebook Streaming** | The same broadcast now also streams to Facebook alongside YouTube — turning it on and off each week is currently a manual step. | **4** |

**Total Engineering Time:** **37 Hours**

------------------------------------------------------------------------

# Future Roadmap

The platform was intentionally designed as a foundation for additional
automation.

| Enhancement | Estimated Time |
|---|---|
| Automatic website publishing for new livestreams and recordings | 3–5 hours |
| Automatic email and social media announcements | 4–8 hours |
| Event management automation (single announcement to all communication channels) | 8–12 hours |
| AI-generated video summaries and transcripts | 6–10 hours |
| Automatic highlight clip generation | 10–20 hours |
| Searchable lecture archive | 12–20 hours |
| AI assistant for media management and communications | 20–40 hours |
| Unified communications dashboard | 20–30 hours |
| System health monitoring and failure alerts (internet, OBS, camera, disk space) | 6–10 hours |
| Automated recurring configuration backups | 2–4 hours |

> **Removed from this list:** "Facebook Live automation and integration."
> Facebook streaming itself is now live (see Section 5) — what's not
> included is a fully hands-free start/stop toggle for it, and that's
> not currently purchasable engineering time. It's blocked upstream: the
> third-party plugin driving the Facebook connection (Aitum Multistream)
> has no API, hotkey, or scriptable control surface for its per-destination
> outputs as of this writing — confirmed directly by testing, not assumed.
> Automating it would require that plugin shipping a feature it doesn't
> have yet, or switching to a different multistream tool entirely. Worth
> revisiting if either changes, but shouldn't be offered as a standard
> line item today.

------------------------------------------------------------------------

# System Details

## 1. Automated Live Streaming

### Overview

Designed and deployed a fully automated streaming workflow capable of
scheduled recordings and livestreams with minimal operator intervention,
built on a custom automation framework designed specifically for AIF's
workflow rather than off-the-shelf scheduling software.

### Workflow

- Scheduled events automatically prepare the production environment.
- Recording and livestreams begin and end according to schedule.
- Broadcast status is continuously reconciled against the wall clock, so
  the system reaches the correct state even after a delayed reboot or a
  missed scheduled action, instead of firing a stale action late.
- Recovery logic prevents duplicate broadcasts and minimizes operator
  intervention.

### Architecture

| Component | Purpose | Sub-Components / Technologies |
|---|---|---|
| Stream Control Engine | Broadcast lifecycle management (start/stop of stream and recording), including the manual command-line interface used for testing and one-off actions | `stream_actions.py` — OBS control via the `obsws-python` WebSocket client; `obs_stream_ctl.py` — manual CLI wrapper |
| Scheduling & Reconciliation Engine | Time-based automation; compares desired vs. actual state and self-heals after any interruption, including unclean shutdowns, stale state, and missed/delayed triggers | `reconcile.py` — wall-clock reconciliation logic; `register_tasks.ps1` — Windows Task Scheduler registration; `dismiss_obs_crash_dialog.ps1` — automated recovery from unclean-shutdown dialogs |
| Multi-Channel Stream Publishing | Automated broadcast creation and lifecycle management on YouTube, plus manually-toggled simultaneous streaming to Facebook | `yt_broadcast.py` + `authorize_youtube.py` — YouTube Data API v3 via Google OAuth (the only authorization step in the system — Facebook requires none, just a static stream key); Aitum Multistream — third-party OBS plugin, Facebook via persistent RTMP key |

### Key Engineering Decisions

- Built the YouTube integration on top of the YouTube Data API rather
  than a plain video stream with nothing managing it — this is what
  makes it possible to create a real, properly-titled broadcast,
  transition it live, and cleanly finalize it into its own separate
  video afterward. Facebook, by contrast, uses a direct stream connection
  with a fixed key rather than an equivalent managed integration — Meta's
  stricter requirements for that level of integration made a simpler,
  more manual approach the practical choice there instead (see Section 5).
- Added automatic safeguards so that if a session gets interrupted or
  stalls partway through — a power blip, a missed step, a connection
  that didn't come back cleanly — the system notices on its own and
  restores the correct state the next time it checks, rather than
  staying stuck until someone manually intervenes. This was directly
  motivated by a real multi-hour power outage that exposed how a simpler
  fixed-schedule approach could otherwise leave things broken for hours
  with nobody aware.

**Engineering Time:** **14 hours**

------------------------------------------------------------------------

## 2. Remote Operations

### Overview

Configured the production system for secure remote administration,
allowing maintenance, updates, and troubleshooting without requiring
physical access to the building — including a mobile-accessible session
configured to start automatically on every reboot, without needing to
remote in and start one manually first.

### Workflow

Administrators can remotely:

- Access the machine's desktop directly, without the audio/capture
  disruptions a standard remote-desktop connection can cause on an
  actively-streaming machine (confirmed by testing; a lower-impact remote
  access method is used specifically to avoid this)
- Reach a mobile-accessible administrative session that starts
  automatically on every boot (confirmed working; whether it stays paired
  to a phone across a real reboot without re-pairing is still being
  verified — see Maintenance Recommendations)
- Update configurations, start or stop services when necessary
- Diagnose hardware and software issues
- Perform routine maintenance with minimal interruption to normal
  operations

### Key Engineering Decisions

- Chose Chrome Remote Desktop over native Windows RDP after direct
  testing confirmed RDP's session takeover breaks OBS's live audio
  capture (the mixer input dropped for several minutes during a live
  test before self-recovering). Chrome Remote Desktop mirrors the
  existing session instead of taking it over, avoiding this entirely.
- Resolved the specific blocker preventing an unattended Claude Code
  session from starting automatically at boot — a one-time workspace
  trust prompt with no one there to answer it — enabling a
  mobile-accessible administrative session with no manual startup step.

**Engineering Time:** **5 hours**

------------------------------------------------------------------------

## 3. Production Reliability

### Overview

Significant effort was devoted to improving system reliability and
reducing the likelihood of missed recordings or failed broadcasts.

### Workflow

The production platform now incorporates multiple layers of recovery and
fault tolerance designed to continue operating through common failure
scenarios, including power loss spanning multiple hours.

### Key Engineering Decisions

- Investigated a real production incident where a multi-day power outage
  caused three missed scheduled triggers to fire in an uncoordinated
  burst on recovery. Determined this was Windows Task Scheduler's own
  catch-up behavior rather than a bug in the automation, and confirmed
  the existing state-checks prevented actual damage (no duplicate
  broadcasts) despite messy-looking logs from the racing processes.
- Used that incident to drive the reconciliation redesign (see Section
  1) that now protects against a repeat, rather than patching the
  symptom in isolation.
- Confirmed local recordings use a crash-resilient file format that
  survives an abrupt interruption — relevant precisely because the
  failure mode it protects against (power loss mid-recording) is a real,
  observed scenario for this system, not a theoretical one.

**Engineering Time:** **8 hours**

------------------------------------------------------------------------

## 4. Audio & Video Integration

### Overview

Redesigned the audio and video signal flow to improve quality,
reliability, and future flexibility.

### Workflow

The final architecture separates audio and video processing, allowing
each subsystem to operate independently while producing a synchronized
production feed.

This design simplifies future upgrades and reduces dependence on
limitations within the camera hardware.

### Key Engineering Decisions

- Deliberately separated the audio and video signal paths — audio comes
  directly from the mixer, video from the camera through a capture card
  — rather than running a physical wire from the camera to the mixer to
  combine them first. This avoids an extra wire run, gives independent
  control over each signal, and delivers better quality than routing
  audio through the camera's own hardware.
- Identified that the capture card's own embedded audio pin was
  redundantly mixed alongside the mixer's Line In on the same output
  track — a latent source of intermittent audio issues — and removed it
  via direct OBS control rather than a manual scene-file edit, avoiding
  the risk of corrupting the scene configuration by hand.
- Traced a reported "no audio on the live stream" issue back to a mixer
  routing mistake external to this system, rather than a defect in the
  automation or OBS configuration, confirmed via a live test after
  isolating the variable — avoiding an unnecessary and more invasive fix
  to something that wasn't actually broken.

**Engineering Time:** **6 hours**

------------------------------------------------------------------------

## 5. Facebook Streaming

### Overview

Extended the production system to stream simultaneously to Facebook
alongside YouTube, using a dedicated multistreaming plugin integrated
into the existing OBS-based workflow.

### Workflow

- The production video/audio feed is pushed to Facebook using a
  persistent, reusable stream key, alongside the existing automated
  YouTube stream.
- Facebook's platform automatically detects and publishes the incoming
  stream around this key, requiring no per-session API integration on
  that side.
- Starting and stopping the Facebook stream is currently a manual step,
  performed alongside the otherwise fully automated YouTube schedule (see
  the note under Future Roadmap for why).

### Key Engineering Decisions

- Chose Aitum Multistream over the older `obs-multi-rtmp` plugin based on
  current community adoption, then verified its actual automation
  capabilities directly against the running system rather than assuming
  from its documentation, which doesn't cover this.
- Corrected a wrong Facebook ingest server URL that Aitum's own built-in
  preset had auto-filled, in favor of the URL from Facebook's own
  dashboard for the specific persistent key in use — a reminder that
  third-party presets can go stale in ways platform-provided values don't.
- Determined through direct testing that Aitum has no API, hotkey, or
  scriptable way to start or stop the Facebook output independently of
  the main stream. This finding directly shaped the decision to keep
  Facebook as a manual step rather than build fragile automation on a
  capability that doesn't exist (see Future Roadmap).
- Took a full backup of the production OBS configuration before making
  any of these changes, as a precaution.

**Engineering Time:** **4 hours**

------------------------------------------------------------------------

# Documentation

Comprehensive documentation has been produced covering:

- System architecture
- Recovery procedures
- Troubleshooting (including a full diagnostic history of the audio
  hardware investigation)
- Automation scripts
- Remote access setup and rationale
- Future expansion

This documentation significantly reduces future maintenance effort by
preserving the engineering decisions and troubleshooting performed
during implementation.

Approximately:

- 573 lines of production automation code (538 streaming automation +
  35 remote access)
- 386 lines of core technical documentation
- 161 lines of hardware diagnostic documentation
- 137 lines of remote-access setup documentation

------------------------------------------------------------------------

# Maintenance Recommendations

- **No automatic recovery from a frozen or blank video signal.** If the
  camera/capture card signal into OBS ever goes stale (distinct from a
  stream/broadcast interruption, which is covered), the current fix is
  manually refreshing the source in OBS — nothing in the automation
  detects or resolves this on its own. Worth a dedicated check if this
  has recurred.
- **Recording storage has no automatic cleanup.** Local recordings
  accumulate indefinitely; at typical session lengths, the current free
  disk space is on the order of several months' runway, not indefinite.
  Periodically clear old recordings, or add this to a future automation
  pass.
- **Facebook streaming is a manual step, not automated.** Whoever runs
  the Friday session needs to start and stop it alongside the automated
  YouTube stream. If it's ever left running by mistake, nothing
  automatically stops it — see System Details, Section 5.
- **Confirm the Claude Remote Control mobile pairing survives a real
  reboot.** This was set up and works, but whether it reconnects without
  re-pairing after a genuine restart hasn't been confirmed against a real
  reboot yet — worth checking the next time one occurs.
- **Periodically confirm the YouTube OAuth authorization is still
  valid** (e.g., after any Google account password change) — the
  automation depends on it and would otherwise fail silently until
  someone checks the log.
- **Physical connections are a recurring failure point.** Several past
  issues traced back to cabling/routing rather than software (mixer
  input routing, capture card connections). Worth a periodic visual
  check, especially after any on-site hardware changes.

------------------------------------------------------------------------

# Professional Services

| Description | Hours |
|---|---|
| Automated Live Streaming | 14 |
| Remote Operations | 5 |
| Production Reliability | 8 |
| Audio & Video Integration | 6 |
| Facebook Streaming | 4 |
| **Total Engineering Time** | **37** |

**Engineering Rate:** $50.00/hour

**Project Total:** **$1,850**
