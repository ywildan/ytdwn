#!/usr/bin/env python3
"""Music Player TUI - plays downloaded music."""

import os
import sys
import time
from pathlib import Path
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Container, ScrollableContainer
from textual.widgets import (
    Button, Header, Footer, Static, DataTable, ProgressBar,
    Label, ListItem, ListView, Rule,
)
from textual import work, on
from textual.reactive import reactive
from rich.text import Text

try:
    import mpv
except ImportError:
    print("❌ python-mpv not found. Install with: pip install python-mpv")
    sys.exit(1)

from config import get_download_dir, get_music_dir, ensure_config_dir

HOME = Path.home()
DEFAULT_DIR = get_download_dir()
DEFAULT_DIR.mkdir(parents=True, exist_ok=True)

MUSIC_DIR = get_music_dir()
MUSIC_DIR.mkdir(parents=True, exist_ok=True)

# Extensions to scan
AUDIO_EXTS = {'.mp3', '.m4a', '.webm', '.ogg', '.opus', '.flac', '.wav'}

# Ensure config directory exists
ensure_config_dir()


class MusicPlayer:
    """Wrapper around mpv for background playback."""

    def __init__(self):
        self.player = mpv.MPV(
            vo=None,              # No video (audio only)
            really_quiet=True,
            ytdl=False,
        )
        self.playlist: list[Path] = []
        self.current_index = -1
        self.duration = 0
        self.position = 0
        self.is_playing = False
        self.is_paused = False
        self._track_ended = False

        # Register EOF callback
        @self.player.event_callback('end-file')
        def on_end_file(event):
            if not self.is_paused and self.is_playing:
                self._track_ended = True

    def load_folder(self, folder: Path):
        """Load all audio files from folder recursively."""
        self.playlist = []
        for root, dirs, files in os.walk(folder):
            for f in sorted(files):
                path = Path(root) / f
                if path.suffix.lower() in AUDIO_EXTS:
                    self.playlist.append(path)

    def save_order(self):
        """Save current playlist order to file."""
        order_file = HOME / ".local/share/youtube-downloader/playlist_order.txt"
        order_file.parent.mkdir(parents=True, exist_ok=True)
        with open(order_file, "w") as f:
            for track in self.playlist:
                f.write(str(track) + "\n")

    def load_order(self, folder: Path) -> bool:
        """Load saved playlist order. Returns True if loaded successfully."""
        order_file = HOME / ".local/share/youtube-downloader/playlist_order.txt"
        if not order_file.exists():
            return False

        with open(order_file, "r") as f:
            saved_paths = [line.strip() for line in f if line.strip()]

        # Build new playlist from saved order (only include files that still exist)
        new_playlist = []
        for path_str in saved_paths:
            path = Path(path_str)
            if path.exists() and path.suffix.lower() in AUDIO_EXTS:
                new_playlist.append(path)

        # Add any new files not in saved order
        existing_paths = set(str(p) for p in new_playlist)
        for root, dirs, files in os.walk(folder):
            for f in sorted(files):
                path = Path(root) / f
                if path.suffix.lower() in AUDIO_EXTS and str(path) not in existing_paths:
                    new_playlist.append(path)

        if new_playlist:
            self.playlist = new_playlist
            return True
        return False

    def move_track(self, from_index: int, to_index: int):
        """Swap track from one position with another."""
        if from_index < 0 or from_index >= len(self.playlist):
            return
        if to_index < 0 or to_index >= len(self.playlist):
            return
        if from_index == to_index:
            return

        # Swap the two tracks
        self.playlist[from_index], self.playlist[to_index] = self.playlist[to_index], self.playlist[from_index]

        # Update current_index
        if self.current_index == from_index:
            self.current_index = to_index
        elif self.current_index == to_index:
            self.current_index = from_index

    def move_up(self, index: int):
        """Move track up in playlist (swap with previous)."""
        if index <= 0 or index >= len(self.playlist):
            return
        self.playlist[index], self.playlist[index-1] = self.playlist[index-1], self.playlist[index]
        if self.current_index == index:
            self.current_index = index - 1
        elif self.current_index == index - 1:
            self.current_index = index

    def move_down(self, index: int):
        """Move track down in playlist (swap with next)."""
        if index < 0 or index >= len(self.playlist) - 1:
            return
        self.playlist[index], self.playlist[index+1] = self.playlist[index+1], self.playlist[index]
        if self.current_index == index:
            self.current_index = index + 1
        elif self.current_index == index + 1:
            self.current_index = index

    def remove_track(self, index: int):
        """Remove track from playlist."""
        if index < 0 or index >= len(self.playlist):
            return
        del self.playlist[index]
        if self.current_index == index:
            self.current_index = -1
            self.stop()
        elif self.current_index > index:
            self.current_index -= 1

    def play(self, index: int = 0):
        """Play item at index."""
        if not self.playlist or index < 0 or index >= len(self.playlist):
            return
        self.current_index = index
        self._track_ended = False  # Reset end flag
        self.player.play(str(self.playlist[index]))
        self.player.pause = False
        self.is_playing = True
        self.is_paused = False

    def toggle_pause(self):
        """Toggle play/pause."""
        if not self.is_playing:
            return
        self.player.pause = not self.player.pause
        self.is_paused = self.player.pause

    def stop(self):
        """Stop playback."""
        self.player.stop()
        self.is_playing = False
        self.is_paused = False

    def next_track(self):
        """Play next track."""
        if self.current_index + 1 < len(self.playlist):
            self.play(self.current_index + 1)
        else:
            # Reached end of playlist
            self.is_playing = False
            self.is_paused = False

    def prev_track(self):
        """Play previous track."""
        if self.current_index - 1 >= 0:
            self.play(self.current_index - 1)

    def seek(self, position: float):
        """Seek to position in seconds."""
        if self.is_playing and not self.is_paused:
            self.player.seek(position, reference="absolute")

    def get_track_info(self) -> dict:
        """Get current track info."""
        if not self.playlist or self.current_index < 0:
            return {}
        path = self.playlist[self.current_index]
        return {
            "title": path.stem,
            "path": str(path),
            "index": self.current_index,
            "total": len(self.playlist),
        }

    def update_position(self):
        """Update position/duration from mpv."""
        try:
            if self.is_playing:
                self.position = self.player.time_pos or 0
                self.duration = self.player.duration or 0

                # Check if track ended using flag set by event callback
                # This is the authoritative mechanism - event callback sets _track_ended
                if self._track_ended:
                    self._track_ended = False
                    self.next_track()
                    return  # Prevent fallback from also triggering

                # Fallback: only check eof_reached if event callback didn't fire
                # This handles cases where the event callback might be missed
                if not self.is_paused and self.player.eof_reached:
                    # Additional guard: only trigger if position is at or near duration
                    if self.duration > 0 and self.position >= self.duration - 1.0:
                        self.next_track()
        except Exception:
            pass


