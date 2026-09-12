#!/usr/bin/env python3
"""YouTube Downloader - Terminal UI (v2.1)"""

import asyncio
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from collections import deque

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, ScrollableContainer, Container
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button, Header, Footer, Input, Select, Static, ProgressBar,
    Markdown, DataTable, Log, Rule, Label, ListView, ListItem, Tabs, Tab,
)
from textual import work, on
from textual.reactive import reactive
from textual.color import Color
from rich.text import Text

HOME = Path.home()
DEFAULT_DIR = HOME / "Downloads" / "youtube-dl"
DEFAULT_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_FILE = HOME / ".local/share/youtube-downloader/history.txt"
HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

YTDLP = "yt-dlp"


def is_playlist(url: str) -> bool:
    return "list=" in url or "/playlist" in url


def get_playlist_info(url: str) -> tuple[int | None, str]:
    """Return (count, title) or (None, '')"""
    try:
        result = subprocess.run(
            [YTDLP, "--flat-playlist", "--print", "%(playlist_count)s|%(playlist_title)s", url],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and "|" in result.stdout.strip():
            parts = result.stdout.strip().split("|", 1)
            if parts[0].isdigit():
                return int(parts[0]), parts[1]
    except Exception:
        pass
    return None, ""


def get_video_title(url: str) -> str:
    """Get actual video title from URL."""
    try:
        result = subprocess.run(
            [YTDLP, "--print", "%(title)s", "--no-warnings", "--quiet", url],
            capture_output=True, text=True, timeout=30
        )
        return result.stdout.strip() or ""
    except Exception:
        return ""


def append_history(entry: str):
    """Append entry to history file."""
    with open(HISTORY_FILE, "a") as f:
        f.write(entry + "\n")


def load_history(limit: int = 50) -> list[list[str]]:
    """Load history entries as list of [time, mode, status, title]."""
    if not HISTORY_FILE.exists():
        return []
    lines = HISTORY_FILE.read_text().strip().split("\n")
    entries = []
    for line in lines[-limit:]:
        parts = line.split("|", 3)
        if len(parts) == 4:
            entries.append(parts)
    return list(reversed(entries))


class InlineDownloadScreen(Screen):
    """Inline download screen."""

    BINDINGS = [("escape", "cancel", "Cancel"), ("backspace", "go_back", "Back")]

    def __init__(self, url, mode, quality, output_dir, is_playlist=False, item_count=0, video_title=""):
        super().__init__()
        self.url = url
        self.mode = mode
        self.quality = quality
        self.output_dir = output_dir
        self.is_playlist = is_playlist
        self.item_count = item_count
        self.video_title = video_title
        self.cancelled = False
        self.process = None
        self.start_time = None
        self.success = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Static("", id="dl-status-icon", classes="dl-icon"),
            Static("", id="dl-title", classes="dl-title"),
            Static("", id="dl-meta", classes="dl-meta"),
            Rule(),
            ProgressBar(total=100, show_eta=True, id="dl-progress"),
            Static("", id="dl-percent", classes="dl-percent"),
            Rule(),
            Log(id="dl-log", auto_scroll=True, classes="dl-log"),
            Rule(),
            Horizontal(
                Button("⛔ Cancel", id="cancel-btn", variant="error"),
                Button("← Back", id="back-btn", variant="default", disabled=True),
                id="dl-buttons",
            ),
            id="dl-container",
        )

    def on_mount(self):
        self.start_time = datetime.now()
        mode_icon = "🎵" if self.mode == "audio" else "🎬"
        type_label = f"Playlist ({self.item_count} items)" if self.is_playlist else "Single"
        self.query_one("#dl-status-icon", Static).update(f"{mode_icon}  DOWNLOADING")
        # Show actual video title, fallback to URL
        display_title = self.video_title if self.video_title else self.url
        self.query_one("#dl-title", Static).update(display_title[:80])
        self.query_one("#dl-meta", Static).update(f"{type_label}  →  {self.output_dir}")
        self.download_job()

    @work(exclusive=True)
    async def download_job(self):
        cmd = self._build_cmd()
        log_widget = self.query_one("#dl-log", Log)
        progress_widget = self.query_one("#dl-progress", ProgressBar)
        percent_widget = self.query_one("#dl-percent", Static)

        log_widget.write_line(f"💿 Starting download...")
        log_widget.write_line(f"📁 Output: {self.output_dir}")
        log_widget.write_line("─" * 40)

        # Start at 0%
        progress_widget.update(progress=0)
        percent_widget.update("0.0%")

        try:
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            async for line in self.process.stdout:
                line_str = line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    continue
                log_widget.write_line(line_str)

                # Parse progress: find "XX.X%" pattern
                if "[download]" in line_str and "%" in line_str:
                    try:
                        # Look for pattern like "12.3%" anywhere in line
                        import re as _re
                        match = _re.search(r'(\d+\.?\d*)%', line_str)
                        if match:
                            pct = float(match.group(1))
                            if 0 <= pct <= 100:
                                progress_widget.update(progress=pct)
                                percent_widget.update(f"{pct:.1f}%")
                    except (ValueError, IndexError):
                        pass

            await self.process.wait()
            elapsed = (datetime.now() - self.start_time).total_seconds()

            if self.cancelled:
                log_widget.write_line("\n⛔ Cancelled by user")
                self.query_one("#dl-status-icon", Static).update("⛔ CANCELLED")
                self._save_history("cancelled")
            elif self.process.returncode == 0:
                self.success = True
                progress_widget.update(progress=100)
                percent_widget.update("100.0%")
                log_widget.write_line(f"\n✅ Done in {elapsed:.1f}s")
                self.query_one("#dl-status-icon", Static).update("✅ COMPLETE")
                self._save_history("done")
            else:
                log_widget.write_line(f"\n❌ Failed (exit: {self.process.returncode})")
                self.query_one("#dl-status-icon", Static).update("❌ FAILED")
                self._save_history("failed")

            self.query_one("#back-btn", Button).disabled = False
            self.query_one("#cancel-btn", Button).disabled = True
            self.query_one("#dl-buttons", Horizontal).refresh()

        except Exception as e:
            log_widget.write_line(f"\n❌ Error: {e}")
            self.query_one("#dl-status-icon", Static).update("❌ ERROR")
            self._save_history("failed")

    def _save_history(self, status: str):
        """Save to history with actual video title."""
        mode_str = "audio" if self.mode == "audio" else "video"
        # Priority: actual title > fallback
        if self.video_title:
            title = self.video_title
        elif self.is_playlist:
            title = f"playlist ({self.item_count} videos)"
        else:
            title = self.url.split("/")[-1] if "/" in self.url else self.url
        entry = f"{datetime.now().strftime('%Y-%m-%d %H:%M')}|{mode_str}|{status}|{title}"
        append_history(entry)

    def _build_cmd(self):
        cmd = [YTDLP, "--newline"]
        if self.is_playlist:
            cmd += ["--yes-playlist"]
        else:
            cmd += ["--no-playlist"]

        if self.is_playlist:
            cmd += ["-o", str(Path(self.output_dir) / "%(playlist_title)s/%(playlist_index)03d - %(title)s.%(ext)s")]
        else:
            cmd += ["-o", str(Path(self.output_dir) / "%(title)s.%(ext)s")]

        if self.mode == "audio":
            cmd += ["-f", "bestaudio/best", "-x", "--audio-format", "mp3", "--audio-quality", self.quality]
        else:
            q = self.quality
            if q == "best":
                fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
            elif q == "1080":
                fmt = "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]"
            elif q == "720":
                fmt = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]"
            else:
                fmt = "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]"
            cmd += ["-f", fmt, "--merge-output-format", "mp4"]

        cmd.append(self.url)
        return cmd

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.cancelled = True
            if self.process:
                self.process.terminate()
        elif event.button.id == "back-btn":
            self.dismiss(self.success)

    def action_cancel(self):
        self.cancelled = True
        if self.process:
            self.process.terminate()

    def action_go_back(self):
        """Go back to main form."""
        self.dismiss(self.success)


