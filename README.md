# GSMTC Media Server for SteelClock

Lightweight Windows media-status bridge for SteelSeries OLED displays. It reads
the current Windows Global System Media Transport Controls session and exposes it
as:

- Clean JSON at `http://127.0.0.1:8765/status`
- A small Beefweb-compatible API at `http://127.0.0.1:8765/api/query`
- Optional console or file output for other OLED tools

The included SteelClock profile uses the built-in Beefweb widget, so no browser
extension, clipboard bridge, Spotify token, or Foobar plugin is required.

Supported SteelClock targets include Apex keyboard OLEDs (128x40), GameDAC Gen 2,
and Arctis Nova Pro base stations (128x64). The included profile is tuned for
128x40 Apex keyboard displays and can be adapted for 128x64 devices.

## Preview

SteelClock 128x40 layout:

```text
Song Name
Artist-Album
PLAY 1:34/2:58
```

Long title and artist rows scroll left continuously.

Raw JSON example:

```json
{
  "title": "Song Name",
  "artist": "Artist",
  "state": "playing",
  "position": 94,
  "duration": 178,
  "album": null,
  "display": "▶ Song Name - Artist [██████░░░░░░] 1:34/2:58"
}
```

## Requirements

- Windows 10/11
- Python 3.10 or newer
- A media app that publishes metadata to Windows GSMTC
- Optional: [SteelClock]((https://github.com/pozitronik/steelclock-go)) for SteelSeries OLED output

Python 3.14 users are supported through the newer `winrt-*` packages. Older
Python versions use `winsdk`.

## Install

```powershell
git clone <your-repo-url>
cd <your-repo-folder>

py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run the Server

```powershell
python .\media_status.py --mode http --port 8765
```

Open:

```text
http://127.0.0.1:8765/status
```

Beefweb-compatible endpoint for SteelClock:

```text
http://127.0.0.1:8765/api/query
```

## SteelClock Setup

Copy the profile into SteelClock's `profiles` folder:

```powershell
Copy-Item .\steelclock_gsm_tc_media_server.json "C:\Path\To\SteelClock\profiles\gsm_tc_media_server.json"
```

Then either:

- Start SteelClock with `-config C:\Path\To\SteelClock\profiles\gsm_tc_media_server.json`
- Or start SteelClock normally and select `GSMTC Media Server` from the tray profile menu

### One-command launcher

If SteelClock is installed under `Documents\steelclock-*-windows-amd64`, run:

```powershell
.\run_media_oled.ps1
```

If SteelClock is somewhere else:

```powershell
$env:STEELCLOCK_DIR = "C:\Path\To\SteelClock"
.\run_media_oled.ps1
```

Stop the bridge and matching SteelClock profile process:

```powershell
.\stop_media_oled.ps1
```

## Other Output Modes

Console JSON:

```powershell
python .\media_status.py
```

Console display line:

```powershell
python .\media_status.py --format display
```

File output:

```powershell
python .\media_status.py --mode file --format display --output output.txt
```

## CLI Options

```text
--mode console|file|http
--format json|display
--output output.txt
--interval 1.0
--bar-width 12
--host 127.0.0.1
--port 8765
--config config.json
```

Notes:

- `--interval` is clamped to 1-2 seconds.
- `--bar-width` is clamped to 10-20 characters.
- HTTP mode always serves JSON and the Beefweb shim.
- `--config` accepts a small JSON object with any CLI option name, for example:

```json
{
  "mode": "file",
  "format": "display",
  "output": "output.txt",
  "interval": 1.0,
  "bar_width": 12,
  "host": "127.0.0.1",
  "port": 8765
}
```

## Metadata Cleanup

Some apps, especially browser players and Apple Music, publish odd metadata such
as:

```text
artist = "Artist — Song name - Single"
title = "Song name"
```

The app normalizes common cases so the OLED shows:

```text
title = "Song name"
artist = "Artist"
```

## Troubleshooting

### The OLED says `STOP 0:00/0:00`

Windows is not currently exposing a valid active GSMTC session. Start playback,
then check:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/status
```

### The time is wrong

The app can only read what Windows GSMTC publishes. If the visible player shows
one duration but `/status` shows a different duration, Windows is publishing stale
or incorrect metadata for that app. Browser players are the most common cause.

The app ignores old finished paused sessions instead of showing fake progress.

### SteelClock shows `[Not running]`

Check that the Python server is running:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/query
```

Check that the SteelClock profile points to:

```json
"server_url": "http://localhost:8765"
```

### GameSense fails but Direct works

That is normal if SteelSeries GG's GameSense service is not available. SteelClock
falls back to direct USB HID when it can.

## Files

- `media_status.py` - GSMTC poller and localhost server
- `steelclock_gsm_tc_media_server.json` - SteelClock profile
- `run_media_oled.ps1` - starts the server and SteelClock profile
- `stop_media_oled.ps1` - stops the bridge/profile processes
- `requirements.txt` - Python dependencies

## License

MIT. See `LICENSE`.
