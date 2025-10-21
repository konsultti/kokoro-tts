"""Gradio web interface for Kokoro TTS.

This module provides a user-friendly web UI for text-to-speech conversion
with support for voice blending, file uploads, and real-time audio playback.
"""

import os
import tempfile
from typing import Optional, Tuple, List
import numpy as np

try:
    import gradio as gr
except ImportError:
    raise ImportError(
        "Gradio is required for the web UI. Install with: pip install 'kokoro-tts[ui]'"
    )

from kokoro_tts.core import (
    KokoroEngine,
    ProcessingOptions,
    AudioFormat,
    SUPPORTED_LANGUAGES
)


class KokoroUI:
    """Gradio UI wrapper for Kokoro TTS engine."""

    def __init__(
        self,
        model_path: str = "kokoro-v1.0.onnx",
        voices_path: str = "voices-v1.0.bin"
    ):
        """Initialize UI with model paths.

        Args:
            model_path: Path to Kokoro ONNX model
            voices_path: Path to voices binary file
        """
        self.model_path = model_path
        self.voices_path = voices_path
        self.engine: Optional[KokoroEngine] = None
        self.voices_list: List[str] = []

    def initialize_engine(self) -> str:
        """Initialize the TTS engine and load voices.

        Returns:
            Status message
        """
        try:
            if self.engine is None:
                self.engine = KokoroEngine(self.model_path, self.voices_path)
                self.engine.load_model()
                self.voices_list = sorted(self.engine.get_voices())
            return f"✓ Engine loaded successfully with {len(self.voices_list)} voices"
        except Exception as e:
            return f"✗ Error loading engine: {str(e)}"

    def generate_simple(
        self,
        text: str,
        voice: str,
        speed: float,
        language: str,
        progress=gr.Progress()
    ) -> Tuple[Optional[Tuple[int, np.ndarray]], str]:
        """Generate audio from text (Simple tab).

        Args:
            text: Input text
            voice: Selected voice
            speed: Speech speed
            language: Language code
            progress: Gradio progress tracker

        Returns:
            Tuple of (audio data, status message)
        """
        if not text.strip():
            return None, "⚠ Please enter some text"

        try:
            # Initialize if needed
            if self.engine is None:
                status = self.initialize_engine()
                if "Error" in status:
                    return None, status

            # Create processing options
            options = ProcessingOptions(
                voice=voice,
                speed=speed,
                lang=language,
                format=AudioFormat.WAV
            )

            # Progress callback
            def update_progress(msg: str, current: int, total: int):
                progress((current, total), desc=msg)

            self.engine.progress_callback = update_progress

            # Generate audio
            progress(0, desc="Generating audio...")
            samples, sample_rate = self.engine.generate_audio(text, options)

            if samples is not None:
                # Gradio expects (sample_rate, samples) tuple
                return (sample_rate, samples), f"✓ Generated {len(samples)/sample_rate:.1f}s of audio"
            else:
                return None, "✗ Audio generation failed"

        except Exception as e:
            return None, f"✗ Error: {str(e)}"

    def generate_from_file(
        self,
        file,
        voice: str,
        speed: float,
        language: str,
        output_format: str,
        progress=gr.Progress()
    ) -> Tuple[Optional[str], str]:
        """Generate audio from uploaded file.

        Args:
            file: Uploaded file object
            voice: Selected voice
            speed: Speech speed
            language: Language code
            output_format: Output audio format
            progress: Gradio progress tracker

        Returns:
            Tuple of (output file path, status message)
        """
        if file is None:
            return None, "⚠ Please upload a file"

        try:
            # Initialize if needed
            if self.engine is None:
                status = self.initialize_engine()
                if "Error" in status:
                    return None, status

            # Get input file path
            input_path = file.name

            # Create output file
            file_ext = output_format.lower()
            output_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=f'.{file_ext}'
            )
            output_path = output_file.name
            output_file.close()

            # Create processing options
            options = ProcessingOptions(
                voice=voice,
                speed=speed,
                lang=language,
                format=AudioFormat(file_ext)
            )

            # Progress callback
            def update_progress(msg: str, current: int, total: int):
                progress((current, total), desc=msg)

            # Process file
            progress(0, desc="Processing file...")
            success = self.engine.process_file(
                input_path,
                output_path,
                options,
                progress_callback=update_progress
            )

            if success:
                return output_path, f"✓ File processed successfully"
            else:
                return None, "✗ File processing failed"

        except Exception as e:
            return None, f"✗ Error: {str(e)}"

    def preview_voice(
        self,
        voice: str,
        speed: float,
        language: str,
        progress=gr.Progress()
    ) -> Tuple[Optional[Tuple[int, np.ndarray]], str]:
        """Generate a preview with the selected voice.

        Args:
            voice: Voice to preview
            speed: Speech speed
            language: Language code
            progress: Gradio progress tracker

        Returns:
            Tuple of (audio data, status message)
        """
        preview_texts = {
            'en-us': "Hello! This is a preview of my voice. How do I sound?",
            'en-gb': "Hello! This is a preview of my voice. How do I sound?",
            'ja': "こんにちは！これは私の声のプレビューです。",
            'zh': "你好！这是我的声音预览。",
            'ko': "안녕하세요! 이것은 제 목소리 미리보기입니다.",
            'es': "¡Hola! Esta es una vista previa de mi voz.",
            'fr': "Bonjour! Ceci est un aperçu de ma voix.",
            'hi': "नमस्ते! यह मेरी आवाज़ का पूर्वावलोकन है।",
            'it': "Ciao! Questa è un'anteprima della mia voce.",
            'pt-br': "Olá! Esta é uma prévia da minha voz."
        }

        preview_text = preview_texts.get(language, preview_texts['en-us'])

        return self.generate_simple(preview_text, voice, speed, language, progress)

    def blend_voices(
        self,
        voice1: str,
        voice2: str,
        weight1: int,
        speed: float,
        language: str,
        progress=gr.Progress()
    ) -> Tuple[Optional[Tuple[int, np.ndarray]], str]:
        """Generate audio with blended voices.

        Args:
            voice1: First voice
            voice2: Second voice
            weight1: Weight for first voice (0-100)
            speed: Speech speed
            language: Language code
            progress: Gradio progress tracker

        Returns:
            Tuple of (audio data, status message)
        """
        weight2 = 100 - weight1
        blended_voice = f"{voice1}:{weight1},{voice2}:{weight2}"

        preview_text = f"This is a blend of {weight1}% {voice1} and {weight2}% {voice2}."

        return self.generate_simple(preview_text, blended_voice, speed, language, progress)


