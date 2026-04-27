"""Media processing adapter using yt-dlp and pydub."""

from __future__ import annotations

import io
import logging
import os
import stat
import urllib.request
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

import yt_dlp
from pydub import AudioSegment

from mimesis.video_ingestion.domain.exceptions import MediaProcessingError
from mimesis.video_ingestion.ports.media_processor_port import MediaProcessorPort

logger = logging.getLogger(__name__)

_FORMAT = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"

# tv_embedded bypasses SABR streaming restriction and n-challenge JS requirement
# when downloading without cookies, which is necessary from cloud server IPs.
_NO_COOKIES_EXTRACTOR_ARGS: dict[str, object] = {"youtube": {"player_client": ["tv_embedded"]}}

# Deno is required by yt-dlp to solve YouTube's n-challenge (throttle bypass).
# Without it, cookie-authenticated downloads fail because the web client (the
# only client that supports cookies in yt-dlp ≥2026) always triggers n-challenge.
# We download Deno lazily to /tmp on first use; the binary persists for the
# lifetime of the worker instance so subsequent invocations skip the download.
_DENO_DIR = Path("/tmp/deno-runtime")
_DENO_BIN = _DENO_DIR / "deno"
_DENO_ZIP_URL = (
    "https://github.com/denoland/deno/releases/download/v2.7.13"
    "/deno-x86_64-unknown-linux-gnu.zip"
)


def _ensure_deno() -> None:
    """Download Deno to /tmp and add to PATH so yt-dlp can solve n-challenge."""
    if _DENO_BIN.exists():
        _add_deno_to_path()
        return
    _DENO_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading Deno for n-challenge solving (~50 MB)…")
    try:
        with urllib.request.urlopen(_DENO_ZIP_URL, timeout=120) as resp:
            zip_bytes = resp.read()
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            zf.extract("deno", str(_DENO_DIR))
        _DENO_BIN.chmod(_DENO_BIN.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        _add_deno_to_path()
        logger.info("Deno ready at %s", _DENO_BIN)
    except Exception as exc:
        logger.warning("Deno download failed (%s) — n-challenge may not be solved", exc)


def _add_deno_to_path() -> None:
    deno_dir = str(_DENO_DIR)
    if deno_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = f"{deno_dir}:{os.environ.get('PATH', '')}"


class YtDlpMediaProcessor(MediaProcessorPort):
    """Downloads source video and extracts MP3 audio using yt-dlp."""

    def __init__(self, cookies: str | None = None) -> None:
        self._cookies = cookies

    def download_source_video(self, youtube_url: str) -> bytes:
        if self._cookies:
            try:
                return self._download(youtube_url, cookies=self._cookies)
            except MediaProcessingError as exc:
                logger.warning("Download with cookies failed (%s) — retrying without cookies", exc)
        return self._download(youtube_url, cookies=None)

    def _download(self, youtube_url: str, cookies: str | None) -> bytes:
        try:
            with TemporaryDirectory() as tmpdir:
                ydl_opts: dict[str, object] = {
                    "format": _FORMAT,
                    "outtmpl": str(Path(tmpdir) / "source.%(ext)s"),
                    "quiet": True,
                    "no_warnings": True,
                    "merge_output_format": "mp4",
                }

                if cookies:
                    _ensure_deno()
                    cookie_path = Path(tmpdir) / "cookies.txt"
                    cookie_path.write_text(cookies)
                    ydl_opts["cookiefile"] = str(cookie_path)
                    # Download yt-dlp's EJS challenge solver script from GitHub.
                    # Required so Deno can solve the n-challenge that YouTube
                    # issues for authenticated (cookie) requests.
                    ydl_opts["remote_components"] = ["ejs:github"]
                else:
                    ydl_opts["extractor_args"] = _NO_COOKIES_EXTRACTOR_ARGS

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([youtube_url])

                result_path = Path(tmpdir) / "source.mp4"
                if not result_path.exists():
                    raise MediaProcessingError("yt-dlp did not produce an output file.")
                return result_path.read_bytes()
        except MediaProcessingError:
            raise
        except Exception as exc:
            raise MediaProcessingError(f"Failed to download source video: {exc}") from exc

    def extract_audio_mp3(self, source_video_bytes: bytes) -> bytes:
        try:
            with TemporaryDirectory() as tmpdir:
                video_path = Path(tmpdir) / "source.mp4"
                audio_path = Path(tmpdir) / "audio.mp3"
                video_path.write_bytes(source_video_bytes)

                audio = AudioSegment.from_file(video_path, format="mp4")
                audio.export(audio_path, format="mp3")
                return audio_path.read_bytes()
        except Exception as exc:
            raise MediaProcessingError(f"Failed to extract mp3 audio: {exc}") from exc