class DownloadApp(App):
    """Main TUI Application - v2.1 Design."""

    CSS = """
    /* ── Layout ── */
    #app-grid {
        layout: grid;
        grid-size: 1;
        grid-rows: 1fr auto;
        height: 100%;
    }

    /* ── Header strip ── */
    #header-strip {
        height: 3;
        background: $surface-darken-2;
        border-bottom: heavy $accent;
        padding: 0 2;
        align: center middle;
    }

    #header-title {
        text-style: bold;
        color: $accent;
    }

    #header-sub {
        text-style: italic;
        color: $text-muted;
        text-align: center;
    }

    /* ── Main content area ── */
    #main-area {
        layout: horizontal;
        height: 1fr;
    }

    /* ── Left: Form ── */
    #form-panel {
        width: 60%;
        padding: 1 2;
        border-right: tall $surface;
        height: 100%;
        overflow-y: auto;
    }

    /* ── Right: History ── */
    #history-panel {
        width: 40%;
        height: 100%;
        border-left: tall $surface;
        padding: 1;
    }

    #history-title {
        text-style: bold;
        color: $accent;
        padding: 0 0 1 0;
    }

    #history-table {
        height: 1fr;
    }

    #history-table > .datatable--cursor {
        background: $accent 20%;
    }

    /* ── Form elements ── */
    #url-input {
        margin: 0 0 1 0;
        border: tall $accent;
    }

    #url-input:focus {
        border: tall $success;
    }

    #info-box {
        padding: 1;
        margin: 0 0 1 0;
        border: tall $surface;
        background: $surface-darken-1;
        min-height: 3;
    }

    #info-box .info-label {
        color: $text-muted;
    }

    #info-box .info-value {
        text-style: bold;
        color: $text;
    }

    .form-row {
        height: auto;
        margin: 0 0 1 0;
    }

    .form-row Label {
        color: $text-muted;
        padding: 0 1 0 0;
        width: 12;
        content-align: center middle;
    }

    Select {
        width: 1fr;
    }

    #output-input {
        width: 1fr;
        margin: 0 1 0 0;
    }

    /* ── Buttons ── */
    #action-row {
        height: auto;
        margin: 1 0 0 0;
        align: left middle;
    }

    #download-btn {
        min-width: 16;
        margin: 0 1 0 0;
    }

    #clear-btn {
        min-width: 10;
    }

    /* ── Status bar ── */
    #status-bar {
        height: 3;
        background: $surface-darken-2;
        border-top: heavy $accent;
        padding: 0 2;
        align: center middle;
    }

    #status-text {
        color: $text;
    }

    #status-hint {
        color: $text-muted;
        text-align: right;
    }

    /* ── Download screen ── */
    #dl-container {
        padding: 1 4;
        height: 100%;
        overflow-y: auto;
    }

    .dl-icon {
        text-style: bold;
        text-align: center;
        color: $accent;
        padding: 1 0 0 0;
    }

    .dl-title {
        text-align: center;
        color: $text;
        padding: 0 0 1 0;
    }

    .dl-meta {
        text-align: center;
        color: $text-muted;
        padding: 0 0 1 0;
    }

    #dl-progress {
        margin: 1 0;
        border: tall $surface;
    }

    .dl-percent {
        text-align: center;
        text-style: bold;
        color: $accent;
        padding: 0 0 1 0;
    }

    .dl-log {
        height: 1fr;
        border: tall $surface;
        background: $surface-darken-2;
        padding: 0 1;
    }

    #dl-buttons {
        padding: 1 0 0 0;
        height: auto;
    }

    #dl-buttons Button {
        margin: 0 1 0 0;
    }

    /* ── Scrollbar ── */
    ScrollableContainer {
        scrollbar-size: 1 1;
    }

    .datatable--header {
        background: $surface-darken-2;
        text-style: bold;
        color: $accent;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "download", "Download"),
        ("c", "clear", "Clear"),
        ("r", "refresh_history", "Refresh"),
        ("v", "paste_clipboard", "Paste"),
        ("backspace", "go_back", "Back"),
    ]

    url_text = reactive("")
    detected_type = reactive("")
    detected_count = reactive(0)
    detected_title = reactive("")

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="app-grid"):
            with Container(id="main-area"):
                # Left panel: Form
                with ScrollableContainer(id="form-panel"):
                    yield Static("🎬🎵  YOUTUBE DOWNLOADER", id="header-title")
                    yield Static("Single video or full playlist — audio or video", id="header-sub")
                    yield Input(placeholder="  Paste YouTube URL here...", id="url-input")
                    yield Static("", id="info-box")

                    # Type + Quality in one row
                    with Horizontal(classes="form-row"):
                        yield Label("Type:")
                        yield Select(
                            [("🎵 Audio (MP3)", "audio"), ("🎬 Video (MP4)", "video")],
                            value="audio",
                            id="type-select",
                        )

                    with Horizontal(classes="form-row"):
                        yield Label("Quality:")
                        yield Select(
                            [("Best (320kbps)", "0"), ("Good (192kbps)", "2"), ("Medium (128kbps)", "5"), ("Low (64kbps)", "7")],
                            value="0",
                            id="quality-audio",
                        )
                        yield Select(
                            [("Best (highest)", "best"), ("1080p", "1080"), ("720p", "720"), ("480p", "480")],
                            value="best",
                            id="quality-video",
                            disabled=True,
                        )

                    with Horizontal(classes="form-row"):
                        yield Label("Output:")
                        yield Input(
                            value=str(DEFAULT_DIR),
                            placeholder="Output directory",
                            id="output-input",
                        )

                    with Horizontal(id="action-row"):
                        yield Button("▶  Download", id="download-btn", variant="success")
                        yield Button("🗑  Clear", id="clear-btn", variant="default")

                # Right panel: History
                with Container(id="history-panel"):
                    yield Static("📋  HISTORY", id="history-title")
                    yield DataTable(id="history-table", zebra_stripes=True)

        # Status bar
        with Horizontal(id="status-bar"):
            yield Static("Ready", id="status-text")
            yield Static(" [d]ownload  [c]lear  [r]efresh  [v]paste  [bs]back  [q]uit", id="status-hint")

    def on_mount(self):
        self.query_one("#url-input", Input).focus()
        self._refresh_history()

    def _refresh_history(self):
        """Reload history table from file."""
        table = self.query_one("#history-table", DataTable)
        table.clear(columns=True)
        table.add_columns("When", "Type", "Status", "Title")

        entries = load_history(30)
        for entry in entries:
            # Color-code status
            status = entry[2]
            if status == "done":
                status_text = Text("✅ done", style="bold green")
            elif status == "cancelled":
                status_text = Text("⛔ skip", style="yellow")
            else:
                status_text = Text("❌ fail", style="red")

            # Shorten time display
            when = entry[0][5:] if len(entry[0]) > 5 else entry[0]  # remove year
            when = when[:-3] if len(when) > 5 else when  # remove seconds

            # Mode icon
            mode_icon = "🎵" if entry[1] == "audio" else "🎬"

            # Truncate title
            title = entry[3][:35] + "…" if len(entry[3]) > 35 else entry[3]

            table.add_row(when, f"{mode_icon} {entry[1]}", status_text, title)

    def watch_url_text(self, value):
        if value and re.match(r"https?://(www\.)?(youtube\.com|youtu\.be)", value):
            self._detect_url(value)
        elif not value:
            self.query_one("#info-box", Static).update("")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "url-input":
            self.url_text = event.value

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "url-input":
            self._detect_url(event.value)

    def _detect_url(self, url: str):
        if not url:
            return
        self.query_one("#info-box", Static).update("⏳ Checking URL...")

        try:
            if is_playlist(url):
                count, title = get_playlist_info(url)
                self.detected_count = count or 0
                self.detected_title = title
                self.query_one("#info-box", Static).update(
                    f"📋 Playlist Detected\n"
                    f"   Title: {title or 'Unknown'}\n"
                    f"   Videos: {count or '?'}"
                )
            else:
                title = get_video_title(url)
                self.detected_title = title
                self.query_one("#info-box", Static).update(
                    f"🎬 Single Video\n"
                    f"   Title: {title}"
                )
        except Exception as e:
            self.query_one("#info-box", Static).update(f"⚠️ Error: {e}")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "type-select":
            is_audio = event.value == "audio"
            self.query_one("#quality-audio", Select).disabled = not is_audio
            self.query_one("#quality-video", Select).disabled = is_audio

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "download-btn":
            self.action_download()
        elif event.button.id == "clear-btn":
            self.action_clear()

    def action_paste_clipboard(self):
        """Paste from clipboard (wl-paste for Wayland)."""
        try:
            # Try wl-paste first (Wayland)
            result = subprocess.run(
                ["wl-paste", "--no-newline"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                clipboard_text = result.stdout.strip()
            else:
                # Fallback to xclip (X11)
                result = subprocess.run(
                    ["xclip", "-selection", "clipboard", "-o"],
                    capture_output=True, text=True, timeout=5
                )
                clipboard_text = result.stdout.strip() if result.returncode == 0 else ""
        except (FileNotFoundError, subprocess.TimeoutExpired):
            clipboard_text = ""

        if clipboard_text:
            self.query_one("#url-input", Input).value = clipboard_text
            self.url_text = clipboard_text
            self.query_one("#status-text", Static).update("📋 Pasted from clipboard")
            self._detect_url(clipboard_text)
        else:
            self.query_one("#status-text", Static).update("⚠️ Clipboard is empty or not available")

    def action_go_back(self):
        """Go back to previous screen or clear form."""
        # If we're in a modal/dismiss it
        if self.screen_stack[-1] is not self:
            self.pop_screen()
            return
        # Otherwise clear form as "back" action
        self.action_clear()

    def action_clear(self):
        self.query_one("#url-input", Input).value = ""
        self.query_one("#info-box", Static).update("")
        self.query_one("#status-text", Static).update("Cleared")
        self.query_one("#url-input", Input).focus()

    def action_refresh_history(self):
        self._refresh_history()
        self.query_one("#status-text", Static).update("History refreshed")

    def action_download(self):
        url = self.query_one("#url-input", Input).value.strip()
        if not url:
            self.notify("URL is empty!", severity="error")
            return

        if not re.match(r"https?://(www\.)?(youtube\.com|youtu\.be)", url):
            self.notify("Invalid URL! Must be from youtube.com or youtu.be", severity="error")
            return

        mode = self.query_one("#type-select", Select).value
        if mode == "audio":
            quality = self.query_one("#quality-audio", Select).value
        else:
            quality = self.query_one("#quality-video", Select).value

        output = self.query_one("#output-input", Input).value.strip()
        output_dir = output if output else str(DEFAULT_DIR)
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        is_pl = is_playlist(url)
        count = self.detected_count if is_pl else 0

        # Get actual video title for history and display
        video_title = ""
        if not is_pl:
            video_title = get_video_title(url)

        self.push_screen(
            InlineDownloadScreen(
                url=url,
                mode=mode,
                quality=quality,
                output_dir=output_dir,
                is_playlist=is_pl,
                item_count=count,
                video_title=video_title,
            ),
            callback=self._on_download_complete,
        )

    def _on_download_complete(self, success):
        """Called when download screen dismisses."""
        self._refresh_history()
        if success:
            self.query_one("#status-text", Static).update("✅ Download complete!")
        else:
            self.query_one("#status-text", Static).update("Download finished")


if __name__ == "__main__":
    app = DownloadApp()
    app.run()