def create_ui(
    model_path: str = "kokoro-v1.0.onnx",
    voices_path: str = "voices-v1.0.bin",
    share: bool = False
) -> gr.Blocks:
    """Create the Gradio UI interface.

    Args:
        model_path: Path to Kokoro model
        voices_path: Path to voices file
        share: Whether to create a public share link

    Returns:
        Gradio Blocks interface
    """
    ui = KokoroUI(model_path, voices_path)

    # Custom CSS for better styling
    custom_css = """
    .gradio-container {
        max-width: 1200px !important;
    }
    .tab-nav button {
        font-size: 16px !important;
    }
    """

    with gr.Blocks(
        title="Kokoro TTS",
        theme=gr.themes.Soft(),
        css=custom_css
    ) as demo:
        gr.Markdown(
            """
            # 🎙️ Kokoro TTS - Text to Speech

            Convert text to natural-sounding speech with multiple voices and languages.
            Supports voice blending, EPUB/PDF processing, and more!
            """
        )

        # Status display
        status_box = gr.Textbox(
            label="Status",
            value="Ready. Engine will initialize on first use.",
            interactive=False
        )

        with gr.Tabs():
            # ===== TAB 1: Quick Generate =====
            with gr.Tab("Quick Generate"):
                gr.Markdown("### Generate speech from text")

                with gr.Row():
                    with gr.Column(scale=2):
                        simple_text = gr.Textbox(
                            label="Text to speak",
                            placeholder="Enter your text here...",
                            lines=8
                        )

                    with gr.Column(scale=1):
                        simple_voice = gr.Dropdown(
                            label="Voice",
                            choices=[],  # Will be populated on load
                            value=None,
                            interactive=True
                        )
                        simple_speed = gr.Slider(
                            minimum=0.5,
                            maximum=2.0,
                            value=1.0,
                            step=0.1,
                            label="Speed"
                        )
                        simple_lang = gr.Dropdown(
                            label="Language",
                            choices=SUPPORTED_LANGUAGES,
                            value="en-us"
                        )

                simple_generate_btn = gr.Button("🎤 Generate Speech", variant="primary", size="lg")

                simple_audio = gr.Audio(label="Generated Audio", type="numpy")
                simple_status = gr.Textbox(label="Result", interactive=False)

                simple_generate_btn.click(
                    fn=ui.generate_simple,
                    inputs=[simple_text, simple_voice, simple_speed, simple_lang],
                    outputs=[simple_audio, simple_status]
                )

            # ===== TAB 2: File Processing =====
            with gr.Tab("File Processing"):
                gr.Markdown("### Convert documents to audiobooks")
                gr.Markdown("Supports `.txt`, `.epub`, and `.pdf` files")

                with gr.Row():
                    with gr.Column(scale=2):
                        file_input = gr.File(
                            label="Upload File",
                            file_types=[".txt", ".epub", ".pdf"]
                        )

                    with gr.Column(scale=1):
                        file_voice = gr.Dropdown(
                            label="Voice",
                            choices=[],
                            value=None,
                            interactive=True
                        )
                        file_speed = gr.Slider(
                            minimum=0.5,
                            maximum=2.0,
                            value=1.0,
                            step=0.1,
                            label="Speed"
                        )
                        file_lang = gr.Dropdown(
                            label="Language",
                            choices=SUPPORTED_LANGUAGES,
                            value="en-us"
                        )
                        file_format = gr.Radio(
                            label="Output Format",
                            choices=["wav", "mp3", "m4a"],
                            value="wav"
                        )

                file_generate_btn = gr.Button("📖 Process File", variant="primary", size="lg")

                file_output = gr.File(label="Download Audio")
                file_status = gr.Textbox(label="Result", interactive=False)

                file_generate_btn.click(
                    fn=ui.generate_from_file,
                    inputs=[file_input, file_voice, file_speed, file_lang, file_format],
                    outputs=[file_output, file_status]
                )

            # ===== TAB 3: Voice Lab =====
            with gr.Tab("Voice Lab"):
                gr.Markdown("### Experiment with voices")

                with gr.Tabs():
                    # Voice Preview
                    with gr.Tab("Voice Preview"):
                        gr.Markdown("Preview individual voices")

                        with gr.Row():
                            with gr.Column():
                                preview_voice = gr.Dropdown(
                                    label="Select Voice",
                                    choices=[],
                                    value=None,
                                    interactive=True
                                )
                                preview_speed = gr.Slider(
                                    minimum=0.5,
                                    maximum=2.0,
                                    value=1.0,
                                    step=0.1,
                                    label="Speed"
                                )
                                preview_lang = gr.Dropdown(
                                    label="Language",
                                    choices=SUPPORTED_LANGUAGES,
                                    value="en-us"
                                )

                        preview_btn = gr.Button("🎧 Preview Voice", variant="primary")
                        preview_audio = gr.Audio(label="Voice Preview", type="numpy")
                        preview_status = gr.Textbox(label="Result", interactive=False)

                        preview_btn.click(
                            fn=ui.preview_voice,
                            inputs=[preview_voice, preview_speed, preview_lang],
                            outputs=[preview_audio, preview_status]
                        )

                    # Voice Blending
                    with gr.Tab("Voice Blending"):
                        gr.Markdown("Blend two voices together")

                        with gr.Row():
                            with gr.Column():
                                blend_voice1 = gr.Dropdown(
                                    label="Voice 1",
                                    choices=[],
                                    value=None,
                                    interactive=True
                                )
                                blend_voice2 = gr.Dropdown(
                                    label="Voice 2",
                                    choices=[],
                                    value=None,
                                    interactive=True
                                )
                                blend_weight = gr.Slider(
                                    minimum=0,
                                    maximum=100,
                                    value=50,
                                    step=5,
                                    label="Voice 1 Weight (%)",
                                    info="Voice 2 will be (100 - this value)%"
                                )
                                blend_speed = gr.Slider(
                                    minimum=0.5,
                                    maximum=2.0,
                                    value=1.0,
                                    step=0.1,
                                    label="Speed"
                                )
                                blend_lang = gr.Dropdown(
                                    label="Language",
                                    choices=SUPPORTED_LANGUAGES,
                                    value="en-us"
                                )

                        blend_btn = gr.Button("🎭 Blend Voices", variant="primary")
                        blend_audio = gr.Audio(label="Blended Audio", type="numpy")
                        blend_status = gr.Textbox(label="Result", interactive=False)

                        blend_btn.click(
                            fn=ui.blend_voices,
                            inputs=[blend_voice1, blend_voice2, blend_weight, blend_speed, blend_lang],
                            outputs=[blend_audio, blend_status]
                        )

        # Load voices on startup
        def load_voices():
            status = ui.initialize_engine()
            voices = ui.voices_list if ui.voices_list else []
            default_voice = voices[0] if voices else None

            return (
                status,
                gr.update(choices=voices, value=default_voice),  # simple_voice
                gr.update(choices=voices, value=default_voice),  # file_voice
                gr.update(choices=voices, value=default_voice),  # preview_voice
                gr.update(choices=voices, value=default_voice),  # blend_voice1
                gr.update(choices=voices, value=default_voice if len(voices) < 2 else voices[1]),  # blend_voice2
            )

        demo.load(
            fn=load_voices,
            outputs=[
                status_box,
                simple_voice,
                file_voice,
                preview_voice,
                blend_voice1,
                blend_voice2
            ]
        )

        gr.Markdown(
            """
            ---
            ### About

            **Kokoro TTS** - Ultra-realistic multilingual text-to-speech

            - 🌍 10+ languages supported
            - 🎭 Voice blending capabilities
            - 📚 EPUB & PDF support
            - ⚡ Fast generation with ONNX

            [GitHub](https://github.com/nazdridoy/kokoro-tts) |
            [Documentation](https://github.com/nazdridoy/kokoro-tts#readme)
            """
        )

    return demo


