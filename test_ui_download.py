#!/usr/bin/env python3
"""
Test script for UI download functionality.

Launch the UI and manually test the download feature in the Job Status Dashboard.
"""

import os
import sys

# Add project to path
sys.path.insert(0, os.path.dirname(__file__))

# Load .env file if it exists
def load_env_file(env_path=".env"):
    """Load environment variables from .env file."""
    if not os.path.exists(env_path):
        return

    print(f"Loading environment from {env_path}")
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            # Parse KEY=VALUE
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                if value:  # Only set if value is not empty
                    os.environ[key] = value
                    print(f"  Set {key}={value}")

load_env_file()

from kokoro_tts.ui.gradio_app import launch_ui

if __name__ == "__main__":
    print("=" * 60)
    print("Kokoro TTS UI - Download Feature Test")
    print("=" * 60)
    print()
    print("Testing the download functionality:")
    print("1. Navigate to the 'Audiobook Generation' tab")
    print("2. Submit a job (or use an existing completed job)")
    print("3. Go to 'Job Status' tab")
    print("4. Select a completed job")
    print("5. Click the '📥 Download' button")
    print("6. Verify the file downloads successfully")
    print()
    print("Starting UI on http://127.0.0.1:7860")
    print("=" * 60)
    print()

    # Launch UI
    launch_ui(
        model_path="kokoro-v1.0.onnx",
        voices_path="voices-v1.0.bin",
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        use_gpu=False
    )
