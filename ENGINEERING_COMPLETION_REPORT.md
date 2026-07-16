# AIF Media Automation Platform

## Engineering Completion Report

## Table of Contents

1. [Project Summary](#project-summary)
2. [System Architecture](#system-architecture)
3. [Deliverables Overview](#deliverables-overview)
4. [Potential Future Expansions](#potential-future-expansions)
5. [System Details](#system-details)
   1. [Automated Live Streaming](#1-automated-live-streaming)
   2. [Remote Operations](#2-remote-operations)
   3. [Production Reliability](#3-production-reliability)
   4. [Audio & Video Integration](#4-audio--video-integration)
6. [Documentation](#documentation)
7. [Maintenance Recommendations](#maintenance-recommendations)
8. [Professional Services — Invoice Summary](#professional-services--invoice-summary)

------------------------------------------------------------------------

## Project Summary

Replaced AIF's manual live-production workflow with a reliable,
remotely-managed system: livestreams run automatically, recordings are
backed up locally, and the same broadcast now reaches both YouTube and
Facebook. Built to be maintained and extended for years, not just to
work today.

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
              ┌─────────────────┴─────────────────┐
              ▼                                     ▼
      YouTube Data API                     Facebook (manual)
              │
      ┌───────┴───────┐
      ▼               ▼
  YouTube      Custom Automation (future)
                       │
                       ▼
  WordPress Website • Email • Social Media (future)
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
| **Automated Live Streaming** | • Runs start to finish automatically, no manual steps<br>• Multiple sessions can be scheduled in advance — currently two every Friday (1:05–2:00 PM and 2:05–3:00 PM)<br>• Self-corrects if something goes wrong mid-schedule<br>• Local recording continues even if the internet drops<br>• Also streams to Facebook alongside YouTube | **16** |
| **Remote Operations** | • The machine itself, plus every scheduled trigger and automation, can be accessed and reconfigured remotely<br>• No on-site visit needed for routine work or schedule changes | **5** |
| **Production Reliability** | • At any moment, the system checks the current time and makes sure the right thing is happening — started, stopped, or already correctly running — even if something was interrupted beforehand<br>• Recovers automatically from power outages<br>• Recovers automatically from software crashes<br>• No manual intervention needed to catch and fix issues | **8** |
| **Audio & Video Integration** | • Physical wiring and capture hardware installed<br>• Audio and video signal paths run independently<br>• Better quality, easier future upgrades | **6** |

**Total Engineering Time:** **35 Hours**

------------------------------------------------------------------------

# Potential Future Expansions

The platform was intentionally designed as a foundation for additional
automation.

| Enhancement | Estimated Time |
|---|---|
| Automatic website and social media publishing when a new livestream or recording is posted (via the YouTube Data API), with pre-set tags and categories | 3–5 hours |
| System health monitoring and automated recurring configuration backups | 8–14 hours |
| Advanced Content Creation & Management — AI-generated video summaries and transcripts, automatic highlight clip generation, and a searchable lecture archive | 28–50 hours |
| Unified Communications Hub — one central place to post an announcement, automatically distributed to email, social media, and other channels | 32–50 hours |

------------------------------------------------------------------------

# System Details

## 1. Automated Live Streaming

### Overview

Designed and deployed a fully automated streaming workflow capable of
scheduled recordings and livestreams with minimal operator intervention,
built on a custom automation framework designed specifically for AIF's
workflow rather than off-the-shelf scheduling software. Distribution now
covers multiple destinations — YouTube fully automated, with Facebook
reached simultaneously as a manually-toggled addition (see Key
Engineering Decisions below).

### Workflow

- Scheduled events automatically prepare the production environment.
- Recording and livestreams begin and end according to schedule.
- Broadcast status is continuously reconciled against the wall clock, so
  the system reaches the correct state even after a delayed reboot or a
  missed scheduled action, instead of firing a stale action late.
- Recovery logic prevents duplicate broadcasts and minimizes operator
  intervention.
- Local recording runs independently of the live stream — if the
  internet connection drops mid-session, the recording keeps going, so
  nothing is lost even though the live broadcast itself is interrupted.

### Architecture

| Component | Purpose | Sub-Components / Technologies |
|---|---|---|
| Stream Control Engine | Broadcast lifecycle management (start/stop of stream and recording), including the manual command-line interface used for testing and one-off actions | `stream_actions.py` — OBS control via the `obsws-python` WebSocket client; `obs_stream_ctl.py` — manual CLI wrapper |
| Scheduling & Reconciliation Engine | Time-based automation; compares desired vs. actual state and self-heals after any interruption, including unclean shutdowns, stale state, and missed/delayed triggers | `reconcile.py` — wall-clock reconciliation logic; `register_tasks.ps1` — Windows Task Scheduler registration; `dismiss_obs_crash_dialog.ps1` — automated recovery from unclean-shutdown dialogs |
| Multi-Channel Stream Publishing | Automated broadcast creation and lifecycle management on YouTube, plus manually-toggled simultaneous streaming to Facebook | `yt_broadcast.py` + `authorize_youtube.py` — YouTube Data API v3 via Google OAuth (the only authorization step in the system — Facebook requires none, just a static stream key); Aitum Multistream — third-party OBS plugin, Facebook via persistent RTMP key |

### Key Engineering Decisions

- Built YouTube on the Data API rather than a plain video stream, so
  broadcasts are properly created, titled, and finalized — not just raw
  video with nothing managing it. Facebook uses a simpler direct
  connection instead, since Meta's stricter requirements didn't justify
  the same approach there.
- Added self-correcting safeguards so an interrupted or stalled session
  recovers automatically instead of staying stuck — motivated by a real
  multi-hour power outage that exposed the risk of a simpler
  fixed-schedule approach.
- Added Facebook as a second destination via a multistreaming plugin,
  then confirmed through testing that it has no API to start/stop
  independently — why it's a manual step today rather than automation
  built on a capability that doesn't exist.

### Future / Recommended Expansions

- Automate the Facebook toggle if the streaming plugin ever adds
  programmatic control (see Potential Future Expansions).
- Support one-off or special-event sessions without manual schedule
  changes.
- Extend the same publishing pattern to additional platforms beyond
  YouTube and Facebook as needed.

**Engineering Time:** **16 hours**

------------------------------------------------------------------------

## 2. Remote Operations

### Overview

Configured the production system for secure remote administration,
allowing maintenance, updates, and troubleshooting without requiring
physical access to the building.

### Workflow

Administrators can remotely:

- Access the machine's desktop directly, without the audio/capture
  disruptions a standard remote-desktop connection can cause on an
  actively-streaming machine (confirmed by testing; a lower-impact remote
  access method is used specifically to avoid this)
- Update configurations, start or stop services when necessary
- Diagnose hardware and software issues
- Perform routine maintenance with minimal interruption to normal
  operations

### Key Engineering Decisions

- Chose Chrome Remote Desktop over native RDP after testing confirmed
  RDP's session takeover breaks OBS's live audio capture; Chrome Remote
  Desktop mirrors the session instead of taking it over.

### Future / Recommended Expansions

- Add a remote status dashboard so system health can be checked at a
  glance instead of connecting in to look.
- Support additional remote users or devices if more than one person
  needs administrative access.
- Add a local LLM for ongoing system maintenance, monitoring, and admin
  tasks — self-hosted infrastructure the system owns outright, rather
  than depending on any individual's personal account.

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

- Investigated a real multi-day power outage that caused three missed
  triggers to fire in a burst on recovery — traced to Windows Task
  Scheduler's own catch-up behavior, not a bug, and confirmed no actual
  damage occurred despite messy-looking logs.
- Used that incident to drive the reconciliation redesign (see Section
  1), fixing the root cause rather than the symptom.
- Confirmed local recordings use a crash-resilient format that survives
  an abrupt interruption — relevant since power loss mid-recording is a
  real, observed scenario here, not theoretical.

### Future / Recommended Expansions

- Add automatic recovery for a frozen or blank video signal (currently
  requires a manual refresh — see Maintenance Recommendations).
- Add automated recording cleanup so storage doesn't require manual
  management.
- Add proactive failure alerts instead of relying on log review after
  the fact.
- Wire the PC with Ethernet and add a UPS, so a WiFi drop or power
  interruption is less likely to happen in the first place, rather than
  only recovering after the fact.

**Engineering Time:** **8 hours**

------------------------------------------------------------------------

## 4. Audio & Video Integration

### Overview

Set up the physical wiring and capture hardware, and redesigned the
audio and video signal flow, to improve quality, reliability, and future
flexibility.

### Workflow

Physical infrastructure — capture card, camera, and mixer connections —
was installed and wired as the foundation for everything else in this
section. On top of that, the final architecture separates audio and
video processing, allowing each subsystem to operate independently while
producing a synchronized production feed.

This design simplifies future upgrades and reduces dependence on
limitations within the camera hardware.

### Key Engineering Decisions

- Separated audio and video signal paths — audio direct from the mixer,
  video via capture card — rather than wiring the camera through the
  mixer first, avoiding an extra wire run and giving better quality and
  independent control over each signal.
- Identified the capture card's own audio pin was redundantly mixed
  alongside the mixer's Line In — a latent source of intermittent
  issues — and removed it via direct OBS control rather than risking a
  manual scene-file edit.
- Traced a reported "no audio on the stream" issue to an external mixer
  routing mistake, not a system defect — confirmed via live test,
  avoiding an unnecessary fix to something that wasn't broken.

### Future / Recommended Expansions

- Additional camera angles or multi-camera switching.
- Upgraded capture or audio hardware if higher resolution or quality is
  ever needed.
- Wireless audio options to reduce physical cabling further.
- Organize and label on-site cabling — currently a tangle that makes
  future troubleshooting and changes harder than necessary.

**Engineering Time:** **6 hours**

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
  automatically stops it — see System Details, Section 1.
- **Periodically confirm the YouTube OAuth authorization is still
  valid** (e.g., after any Google account password change) — the
  automation depends on it and would otherwise fail silently until
  someone checks the log.
- **Physical connections are a recurring failure point.** Several past
  issues traced back to cabling/routing rather than software (mixer
  input routing, capture card connections). Worth a periodic visual
  check, especially after any on-site hardware changes.

------------------------------------------------------------------------

# Professional Services — Invoice Summary

| Description | Hours |
|---|---|
| Automated Live Streaming | 16 |
| Remote Operations | 5 |
| Production Reliability | 8 |
| Audio & Video Integration | 6 |
| **Total Engineering Time** | **35** |

**Engineering Rate:** $50.00/hour

**Project Total:** **$1,750**