def launch_ui(
    model_path: str = "kokoro-v1.0.onnx",
    voices_path: str = "voices-v1.0.bin",
    server_name: str = "127.0.0.1",
    server_port: int = 7860,
    share: bool = False
):
    """Launch the Gradio web UI.

    This function can be called directly or used as a console entry point.
    When used as a console entry point (kokoro-tts-ui), it parses command-line
    arguments automatically.

    Args:
        model_path: Path to Kokoro model file
        voices_path: Path to voices file
        server_name: Server hostname
        server_port: Server port
        share: Create public share link
    """
    # If called as entry point, parse args
    import sys
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser(description="Launch Kokoro TTS Web UI")
        parser.add_argument("--model", default=model_path, help="Path to model file")
        parser.add_argument("--voices", default=voices_path, help="Path to voices file")
        parser.add_argument("--server-name", default=server_name, help="Server hostname")
        parser.add_argument("--server-port", type=int, default=server_port, help="Server port")
        parser.add_argument("--share", action="store_true", help="Create public share link")
        args = parser.parse_args()

        model_path = args.model
        voices_path = args.voices
        server_name = args.server_name
        server_port = args.server_port
        share = args.share

    demo = create_ui(model_path, voices_path, share)
    demo.launch(
        server_name=server_name,
        server_port=server_port,
        share=share,
        show_error=True
    )


if __name__ == "__main__":
    launch_ui()
