# GSMTC OLED Bridge

Lightweight Windows media bridge for SteelSeries OLED devices and SteelClock.

Shows live media info directly on supported OLED displays without requiring SteelSeries GG.

Supports:

* Song title
* Artist
* Play/Pause state
* Progress bar
* HTTP JSON endpoint
* File output mode

Works with:

* Spotify
* YouTube
* VLC
* Browser media
* Apple Music
* Any app exposing Windows GSMTC metadata

Compatible with:

* SteelSeries Apex OLED keyboards
* GameDAC Gen 2
* Arctis Nova Pro base stations
* steelclock-go

---

# Preview

```text
Song Name
Artist Name
▶ 1:34 █████░░░ 2:58
```

JSON output:

```json
{
  "title": "Song Name",
  "artist": "Artist",
  "state": "playing",
  "position": 94,
  "duration": 178,
  "display": "▶ Song Name - Artist [██████░░░░░░] 1:34/2:58"
}
```

---

# Quick Start

## 1. Clone the repository

```powershell
git clone https://github.com/geatspahiu/gsmtc-oled-bridge
cd gsmtc-oled-bridge
```

## 2. Install dependencies

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## 3. Run the media bridge

HTTP mode:

```powershell
python media_status.py --mode http
```

File mode:

```powershell
python media_status.py --mode file --format display --output output.txt
```

---

# Endpoints

JSON status:

```text
http://127.0.0.1:8765/status
```

SteelClock-compatible endpoint:

```text
http://127.0.0.1:8765/api/query
```

---

# SteelClock Setup

Copy the included profile:

```powershell
Copy-Item .\steelclock_gsm_tc_media_server.json "C:\Path\To\SteelClock\profiles\"
```

Then:

* launch SteelClock
* select the GSMTC profile
* start playback

The OLED should update automatically.

---

# One-Command Launcher

If SteelClock is installed in:

```text
Documents\steelclock-*-windows-amd64
```

Run:

```powershell
.\run_media_oled.ps1
```

Stop everything:

```powershell
.\stop_media_oled.ps1
```

---

# CLI Options

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

---

# Troubleshooting

## OLED shows STOP 0:00/0:00

Windows is not exposing an active GSMTC session.

Start playback and test:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/status
```

---

## SteelClock shows [Not running]

Verify the bridge is running:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/query
```

Verify the profile uses:

```json
"server_url": "http://localhost:8765"
```

---

# Requirements

* Windows 10/11
* Python 3.10+
* Media app with GSMTC support

Python 3.14 uses `winrt-*` packages automatically.

---

# License

MIT
