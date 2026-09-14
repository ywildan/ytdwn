#!/usr/bin/env python3
"""YouTube Downloader - Single video/audio or full playlist."""

import subprocess
import sys
import os
import re
from pathlib import Path

from config import get_download_dir, ensure_config_dir

DEFAULT_DIR = get_download_dir()
DEFAULT_DIR.mkdir(parents=True, exist_ok=True)

# Ensure config directory exists
ensure_config_dir()

YTDLP = "yt-dlp"


def is_playlist(url: str) -> bool:
    return "list=" in url or "/playlist" in url


def get_playlist_count(url: str) -> int | None:
    """Return number of videos in playlist, or None if not a playlist."""
    if not is_playlist(url):
        return None
    try:
        result = subprocess.run(
            [YTDLP, "--flat-playlist", "--print", "%(playlist_count)s", url],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip().isdigit():
            return int(result.stdout.strip())
    except Exception:
        pass
    return None


def get_video_title(url: str) -> str:
    try:
        result = subprocess.run(
            [YTDLP, "--print", "%(title)s", "--no-warnings", "--quiet", url],
            capture_output=True, text=True, timeout=30
        )
        return result.stdout.strip() or "output"
    except Exception:
        return "output"


PROGRESS_MARKER = "YTDWN_PROGRESS|"


def build_cmd(url: str, mode: str, quality: str, output_dir: Path, playlist: bool = False) -> list[str]:
    cmd = [YTDLP, "--no-warnings", "--newline"]

    # Use progress template with custom marker for reliable parsing
    # download: is a type selector, not literal output. We embed our own marker.
    cmd += ["--progress-template", f"download:{PROGRESS_MARKER}%(progress._percent_str)s|%(progress._eta_str)s|%(progress._speed_str)s"]

    if playlist:
        cmd += ["--yes-playlist"]
    else:
        cmd += ["--no-playlist"]

    # Template output
    if playlist:
        cmd += ["-o", str(output_dir / "%(playlist_title)s/%(playlist_index)03d - %(title)s.%(ext)s")]
    else:
        cmd += ["-o", str(output_dir / "%(title)s.%(ext)s")]

    if mode == "audio":
        cmd += [
            "-f", "bestaudio/best",
            "-x", "--audio-format", "mp3",
            "--audio-quality", quality,  # 0=best, 9=worst
            "--embed-thumbnail",
            "--parse-metadata", "title:%(meta_title)s",
        ]
    else:  # video
        if quality == "best":
            fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        elif quality == "1080":
            fmt = "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]"
        elif quality == "720":
            fmt = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]"
        else:  # 480
            fmt = "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]"
        cmd += ["-f", fmt, "--merge-output-format", "mp4"]

    cmd.append(url)
    return cmd


def download(url: str, mode: str, quality: str, output_dir: Path) -> bool:
    playlist = is_playlist(url)
    cmd = build_cmd(url, mode, quality, output_dir, playlist)

    print(f"\n{'='*50}")
    print(f"  Mode   : {'🎵 Audio only' if mode == 'audio' else '🎬 Video'}")
    print(f"  Type   : {'Playlist' if playlist else 'Single'}")
    if mode == "audio":
        q_label = {"0": "Best (320kbps)", "2": "Good (192kbps)", "5": "Medium (128kbps)", "7": "Low (64kbps)"}.get(quality, quality)
        print(f"  Quality: {q_label}")
    else:
        q_label = {"best": "Best", "1080": "1080p", "720": "720p", "480": "480p"}.get(quality, quality)
        print(f"  Quality: {q_label}")
    print(f"  Output : {output_dir}")
    print(f"{'='*50}\n")

    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        # Pattern: YTDWN_PROGRESS|<pct>%|<eta>|<speed>
        # _percent_str may have leading whitespace, e.g. "  0.0%" or " 12.4%"
        progress_pattern = re.compile(rf'{re.escape(PROGRESS_MARKER)}(\s*\d+\.?\d*)%\|([^|]*)\|([^|]*)')

        for line in process.stdout:
            line = line.rstrip()
            if not line:
                continue

            match = progress_pattern.search(line)
            if match:
                pct_str, eta, speed = match.groups()
                try:
                    pct = float(pct_str.strip())
                    if 0 <= pct <= 100:
                        print(f"\r  Progress: {pct:.1f}% | ETA: {eta} | Speed: {speed}", end="", flush=True)
                except ValueError:
                    pass
            else:
                print(f"  {line}")

        process.wait()
        print()  # Newline after progress
        return process.returncode == 0
    except KeyboardInterrupt:
        print("\n\n⛔ Dibatalkan oleh user.")
        return False
    except FileNotFoundError:
        print(f"\n❌ '{YTDLP}' tidak ditemukan. Install dengan: pip install yt-dlp")
        return False


def menu_quality(mode: str) -> str:
    if mode == "audio":
        print("\nPilih kualitas audio:")
        print("  1. Best  (320kbps)")
        print("  2. Good  (192kbps)")
        print("  3. Medium (128kbps)")
        print("  4. Low   (64kbps)")
        choice = input("Pilih [1-4, default=1]: ").strip() or "1"
        mapping = {"1": "0", "2": "2", "3": "5", "4": "7"}
        return mapping.get(choice, "0")
    else:
        print("\nPilih kualitas video:")
        print("  1. Best (highest available)")
        print("  2. 1080p")
        print("  3. 720p")
        print("  4. 480p")
        choice = input("Pilih [1-4, default=1]: ").strip() or "1"
        mapping = {"1": "best", "2": "1080", "3": "720", "4": "480"}
        return mapping.get(choice, "best")


def main():
    print("\n🎬🎵  YOUTUBE DOWNLOADER  🎵🎸")
    print("   Download single video/audio or full playlist\n")

    url = input("Masukkan URL YouTube: ").strip()
    if not url:
        print("❌ URL kosong.")
        sys.exit(1)

    if not re.match(r"https?://(www\.)?(youtube\.com|youtu\.be)", url):
        print("❌ URL tidak valid. Harus dari youtube.com atau youtu.be")
        sys.exit(1)

    # Cek playlist
    playlist_count = get_playlist_count(url)
    if playlist_count is not None:
        print(f"\n📋 Terdeteksi PLAYLIST dengan {playlist_count} video.")

    # Pilih mode
    print("\nPilih tipe download:")
    print("  1. 🎵 Audio saja (MP3)")
    print("  2. 🎬 Video (MP4)")
    mode_choice = input("Pilih [1-2, default=1]: ").strip() or "1"
    mode = "audio" if mode_choice == "1" else "video"

    # Kualitas
    quality = menu_quality(mode)

    # Output dir
    custom = input(f"\nOutput dir [default: {DEFAULT_DIR}]: ").strip()
    output_dir = Path(custom).expanduser() if custom else DEFAULT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Confirm
    if playlist_count and playlist_count > 5:
        confirm = f"\n⚠️  Download {playlist_count} video? [y/N]: "
        if input(confirm).strip().lower() != "y":
            print("Dibatalkan.")
            sys.exit(0)

    # Go!
    success = download(url, mode, quality, output_dir)

    if success:
        print(f"\n✅ Selesai! File tersimpan di: {output_dir}")
    else:
        print("\n❌ Download gagal.")


if __name__ == "__main__":
    main()
