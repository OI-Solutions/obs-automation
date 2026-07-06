"""
Idempotent reconciliation for the Friday stream schedule.

Problem this solves: the 4 fixed-time scheduled tasks (Session1/2 Start/Stop)
are registered with -StartWhenAvailable, so a trigger missed while the
machine is off/rebooting gets queued and fires the moment the machine is
back - regardless of what the actual wall-clock time is by then. Before this
module existed, that meant a long outage spanning multiple trigger
boundaries could fire a stale start/stop burst hours late, briefly taking
the camera/mic live to real viewers at the wrong time. See README.md
"Incident history" (2026-07-03/07-05) for the real occurrence.

The fix: every trigger now runs reconcile() instead of a hardcoded
start/stop. reconcile() figures out what should be true right now purely
from the wall clock (idle / session 1 live / session 2 live - Fridays
only), compares that to what's actually true, and takes only the action
needed to close the gap - or nothing if they already match. Running it
concurrently, repeatedly, or hours late all converge to the same correct
end state:

  - Outside any session window but a broadcast is still tracked -> stale,
    finalize it (this is the exact bug fixed by hand on 2026-07-06 for
    broadcast cgCGqf-Ai5U, which was left LIVE for ~26 hours after a
    mid-test restart skipped the stop call).
  - Inside a session window and nothing tracked -> start it fresh.
  - Inside a session window, the *wrong* session is tracked (e.g. session 1
    never stopped and we've rolled into session 2's window) -> finalize the
    wrong one, then start the right one.
  - Inside a session window, the right session is tracked, but OBS's stream
    output isn't actually active (e.g. a mid-session power loss restarted
    OBS with outputs stopped while current_broadcast.json survived on
    disk) -> resume it. do_start() is safe to call again here: it sees a
    broadcast is already tracked and skips recreating it, but still issues
    start_stream()/start_record() since those are genuinely inactive.
  - Inside a session window, the right session is tracked and genuinely
    streaming -> no action.

A simple exclusive-create lock file (reconcile.lock) prevents two
reconcile() runs from acting concurrently, which matters most right after a
delayed reboot when several missed triggers plus the AtLogOn trigger can
all fire within moments of each other. A lock older than
LOCK_STALE_SECONDS is treated as abandoned (e.g. a previous run got killed
by the task's ExecutionTimeLimit) and reclaimed rather than blocking
forever.

Session window times must be kept in sync with register_tasks.ps1's
trigger times by hand - there is no single shared source of truth for them
today (see README "Open questions").
"""
import os
import time
from datetime import datetime, time as dtime

import stream_actions as sa
import yt_broadcast as yt

HERE = os.path.dirname(__file__)
LOCK_PATH = os.path.join(HERE, "reconcile.lock")
LOCK_STALE_SECONDS = 12 * 60  # a bit longer than the tasks' 10-minute ExecutionTimeLimit

FRIDAY = 4  # datetime.weekday()
SESSION_WINDOWS = {
    1: (dtime(13, 5), dtime(14, 0)),  # 1:05pm - 2:00pm
    2: (dtime(14, 5), dtime(15, 0)),  # 2:05pm - 3:00pm
}


def desired_session(now):
    """Which session (1, 2, or None) should be live at this moment, per the wall clock."""
    if now.weekday() != FRIDAY:
        return None
    t = now.time()
    for session, (start, end) in SESSION_WINDOWS.items():
        if start <= t < end:
            return session
    return None


class LockHeld(Exception):
    pass


def _acquire_lock():
    try:
        age = time.time() - os.path.getmtime(LOCK_PATH)
        if age < LOCK_STALE_SECONDS:
            raise LockHeld(f"lock is {age:.0f}s old, still fresh")
        os.remove(LOCK_PATH)  # stale - a previous run never got to release it
    except FileNotFoundError:
        pass
    fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.close(fd)


def _release_lock():
    try:
        os.remove(LOCK_PATH)
    except FileNotFoundError:
        pass


def _stream_actually_active():
    cl = sa.connect()
    try:
        return cl.get_stream_status().output_active
    finally:
        cl.disconnect()


def reconcile():
    try:
        _acquire_lock()
    except (LockHeld, FileExistsError) as e:
        sa.log(f"reconcile: skipped - another reconcile is already running ({e})")
        return

    try:
        desired = desired_session(datetime.now())
        state = yt.load_state()
        tracked = state.get("session") if state else None

        if desired is None:
            if tracked is None:
                sa.log("reconcile: idle, nothing tracked - no action")
            else:
                sa.log(f"reconcile: session {tracked} is tracked but we're outside any session window - finalizing it")
                sa.do_stop()
            return

        if tracked is not None and tracked != desired:
            sa.log(f"reconcile: session {tracked} is tracked but session {desired} should be live now - finalizing {tracked} first")
            sa.do_stop()
            tracked = None

        if tracked is None:
            sa.log(f"reconcile: session {desired} should be live but isn't tracked - starting it")
            sa.do_start(desired)
            return

        if _stream_actually_active():
            sa.log(f"reconcile: session {desired} already live - no action")
        else:
            sa.log(f"reconcile: session {desired} is tracked but the stream isn't active (likely resumed after a restart) - resuming it")
            sa.do_start(desired)
    finally:
        _release_lock()


if __name__ == "__main__":
    reconcile()
