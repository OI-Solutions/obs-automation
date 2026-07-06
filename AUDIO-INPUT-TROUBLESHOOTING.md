# Audio input troubleshooting — no recording devices appear in Windows

## The problem

This machine (the AIF streaming box, Dell OptiPlex 3050) cannot get any audio
input signal recognized by Windows at all. **Zero devices appear in Windows
Sound Settings' Recording tab or the classic `mmsys.cpl` Recording tab**, with
"Show Disabled Devices" and "Show Disconnected Devices" both checked — the
list is genuinely empty, not just filtered. Same result in OBS's audio input
device dropdown.

This is why OBS is currently configured to receive audio via RTMPS from the
camera (the audio signal is fed into the Fomaku camera upstream, which mixes
it in before the feed ever reaches this PC) instead of using a local Windows
audio input device — that workaround is what's in place *because* this
problem has never been solved.

## Devices tried (all fail identically)

1. **Onboard headset/line jack** (front panel) — jack-sensing works correctly
   (Windows pops up the "what did you plug in?" dialog), user selects
   Line-in, but still nothing appears in Recording devices afterward.
2. **A small generic USB adapter** with two 3.5mm in/out jacks (never fully
   retested after the C-Media identification below — see Next steps).
3. **A ClearClick USB audio interface with AUX-in** — this is the main one
   tested. **Confirmed working perfectly on a MacBook** — rules out the
   device/cable itself being defective. On this OptiPlex, across multiple
   USB ports (including a port proven good by the video capture card), it
   still produces zero visible recording devices.

Note: there is also a separate **Guermok USB3 video capture card** plugged
into this machine (`VID_345F&PID_2130`) used for video only — it has no audio
streaming interface at all (confirmed via USB descriptor enumeration) and was
never a candidate for solving this; don't confuse it with the ClearClick
audio interface, they are two different physical devices.

## What's been ruled out (all confirmed clean via direct inspection)

- **USB port/hardware failure** — ruled out; the ClearClick interface works
  fine on a MacBook, and was tested on an OptiPlex port already proven good
  by the video capture card.
- **Group Policy device installation restrictions**
  (`HKLM\SOFTWARE\Policies\Microsoft\Windows\DeviceInstall\Restrictions`) —
  key doesn't exist on this machine.
- **AppPrivacy / microphone force-deny policy**
  (`HKLM\SOFTWARE\Policies\Microsoft\Windows\AppPrivacy`) — key doesn't exist.
  A broad recursive search of the entire `HKLM\SOFTWARE\Policies` tree for
  anything mentioning Mic/Camera/Audio/Capture turned up nothing.
- **Microphone privacy consent** — both the machine-wide and per-user
  `CapabilityAccessManager\ConsentStore\Microphone` values are `Allow`.
- **MDM/Intune enrollment** — `dsregcmd /status` confirms this machine is not
  Azure AD joined, not domain joined, and not MDM-enrolled. The enrollment
  GUIDs visible under `HKLM\SOFTWARE\Microsoft\Enrollments` are normal stock
  Windows plumbing present on every install, not evidence of leftover
  corporate management.
- **Third-party antivirus/endpoint security with mic-blocking features** —
  only stock Windows Defender is registered (Security Center check + install
  list scan for ESET/Sophos/McAfee/CrowdStrike/Bitdefender/etc. all came back
  empty).
- **Windows Audio services** — `AudioSrv` and `AudioEndpointBuilder` both
  `Running`/`Automatic`; restarting both did not surface any device.
- **Driver health for the C-Media chip inside the ClearClick interface**
  (`VID_0D8C&PID_0014`, the actual USB Audio Class silicon — a very common
  generic chipset) — `Get-PnpDevice`/`Win32_PnPEntity` show
  `Status: OK`, `ConfigManagerErrorCode: CM_PROB_NONE`. A full
  `Disable-PnpDevice` / `Enable-PnpDevice` cycle came back completely clean,
  no error surfaced.
- **Waves Audio Effects Component (Dell MaxxAudio)** interfering with
  non-Realtek endpoints — plausible theory, but the registry proves it's not
  the blocker (see below).
- **`audiodg.exe` (Windows Audio Device Graph Isolation) crashing** when a
  capture stream initializes — checked Application event log for crash
  reports mentioning `audiodg`; none found, in the relevant window or ever.

## The actual, confirmed behavior (from raw event log + registry, not just UI)

This part matters for whoever picks this up next — don't re-derive it, it
took a lot of digging:

