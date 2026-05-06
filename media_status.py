import argparse
import asyncio
import json
import sys
import threading
import time
from dataclasses import asdict, dataclass
from datetime import timedelta
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, unquote, urlparse


def configure_stdout() -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")


@dataclass(frozen=True)
class MediaStatus:
    title: Optional[str]
    artist: Optional[str]
    state: str
    position: int
    duration: int
    album: Optional[str]
    display: str


def load_media_manager():
    try:
        from winsdk.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as MediaManager,
        )
        return MediaManager
    except ImportError:
        pass

    try:
        from winrt.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as MediaManager,
        )
        return MediaManager
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency: install `winsdk` or `winrt-Windows.Media.Control`."
        ) from exc


def playback_state(status) -> str:
    name = getattr(status, "name", str(status)).lower()
    if "playing" in name:
        return "playing"
    if "paused" in name:
        return "paused"
    return "stopped"


def seconds(value) -> int:
    if value is None:
        return 0
    if isinstance(value, timedelta):
        return max(0, int(value.total_seconds()))
    total_seconds = getattr(value, "total_seconds", None)
    if callable(total_seconds):
        return max(0, int(total_seconds()))
    return max(0, int(value))


def format_time(total_seconds: int) -> str:
    total_seconds = max(0, int(total_seconds))
    minutes, secs = divmod(total_seconds, 60)
    return f"{minutes}:{secs:02d}"


def progress_bar(position: int, duration: int, width: int = 12) -> str:
    width = min(20, max(10, width))
    if duration <= 0:
        filled = 0
    else:
        filled = round((max(0, min(position, duration)) / duration) * width)
    return "█" * filled + "░" * (width - filled)


def state_icon(state: str) -> str:
    return "▶" if state == "playing" else "⏸"


def state_label(state: str) -> str:
    if state == "playing":
        return "PLAY"
    if state == "paused":
        return "PAUSE"
    return "STOP"


def display_line(
    title: Optional[str],
    artist: Optional[str],
    state: str,
    position: int,
    duration: int,
    bar_width: int,
) -> str:
    if not title and not artist:
        return "⏸ Nothing playing"

    icon = state_icon(state)
    name = title or "Unknown title"
    by = artist or "Unknown artist"
    bar = progress_bar(position, duration, bar_width)
    return f"{icon} {name} - {by} [{bar}] {format_time(position)}/{format_time(duration)}"


class PositionTracker:
    def __init__(self) -> None:
        self._last_key = None
        self._last_position = 0
        self._last_seen = time.monotonic()

    def update(self, title: Optional[str], artist: Optional[str], state: str, position: int, duration: int) -> int:
        now = time.monotonic()
        key = (title or "", artist or "", duration)

        if key != self._last_key:
            if state == "playing" and duration > 0 and position >= duration - 1:
                position = 0
            self._last_key = key
            self._last_position = position
            self._last_seen = now
            return position

        if state == "playing" and duration > 0:
            elapsed = max(0, int(now - self._last_seen))
            local_position = min(duration, self._last_position + elapsed)
            if position >= duration - 1 and self._last_position < duration - 1:
                position = local_position
            else:
                position = max(position, local_position)

        self._last_position = position
        self._last_seen = now
        return position


def normalize_metadata(title: Optional[str], artist: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    title = title.strip() if title else None
    artist = artist.strip() if artist else None

    if title and artist:
        title_index = artist.lower().find(title.lower())
        if title_index > 0:
            candidate = artist[:title_index].strip(" -–—")
            if candidate:
                artist = candidate
                return title, artist

        prefix = f"{title} - "
        if artist.lower().startswith(prefix.lower()):
            artist = artist[len(prefix):].strip() or None
        return title, artist

    if not title and artist:
        for separator in (" - ", " – ", " — "):
            if separator in artist:
                left, right = artist.split(separator, 1)
                if left.strip() and right.strip():
                    return right.strip(), left.strip()

    if title and not artist:
        for separator in (" - ", " – ", " — "):
            if separator in title:
                left, right = title.split(separator, 1)
                if left.strip() and right.strip():
                    return right.strip(), left.strip()

    return title, artist


async def read_status(manager, bar_width: int) -> MediaStatus:
    session = manager.get_current_session()
    if session is None:
        display = display_line(None, None, "stopped", 0, 0, bar_width)
        return MediaStatus(None, None, "stopped", 0, 0, None, display)

    try:
        props = await session.try_get_media_properties_async()
    except Exception:
        props = None

    try:
        playback_info = session.get_playback_info()
        state = playback_state(playback_info.playback_status)
    except Exception:
        state = "stopped"

    try:
        timeline = session.get_timeline_properties()
        position = seconds(timeline.position)
        duration = seconds(timeline.end_time)
        last_updated = getattr(timeline, "last_updated_time", None)
    except Exception:
        position = 0
        duration = 0
        last_updated = None

    title = (getattr(props, "title", None) or "").strip() or None
    artist = (getattr(props, "artist", None) or "").strip() or None
    title, artist = normalize_metadata(title, artist)
    album = (getattr(props, "album_title", None) or "").strip() or None

    if is_stale_finished_session(state, position, duration, last_updated):
        display = display_line(None, None, "stopped", 0, 0, bar_width)
        return MediaStatus(None, None, "stopped", 0, 0, None, display)

    display = display_line(title, artist, state, position, duration, bar_width)
    return MediaStatus(title, artist, state, position, duration, album, display)


def is_stale_finished_session(state: str, position: int, duration: int, last_updated) -> bool:
    if state != "paused" or duration <= 0 or position < duration - 1 or last_updated is None:
        return False
    if isinstance(last_updated, datetime):
        if last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - last_updated).total_seconds() > 30
    return False


