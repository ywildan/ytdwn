"""Configuration management for ytdwn."""

import os
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib


CONFIG_DIR = Path.home() / ".config" / "ytdwn"
CONFIG_FILE = CONFIG_DIR / "config.toml"


def _expand_path(path_str: str) -> Path:
    """Expand ~ and environment variables in path string."""
    return Path(os.path.expandvars(os.path.expanduser(path_str)))


def _get_default_download_dir() -> Path:
    """Get default download directory."""
    return Path.home() / "Downloads" / "youtube-dl"


def _get_default_music_dir() -> Path:
    """Get default music directory."""
    return Path.home() / "Downloads" / "youtube-dl"


def load_config() -> dict:
    """Load configuration from file with env var overrides."""
    config = {}

    # Start with defaults
    config["download_dir"] = str(_get_default_download_dir())
    config["music_dir"] = str(_get_default_music_dir())

    # Load from config file if it exists
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "rb") as f:
                file_config = tomllib.load(f)
                if "download_dir" in file_config:
                    config["download_dir"] = file_config["download_dir"]
                if "music_dir" in file_config:
                    config["music_dir"] = file_config["music_dir"]
        except Exception:
            # Ignore config file errors, use defaults
            pass

    # Override with environment variables
    if "YTDWN_DOWNLOAD_DIR" in os.environ:
        config["download_dir"] = os.environ["YTDWN_DOWNLOAD_DIR"]
    if "YTDWN_MUSIC_DIR" in os.environ:
        config["music_dir"] = os.environ["YTDWN_MUSIC_DIR"]

    # Expand paths
    config["download_dir"] = str(_expand_path(config["download_dir"]))
    config["music_dir"] = str(_expand_path(config["music_dir"]))

    return config


def get_download_dir() -> Path:
    """Get configured download directory."""
    return Path(load_config()["download_dir"])


def get_music_dir() -> Path:
    """Get configured music directory."""
    return Path(load_config()["music_dir"])


def ensure_config_dir() -> None:
    """Ensure config directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def create_default_config() -> None:
    """Create default config file if it doesn't exist."""
    ensure_config_dir()
    if not CONFIG_FILE.exists():
        default_config = f"""# ytdwn configuration
# download_dir = "~/Downloads/youtube-dl"
# music_dir = "~/Music"
"""
        CONFIG_FILE.write_text(default_config)