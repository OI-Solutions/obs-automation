"""
Shared engine for starting/stopping a Jumu'ah session: OBS websocket control
plus the YouTube broadcast lifecycle. Used by both obs_stream_ctl.py (manual
CLI, one-shot actions) and reconcile.py (scheduled, wall-clock-driven).

Keeping this logic in one place means both callers share identical
start/stop behavior, including the "already active / already tracked"
idempotency checks that make it safe to call do_start()/do_stop() more than
once in a row without creating duplicate broadcasts or double-starting
outputs.
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime

import obsws_python as obs

import yt_broadcast as yt

HERE = os.path.dirname(__file__)
LOG_PATH = os.path.join(HERE, "logs", "stream.log")
OBS_WS_CONFIG = os.path.join(
    os.environ["APPDATA"], "obs-studio", "plugin_config", "obs-websocket", "config.json"
)
OBS_EXE = r"C:\Program Files\obs-studio\bin\64bit\obs64.exe"
OBS_DIR = r"C:\Program Files\obs-studio\bin\64bit"

ORDINALS = {1: "First", 2: "Second"}


def log(msg):
    line = f"{datetime.now().isoformat(timespec='seconds')} {msg}"
    print(line)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_ws_settings():
    with open(OBS_WS_CONFIG, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg["server_port"], cfg.get("server_password", "")


def try_connect(port, password, retries, delay):
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            return obs.ReqClient(host="127.0.0.1", port=port, password=password, timeout=5)
        except Exception as e:
            last_err = e
            log(f"connect attempt {attempt}/{retries} failed: {e}")
            time.sleep(delay)
    raise last_err


def connect(retries=6, delay=5):
    port, password = load_ws_settings()
    try:
        return try_connect(port, password, retries, delay)
    except Exception:
        log("OBS unreachable - attempting to launch it")
        try:
            subprocess.Popen([OBS_EXE], cwd=OBS_DIR)
        except Exception as e:
            log(f"failed to launch OBS: {e}")
            raise
        return try_connect(port, password, retries, delay)


def do_start(session):
    """session: 1 or 2. Safe to call repeatedly - skips any step already done."""
    cl = connect()
    try:
        stream_active = cl.get_stream_status().output_active
        record_active = cl.get_record_status().output_active

        state = yt.load_state()
        if state:
            log(f"start requested but a YouTube broadcast is already tracked ({state['broadcast_id']}) - skipping broadcast creation")
        else:
            try:
                youtube = yt.get_client()
                obs_key = cl.get_stream_service_settings().stream_service_settings.get("key", "")
                stream_id = yt.get_persistent_stream_id(youtube, obs_key)
                title = f"{ORDINALS[session]} Jumu'ah Khutbah - {datetime.now():%Y-%m-%d}"
                broadcast_id = yt.create_and_bind_broadcast(youtube, stream_id, title)
                yt.save_state(broadcast_id, stream_id, session)
                log(f"YouTube broadcast created and bound: {broadcast_id} ({title})")
            except Exception as e:
                log(f"WARNING: could not create YouTube broadcast ({e}) - continuing with local recording only")

        if stream_active:
            log("start requested but stream already active - skipping")
        else:
            cl.start_stream()
            log("stream START issued")

        if record_active:
            log("start requested but recording already active - skipping")
        else:
            cl.start_record()
            log("recording START issued")

        state = yt.load_state()
        if state:
            try:
                youtube = yt.get_client()
                if yt.wait_for_active_stream(youtube, state["stream_id"]):
                    yt.transition(youtube, state["broadcast_id"], "live")
                    log(f"YouTube broadcast transitioned to LIVE: {state['broadcast_id']}")
                else:
                    log(f"WARNING: YouTube never detected active stream data within timeout for {state['broadcast_id']}")
            except Exception as e:
                log(f"WARNING: failed to transition broadcast to live ({e})")
    finally:
        cl.disconnect()


def do_stop():
    """Safe to call even if nothing is active - every step no-ops cleanly."""
    cl = connect()
    try:
        stream_active = cl.get_stream_status().output_active
        record_active = cl.get_record_status().output_active

        if not stream_active:
            log("stop requested but stream not active - skipping")
        else:
            cl.stop_stream()
            log("stream STOP issued")

        if not record_active:
            log("stop requested but recording not active - skipping")
        else:
            result = cl.stop_record()
            log(f"recording STOP issued - saved to {result.output_path}")

        state = yt.load_state()
        if state:
            try:
                youtube = yt.get_client()
                yt.transition(youtube, state["broadcast_id"], "complete")
                log(f"YouTube broadcast transitioned to COMPLETE: {state['broadcast_id']}")
            except Exception as e:
                log(f"WARNING: failed to transition broadcast {state['broadcast_id']} to complete ({e}) - clearing tracked state anyway so the next session isn't blocked")
            finally:
                yt.clear_state()
        else:
            log("stop requested but no tracked YouTube broadcast - skipping transition")
    finally:
        cl.disconnect()
