import json
import os
import subprocess
import sys
import time
from datetime import datetime

import obsws_python as obs

import yt_broadcast as yt

LOG_PATH = os.path.join(os.path.dirname(__file__), "logs", "stream.log")
OBS_WS_CONFIG = os.path.join(
    os.environ["APPDATA"], "obs-studio", "plugin_config", "obs-websocket", "config.json"
)
OBS_EXE = r"C:\Program Files\obs-studio\bin\64bit\obs64.exe"
OBS_DIR = r"C:\Program Files\obs-studio\bin\64bit"


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


ORDINALS = {"1": "First", "2": "Second"}


def main():
    valid_start = len(sys.argv) == 3 and sys.argv[1] == "start" and sys.argv[2] in ORDINALS
    valid_stop = len(sys.argv) == 2 and sys.argv[1] == "stop"
    if not (valid_start or valid_stop):
        print("usage: obs_stream_ctl.py start [1|2]\n       obs_stream_ctl.py stop")
        sys.exit(2)

    action = sys.argv[1]
    cl = connect()

    try:
        stream_active = cl.get_stream_status().output_active
        record_active = cl.get_record_status().output_active

        if action == "start":
            state = yt.load_state()
            if state:
                log(f"start requested but a YouTube broadcast is already tracked ({state['broadcast_id']}) - skipping broadcast creation")
            else:
                try:
                    youtube = yt.get_client()
                    obs_key = cl.get_stream_service_settings().stream_service_settings.get("key", "")
                    stream_id = yt.get_persistent_stream_id(youtube, obs_key)
                    title = f"{ORDINALS[sys.argv[2]]} Jumu'ah Khutbah - {datetime.now():%Y-%m-%d}"
                    broadcast_id = yt.create_and_bind_broadcast(youtube, stream_id, title)
                    yt.save_state(broadcast_id, stream_id)
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
        else:
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


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"ERROR: {e}")
        sys.exit(1)
