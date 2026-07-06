import json
import obs_stream_ctl as ctl

cl = ctl.connect()
try:
    name = "Audio Input Capture"
    mute = cl.get_input_mute(name)
    vol = cl.get_input_volume(name)
    settings = cl.get_input_settings(name)
    print("MUTE:", mute.input_muted)
    print("VOLUME:", vol.input_volume_db, "dB /", vol.input_volume_mul, "mul")
    print("SETTINGS:", json.dumps(settings.input_settings, indent=2, default=str))

    tracks = cl.get_input_audio_tracks(name)
    print("TRACKS:", json.dumps(vars(tracks), default=str))

    stream = cl.get_stream_status()
    print("STREAM ACTIVE:", stream.output_active, "BYTES:", stream.output_bytes)
finally:
    cl.disconnect()
