"""
Configuration module for Etkinliktoplama data pipeline.
Provides load_sources_config, load_sources, and get_output_dir.
"""

import json
import os
from typing import List, Dict, Any

def get_project_root() -> str:
    """Returns absolute path to project root directory."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_output_dir() -> str:
    """Returns absolute path to output directory where generated JSON files are written."""
    env_dir = os.getenv("OUTPUT_DIR", "").strip()
    if env_dir:
        return os.path.abspath(env_dir)
    return get_project_root()

def load_sources_config() -> List[Dict[str, Any]]:
    """Loads sources configuration from config/sources.json."""
    root = get_project_root()
    config_path = os.path.join(root, "config", "sources.json")

    if not os.path.exists(config_path):
        config_path = os.path.join(root, "config", "sources.default.json")

    if not os.path.exists(config_path):
        # Fallback default sources
        return [
            {"id": "community", "enabled": True},
            {"id": "web_social", "enabled": True},
            {"id": "ticketmaster", "enabled": True},
            {"id": "local_official", "enabled": True},
            {"id": "federations", "enabled": True},
            {"id": "pages", "enabled": True},
            {"id": "wikidata", "enabled": True},
        ]

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data.get("sources", [])
            elif isinstance(data, list):
                return data
    except Exception as e:
        print(f"Warning: Failed to load config from {config_path}: {e}")

    return []

# Alias for backwards compatibility
load_sources = load_sources_config