- Every time the C-Media device (ClearClick interface) connects, Windows'
  `Microsoft-Windows-Kernel-PnP/Configuration` event log shows it going
  through a completely normal, error-free driver load
  (`wdma_usb.inf` / `usbaudio` service), **and** shows `audioendpoint.inf`
  successfully configuring two `SWD\MMDEVAPI\{...}` endpoint devices for it
  every single time.
- The registry cache at
  `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Capture`
  confirms this further: it contains a "Microphone"-labeled entry for
  **every one of those exact GUIDs** from the event log. Windows' audio
  stack unambiguously does recognize and correctly label this device as a
  microphone every time it connects.
- Despite that, `Get-PnpDevice -Class AudioEndpoint` never shows the device
  as `Present: True`, at any point it was checked — including moments after
  a connection event, and including while the underlying USB driver instance
  itself was sitting at `Present: True` with a clean error code.
- During one round of testing, the same physical device instance
  reconnected **5 times within about 3 minutes** (new PnP instance ID each
  time), suggesting some instability in addition to the endpoint just not
  sticking — though this could equally have been the user physically
  swapping it between ports during testing, not spontaneous flakiness.
- Two separate power-management settings were found enabled and have been
  **disabled** as a precaution (not confirmed as the fix, but correct
  regardless for an always-on AV production box): USB Selective Suspend in
  the active power plan (was `Enabled` for both AC/DC, now `Disabled`), and
  the C-Media device's own "allow the computer to turn off this device to
  save power" flag (was `True`, now `False`).

**Bottom line interpretation:** the driver layer and the low-level MMDevice
endpoint-creation logic both work correctly and are not the problem. Whatever
is actually preventing the device from being *visible/usable* sits somewhere
above that — most likely genuine Windows system file corruption (see below),
possibly a corrupted default audio-effects/APO registration, or something
`sfc`/`DISM` can reach that manual registry inspection can't.

## SFC finding (2026-07-05, ~9:12 PM) — action pending reboot

`sfc /scannow` found and repaired 3 corrupted files:

- `C:\WINDOWS\System32\drivers\BthA2dp.sys`
- `C:\WINDOWS\System32\drivers\BthHfEnum.sys`
- `C:\WINDOWS\System32\drivers\bthmodem.sys`

These are **Bluetooth audio profile drivers** (A2DP / Hands-Free), not
directly part of the USB or onboard analog capture path being tested. This
is not a confirmed fix — it may be unrelated — but it's the only concrete
corruption found on the system, and it's plausible that a corrupted
Bluetooth audio driver could cause `AudioEndpointBuilder` to fail partway
through enumerating *all* audio endpoints (Bluetooth and otherwise) in a way
that would explain non-Bluetooth capture devices silently failing to stick
around too.

**Repaired driver files on disk do not take effect until reboot.** A reboot
was pending at the point this was written up — that's the next action.

## Next steps (in order) after the reboot

1. **Retest both paths**: plug the ClearClick interface back in, and try the
   front-panel line-in again. Check Sound Settings' Recording tab and OBS's
   audio input list.
2. If still nothing: run the built-in **Recording Audio troubleshooter**
   (Settings → System → Troubleshoot → Other troubleshooters → Recording
   Audio, or `msdt.exe /id AudioRecordingDiagnostic`). This requires
   interactive input (device selection), so it needs to be run by hand
   rather than scripted — but it runs internal Microsoft repair heuristics
   that go beyond what manual registry/log inspection can see.
3. If still nothing: try the plain **generic USB adapter** (the "small
   dongle" with two 3.5mm jacks, mentioned early on but never conclusively
   retested after the C-Media identification) — if it also fails identically,
   that's further confirmation the problem is systemic to this Windows
   install rather than specific to the ClearClick unit.
4. If still nothing: consider uninstalling the Realtek driver via Device
   Manager ("Uninstall device" + "Delete the driver software for this
   device"), rebooting, and letting Windows reinstall the generic/inbox HD
   Audio driver fresh — this tests whether the Realtek driver stack itself
   is the corrupted component, independent of the SFC-repaired Bluetooth
   drivers.
5. If still nothing after all of the above: this may need a deeper repair —
   `DISM /Online /Cleanup-Image /RestoreHealth` (a more thorough version of
   what SFC does, pulls from Windows Update or a mounted image to fix things
   SFC's local component store can't), or, as a last resort, an in-place
   Windows repair install.