class MusicApp(App):
    """Music Player TUI."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #player-grid {
        layout: grid;
        grid-size: 1;
        grid-rows: auto 1fr auto;
        height: 100%;
    }

    /* ── Top: Now Playing ── */
    #now-playing {
        height: auto;
        padding: 1 2;
        border-bottom: heavy $accent;
        background: $surface-darken-2;
        align: center middle;
    }

    #track-title {
        text-style: bold;
        color: $accent;
        text-align: center;
    }

    #track-meta {
        color: $text-muted;
        text-align: center;
        padding: 0;
    }

    #progress-area {
        padding: 0 2;
    }

    #time-label {
        color: $text-muted;
        text-align: center;
    }

    #progress-bar {
        margin: 0 0 1 0;
    }

    /* ── Middle: Playlist ── */
    #playlist-panel {
        height: 1fr;
        border-bottom: tall $surface;
        padding: 0;
    }

    #playlist-title {
        text-style: bold;
        color: $accent;
        padding: 1 1 0 1;
    }

    #playlist-table {
        height: 1fr;
    }

    #playlist-table > .datatable--cursor {
        background: $accent 15%;
    }

    #playlist-table > .datatable--hover {
        background: $accent 8%;
    }

    /* ── Bottom: Controls ── */
    #controls-bar {
        height: 4;
        background: $surface-darken-2;
        border-top: heavy $accent;
        padding: 0 2;
        align: center middle;
    }

    #controls-bar Button {
        margin: 0 1;
        min-width: 8;
    }

    #btn-play {
        min-width: 12;
        border: tall $success;
    }

    #btn-prev, #btn-next {
        border: tall $surface;
    }

    .reorder-btn {
        min-width: 6 !important;
    }

    #status-text {
        color: $text-muted;
        text-align: right;
        padding: 0 2;
    }

    .datatable--header {
        background: $surface-darken-2;
        text-style: bold;
        color: $accent;
    }

    /* ── Action column styling ── */
    #playlist-table .datatable--col-2,
    #playlist-table .datatable--col-3 {
        width: 3;
        text-align: center;
        color: $accent;
    }

    /* ── Drag and drop ── */
    #drag-overlay {
        height: auto;
        padding: 0 2;
        background: $accent 30%;
        border: tall $accent;
        text-align: center;
        color: $text;
        text-style: bold;
        display: none;
    }

    .dragging {
        background: $accent 25% !important;
        text-style: bold;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("space", "toggle_pause", "Play/Pause"),
        ("n", "next", "Next"),
        ("p", "prev", "Prev"),
        ("s", "stop", "Stop"),
        ("r", "rescan", "Rescan"),
        ("u", "move_up", "Move Up"),
        ("d", "move_down", "Move Down"),
        ("x", "remove_track", "Remove"),
    ]

    def __init__(self, start_path: Path = MUSIC_DIR):
        super().__init__()
        self.music = MusicPlayer()
        self.start_path = start_path
        self.folder_error: str | None = None

        # Validate and load music folder
        self._validate_and_load_folder(start_path)

        self.selected_row = 0
        # Drag state
        self.dragging = False
        self.drag_start_row = -1
        self.drag_current_row = -1

    def _validate_and_load_folder(self, folder: Path | str) -> None:
        """Validate folder and load playlist. Sets self.folder_error if invalid."""
        folder = Path(folder)
        self.folder_error = None

        if not folder.exists():
            self.folder_error = f"Directory not found: {folder}"
        elif not folder.is_dir():
            self.folder_error = f"Not a directory: {folder}"
        elif not os.access(folder, os.R_OK):
            self.folder_error = f"Cannot read directory (permission denied): {folder}"
        else:
            # Try to load saved order first
            if not self.music.load_order(folder):
                self.music.load_folder(folder)
            return

        # If we reach here, there was an error - start with empty playlist
        self.music.playlist = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="player-grid"):
            # Now Playing section
            with Container(id="now-playing"):
                yield Static("♫ Music Player", id="track-title")
                yield Static("", id="track-meta")

            # Progress bar
            with Container(id="progress-area"):
                yield ProgressBar(total=100, show_eta=False, id="progress-bar")
                yield Static("", id="time-label")

            # Playlist
            with Container(id="playlist-panel"):
                yield Static("📋 Playlist", id="playlist-title")
                yield DataTable(id="playlist-table", zebra_stripes=True, cursor_type="cell")
                # Drag overlay
                yield Static("", id="drag-overlay")

            # Controls
            with Horizontal(id="controls-bar"):
                yield Button("⬆ Up", id="btn-up", classes="reorder-btn", variant="default")
                yield Button("⬇ Down", id="btn-down", classes="reorder-btn", variant="default")
                yield Button("✕", id="btn-remove", classes="reorder-btn", variant="error")
                yield Button("│", id="btn-sep", disabled=True, variant="default")
                yield Button("⏮ Prev", id="btn-prev", variant="default")
                yield Button("▶ Play", id="btn-play", variant="success")
                yield Button("⏭ Next", id="btn-next", variant="default")
                yield Button("⏹ Stop", id="btn-stop", variant="error")

        # Status bar
        with Static(id="status-text"):
            yield Static("")

    def on_mount(self):
        self.title = "🎵 Music Player"
        self.sub_title = f"{len(self.music.playlist)} tracks"
        self._suppress_play = False
        self._load_playlist_table()
        self.query_one("#drag-overlay", Static).display = False

        # Show folder error if validation failed
        if self.folder_error:
            self.notify(self.folder_error, title="Music Folder Error", severity="error")
            self.query_one("#status-text", Static).update(f"⚠️ {self.folder_error}")

        # Start position update loop
        self.set_interval(0.5, self._update_position)

    def _load_playlist_table(self, highlight_row: int = -1):
        """Load playlist table with action buttons."""
        table = self.query_one("#playlist-table", DataTable)
        table.clear(columns=True)
        table.add_columns("#", "▲", "▼", "Title")

        for i, track in enumerate(self.music.playlist):
            # Determine styling
            if i == self.music.current_index:
                title = Text(f"♫ {track.stem[:50]}", style="bold green")
            else:
                title = track.stem[:50]

            row_idx = f"{i+1:03d}"
            # Up/down arrows (disabled for first/last)
            up = "▲" if i > 0 else "─"
            down = "▼" if i < len(self.music.playlist) - 1 else "─"
            table.add_row(row_idx, up, down, title)

        # Restore cursor position
        if highlight_row >= 0 and highlight_row < len(self.music.playlist):
            table.cursor_cell = (highlight_row, 3)  # Column 3 = Title

        # Save order after any modification
        self.music.save_order()

    def _update_position(self):
        """Update progress bar and time label."""
        self.music.update_position()

        pos = self.music.position
        dur = self.music.duration

        if dur > 0:
            pct = (pos / dur) * 100
            self.query_one("#progress-bar", ProgressBar).update(progress=pct)
            self.query_one("#time-label", Static).update(
                f"{self._format_duration(pos)} / {self._format_duration(dur)}"
            )
        else:
            self.query_one("#progress-bar", ProgressBar).update(progress=0)
            self.query_one("#time-label", Static).update("— / —")

        # Update now playing
        info = self.music.get_track_info()
        if info:
            self.query_one("#track-title", Static).update(
                f"♫ {info['title'][:60]}"
            )
            self.query_one("#track-meta", Static).update(
                f"{info['index']+1} of {info['total']}  •  {'⏸ Paused' if self.music.is_paused else '▶ Playing' if self.music.is_playing else '⏹ Stopped'}"
            )

        # Update play button label
        btn = self.query_one("#btn-play", Button)
        if self.music.is_paused:
            btn.label = "▶ Resume"
        elif self.music.is_playing:
            btn.label = "⏸ Pause"
        else:
            btn.label = "▶ Play"

    def _format_duration(self, seconds: float) -> str:
        if seconds <= 0 or seconds != seconds:
            return "—"
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        hours = int(minutes // 60)
        if hours > 0:
            return f"{hours}:{minutes%60:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    def on_mouse_down(self, event) -> None:
        """Start potential drag operation on mouse button press."""
        table = self.query_one("#playlist-table", DataTable)
        region = table.region
        mouse_y = getattr(event, 'screen_y', event.y)
        if (region.x <= event.screen_x < region.x + region.width and
            region.y <= mouse_y < region.y + region.height):
            # Account for header row (1) and scroll offset
            row = int(mouse_y - region.y - 1 + table.scroll_y)
            if 0 <= row < len(self.music.playlist):
                self.dragging = True
                self.drag_start_row = row
                self.drag_current_row = row
                self.selected_row = row

    def on_mouse_move(self, event) -> None:
        """Handle drag motion - update drop position."""
        if not self.dragging:
            return

        table = self.query_one("#playlist-table", DataTable)
        region = table.region
        mouse_y = getattr(event, 'screen_y', event.y)
        if (region.x <= event.screen_x < region.x + region.width and
            region.y <= mouse_y < region.y + region.height):
            # Account for header row (1) and scroll offset
            row = int(mouse_y - region.y - 1 + table.scroll_y)
            if 0 <= row < len(self.music.playlist):
                self.drag_current_row = row

                overlay = self.query_one("#drag-overlay", Static)
                if self.drag_current_row != self.drag_start_row:
                    track_name = self.music.playlist[self.drag_start_row].stem[:40]
                    overlay.update(f"📦 Move to position {self.drag_current_row + 1}: {track_name}")
                    overlay.styles.display = "block"
                    overlay.display = True
                else:
                    overlay.display = False

    def on_mouse_up(self, event) -> None:
        """Complete drag operation on mouse button release."""
        if not self.dragging:
            return

        self.dragging = False
        overlay = self.query_one("#drag-overlay", Static)
        overlay.display = False

        if self.drag_start_row != self.drag_current_row:
            from_idx = self.drag_start_row
            to_idx = self.drag_current_row

            self._suppress_play = True
            self.music.move_track(from_idx, to_idx)
            self.selected_row = to_idx
            self._load_playlist_table(highlight_row=to_idx)
            self.notify(f"Moved to position {to_idx + 1}", title="Drag & Drop")
            self.set_timer(0.1, lambda: setattr(self, '_suppress_play', False))

        self.drag_start_row = -1
        self.drag_current_row = -1

    @on(DataTable.CellSelected)
    def on_cell_selected(self, event: DataTable.CellSelected):
        """Handle cell clicks in playlist table."""
        if self._suppress_play:
            return

        row = event.coordinate.row
        column = event.coordinate.column  # 0-indexed: 0=#, 1=▲, 2=▼, 3=Title

        if column == 1:  # Up arrow clicked
            if row > 0:
                self._suppress_play = True
                self.music.move_up(row)
                self.selected_row = row - 1
                self._load_playlist_table(highlight_row=self.selected_row)
                self.notify(f"Moved up to position {row}", title="Reorder")
                self.set_timer(0.1, lambda: setattr(self, '_suppress_play', False))

        elif column == 2:  # Down arrow clicked
            if row < len(self.music.playlist) - 1:
                self._suppress_play = True
                self.music.move_down(row)
                self.selected_row = row + 1
                self._load_playlist_table(highlight_row=self.selected_row)
                self.notify(f"Moved down to position {row + 2}", title="Reorder")
                self.set_timer(0.1, lambda: setattr(self, '_suppress_play', False))

        elif column == 3:  # Title clicked - play track
            self.selected_row = row
            if row < len(self.music.playlist):
                self.music.play(row)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-play":
            if self.music.is_playing and not self.music.is_paused:
                self.music.toggle_pause()
            elif self.music.is_paused:
                self.music.toggle_pause()
            else:
                self.music.play(self.selected_row if self.selected_row < len(self.music.playlist) else 0)
        elif event.button.id == "btn-prev":
            self.music.prev_track()
        elif event.button.id == "btn-next":
            self.music.next_track()
        elif event.button.id == "btn-stop":
            self.music.stop()
        elif event.button.id == "btn-up":
            self.action_move_up()
        elif event.button.id == "btn-down":
            self.action_move_down()
        elif event.button.id == "btn-remove":
            self.action_remove_track()

    def action_toggle_pause(self):
        self.music.toggle_pause()

    def action_next(self):
        self.music.next_track()

    def action_prev(self):
        self.music.prev_track()

    def action_stop(self):
        self.music.stop()

    def action_move_up(self):
        """Move selected track up in playlist."""
        if self.selected_row > 0:
            self._suppress_play = True
            self.music.move_up(self.selected_row)
            self.selected_row -= 1
            self._load_playlist_table(highlight_row=self.selected_row)
            self.notify("Moved up", title="Reorder")
            self.set_timer(0.1, lambda: setattr(self, '_suppress_play', False))

    def action_move_down(self):
        """Move selected track down in playlist."""
        if self.selected_row < len(self.music.playlist) - 1:
            self._suppress_play = True
            self.music.move_down(self.selected_row)
            self.selected_row += 1
            self._load_playlist_table(highlight_row=self.selected_row)
            self.notify("Moved down", title="Reorder")
            self.set_timer(0.1, lambda: setattr(self, '_suppress_play', False))

    def action_remove_track(self):
        """Remove selected track from playlist."""
        if len(self.music.playlist) > 0 and 0 <= self.selected_row < len(self.music.playlist):
            self.music.remove_track(self.selected_row)
            if self.selected_row >= len(self.music.playlist):
                self.selected_row = len(self.music.playlist) - 1
            self._load_playlist_table()
            self.notify("Track removed", title="Remove")

    def action_rescan(self):
        self._validate_and_load_folder(self.start_path)
        self._load_playlist_table()
        if self.folder_error:
            self.notify(self.folder_error, title="Music Folder Error", severity="error")
            self.query_one("#status-text", Static).update(f"⚠️ {self.folder_error}")
        else:
            self.query_one("#status-text", Static).update("")
            self.notify(f"Rescanned: {len(self.music.playlist)} tracks", title="Rescan")
        self.sub_title = f"{len(self.music.playlist)} tracks"

    def on_quit(self):
        self.music.player.quit()


if __name__ == "__main__":
    app = MusicApp()
    app.run()