def with_tracked_position(status: MediaStatus, tracker: PositionTracker, bar_width: int) -> MediaStatus:
    position = tracker.update(status.title, status.artist, status.state, status.position, status.duration)
    display = display_line(status.title, status.artist, status.state, position, status.duration, bar_width)
    return MediaStatus(
        status.title,
        status.artist,
        status.state,
        position,
        status.duration,
        status.album,
        display,
    )


def encode_status(status: MediaStatus, output_format: str) -> str:
    if output_format == "display":
        return status.display
    return json.dumps(asdict(status), ensure_ascii=False, separators=(",", ":"))


def beefweb_column(status: MediaStatus, pattern: str) -> str:
    pattern = unquote(pattern).lower()
    if "display" in pattern:
        return status.display
    if "progress" in pattern:
        return progress_bar(status.position, status.duration, 16)
    if "time" in pattern:
        return f"{format_time(status.position)}/{format_time(status.duration)}"
    if "title" in pattern:
        return status.title or "Nothing playing"
    if "artist" in pattern:
        return status.artist or ""
    if "album" in pattern:
        if not status.title and not status.artist:
            return "STOP 0:00/0:00"
        return f"{state_label(status.state)} {format_time(status.position)}/{format_time(status.duration)}"
    if "length" in pattern or "duration" in pattern:
        return str(status.duration)
    if "playback_time" in pattern or "position" in pattern:
        return str(status.position)
    return ""


def beefweb_player_payload(status: MediaStatus, trcolumns: str = "%artist%,%title%,%album%,%progress%,%time%,%display%") -> dict:
    columns = [beefweb_column(status, item.strip()) for item in trcolumns.split(",")]
    playback_state = "stopped" if status.display == "⏸ Nothing playing" else status.state
    return {
        "player": {
            "activeItem": {
                "columns": columns,
                "duration": float(status.duration),
                "index": 0,
                "playlistId": "gsm_tc",
                "playlistIndex": 0,
                "position": float(status.position),
            },
            "info": {
                "name": "GSMTC",
                "pluginVersion": "media_status",
                "title": "Windows GSMTC",
                "version": "1",
            },
            "playbackMode": 0,
            "playbackModes": ["Default"],
            "playbackState": playback_state,
            "volume": {
                "isMuted": False,
                "max": 0.0,
                "min": -100.0,
                "type": "db",
                "value": 0.0,
            },
        }
    }


def write_atomic(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text + "\n", encoding="utf-8")
    tmp.replace(path)


class LatestStatus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._status = MediaStatus(None, None, "stopped", 0, 0, None, "⏸ Nothing playing")
        self._updated_at = time.monotonic()

    def set(self, status: MediaStatus) -> None:
        with self._lock:
            self._status = status
            self._updated_at = time.monotonic()

    def get(self) -> MediaStatus:
        with self._lock:
            return self._status

    def adjusted(self, bar_width: int) -> MediaStatus:
        with self._lock:
            status = self._status
            updated_at = self._updated_at

        if status.state != "playing" or status.duration <= 0:
            return status

        elapsed = max(0, int(time.monotonic() - updated_at))
        position = min(status.duration, status.position + elapsed)
        display = display_line(status.title, status.artist, status.state, position, status.duration, bar_width)
        return MediaStatus(
            status.title,
            status.artist,
            status.state,
            position,
            status.duration,
            status.album,
            display,
        )


def start_http_server(host: str, port: int, latest: LatestStatus, bar_width: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path in ("/", "/status"):
                payload_text = encode_status(latest.adjusted(bar_width), "json")
                self.send_json(payload_text)
                return

            if parsed.path in ("/api/player", "/api/query"):
                query = parse_qs(parsed.query)
                trcolumns = query.get("trcolumns", ["%artist%,%title%,%album%"])[0]
                payload_text = json.dumps(
                    beefweb_player_payload(latest.adjusted(bar_width), trcolumns),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                self.send_json(payload_text)
                return

            if parsed.path == "/api/outputs":
                self.send_json('{"outputs":[]}')
                return

            if parsed.path == "/api/playlists":
                self.send_json('{"playlists":[]}')
                return

            if parsed.path == "/api":
                self.send_json('{"name":"GSMTC Beefweb shim","version":"1"}')
                return

            if parsed.path != "/":
                self.send_error(404)
                return

        def send_json(self, payload_text: str) -> None:
            payload = payload_text.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format, *args) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


async def run(args) -> None:
    MediaManager = load_media_manager()
    manager = await MediaManager.request_async()
    latest = LatestStatus()
    tracker = PositionTracker()
    server = None

    if args.mode == "http":
        server = start_http_server(args.host, args.port, latest, args.bar_width)
        print(f"http://{args.host}:{args.port}/status", flush=True)

    try:
        while True:
            status = with_tracked_position(await read_status(manager, args.bar_width), tracker, args.bar_width)
            latest.set(status)

            if args.mode == "console":
                print(encode_status(status, args.format), flush=True)
            elif args.mode == "file":
                write_atomic(args.output, encode_status(status, args.format))

            await asyncio.sleep(args.interval)
    finally:
        if server is not None:
            server.shutdown()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Poll Windows GSMTC media status and output JSON or OLED display text."
    )
    parser.add_argument("--mode", choices=("console", "file", "http"), default="console")
    parser.add_argument("--format", choices=("json", "display"), default="json")
    parser.add_argument("--output", type=Path, default=Path("output.txt"))
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--bar-width", type=int, default=12)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    args.interval = min(2.0, max(1.0, args.interval))
    args.bar_width = min(20, max(10, args.bar_width))
    return args


def main() -> None:
    configure_stdout()
    try:
        asyncio.run(run(parse_args()))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
