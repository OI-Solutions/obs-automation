"""
Manual one-shot CLI: python obs_stream_ctl.py [start 1|2 | stop]

For unattended scheduled runs, see reconcile.py instead - it decides
start-vs-stop from the wall clock so a delayed reboot doesn't blindly fire a
stale action. This script always does exactly what you tell it, which is
what you want for manual testing.
"""
import sys

from stream_actions import do_start, do_stop, log

ORDINALS = {"1": 1, "2": 2}


def main():
    valid_start = len(sys.argv) == 3 and sys.argv[1] == "start" and sys.argv[2] in ORDINALS
    valid_stop = len(sys.argv) == 2 and sys.argv[1] == "stop"
    if not (valid_start or valid_stop):
        print("usage: obs_stream_ctl.py start [1|2]\n       obs_stream_ctl.py stop")
        sys.exit(2)

    if sys.argv[1] == "start":
        do_start(ORDINALS[sys.argv[2]])
    else:
        do_stop()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"ERROR: {e}")
        sys.exit(1)
