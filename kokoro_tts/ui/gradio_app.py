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
        voices_path: str = "voices-v1.0.bin",
        use_gpu: bool = False
    ):
        """Initialize UI with model paths.

        Args:
            model_path: Path to Kokoro ONNX model
            voices_path: Path to voices binary file
            use_gpu: Enable GPU acceleration if available
        """
        self.model_path = model_path
        self.voices_path = voices_path
        self.use_gpu = use_gpu
        self.engine: Optional[KokoroEngine] = None
        self.voices_list: List[str] = []

    def initialize_engine(self) -> str:
        """Initialize the TTS engine and load voices.

        Returns:
            Status message
        """
        try:
            if self.engine is None:
                self.engine = KokoroEngine(
                    self.model_path,
                    self.voices_path,
                    use_gpu=self.use_gpu
                )
                self.engine.load_model()
                self.voices_list = sorted(self.engine.get_voices())

                gpu_status = " (GPU enabled)" if self.use_gpu else ""
                return f"✓ Engine loaded successfully with {len(self.voices_list)} voices{gpu_status}"
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

    def preview_audiobook_chapters(
        self,
        file,
        progress=gr.Progress()
    ) -> Tuple[dict, str, str]:
        """Preview chapters from uploaded book.

        Args:
            file: Uploaded EPUB or PDF file
            progress: Gradio progress tracker

        Returns:
            Tuple of (chapters dict, title, author)
        """
        if file is None:
            return {}, "", ""

        try:
            progress(0, desc="Loading book...")

            # Import required modules
            from kokoro_tts.audiobook import extract_epub_metadata, extract_pdf_metadata
            from kokoro_tts.core import extract_chapters_from_epub, PdfParser

            input_path = file.name

            # Extract metadata and chapters based on file type
            if input_path.endswith('.epub'):
                progress(0.3, desc="Extracting EPUB metadata...")
                metadata = extract_epub_metadata(input_path)

                progress(0.6, desc="Extracting chapters...")
                chapters_data = extract_chapters_from_epub(
                    input_path,
                    debug=False,
                    skip_confirmation=True,
                    skip_front_matter=False  # Show all chapters for preview
                )
            elif input_path.endswith('.pdf'):
                progress(0.3, desc="Extracting PDF metadata...")
                metadata = extract_pdf_metadata(input_path)

                progress(0.6, desc="Extracting chapters...")
                parser = PdfParser(input_path, debug=False, skip_confirmation=True)
                chapters_data = parser.get_chapters()
            else:
                return {"error": "Unsupported file type"}, "", ""

            # Format chapters for display
            progress(0.9, desc="Formatting chapters...")
            chapters_dict = {
                f"Chapter {i+1}": ch['title'][:80]  # Truncate long titles
                for i, ch in enumerate(chapters_data)
            }

            progress(1.0, desc="Complete!")

            return (
                chapters_dict,
                metadata.get('title', ''),
                metadata.get('author', '')
            )

        except Exception as e:
            return {"error": str(e)}, "", ""

    def generate_audiobook(
        self,
        file,
        voice: str,
        speed: float,
        language: str,
        title: str,
        author: str,
        narrator: str,
        year: str,
        genre: str,
        description: str,
        cover_file,
        select_chapters: str,
        skip_front_matter: bool,
        add_intro: bool,
        intro_text: str,
        keep_temp: bool,
        no_chapters: bool,
        progress=gr.Progress()
    ) -> Tuple[Optional[str], str, str]:
        """Generate audiobook from uploaded file.

        Args:
            file: Uploaded EPUB or PDF
            voice: Voice selection
            speed: Speech speed
            language: Language code
            title: Book title override
            author: Author override
            narrator: Narrator name
            year: Publication year
            genre: Book genre
            description: Book description
            cover_file: Custom cover image
            select_chapters: Chapter selection string
            skip_front_matter: Skip front matter chapters
            add_intro: Add introduction chapter
            intro_text: Custom intro text
            keep_temp: Keep temporary files
            no_chapters: Skip chapter markers
            progress: Gradio progress tracker

        Returns:
            Tuple of (output file path, info text, progress log)
        """
        if file is None:
            return None, "", "⚠ Please upload a file"

        if not voice:
            return None, "", "⚠ Please select a voice"

        temp_merged = None
        temp_dir_created = None

        try:
            # Initialize engine if needed
            if self.engine is None:
                status = self.initialize_engine()
                if "Error" in status:
                    return None, "", status

            progress(0.05, desc="[1/7] Initializing...")

            # Import required modules
            from kokoro_tts.audiobook import AudiobookCreator, calculate_chapter_timings, embed_audiobook_metadata
            from kokoro_tts.core import AudiobookOptions, Chapter
            from kokoro_tts.core import extract_chapters_from_epub, PdfParser, generate_audiobook_intro
            import shutil

            input_path = file.name

            # Create output file with original filename
            # Extract base name without extension
            import os
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            output_filename = f"{base_name}.m4a"

            output_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix='.m4a',
                prefix=f"{base_name}_"
            )
            output_path = output_file.name
            output_file.close()

            # Create audiobook options
            audiobook_opts = AudiobookOptions(
                select_chapters=select_chapters or "all",
                keep_temp=keep_temp,
                no_metadata=False,  # Always embed metadata in UI
                no_chapters=no_chapters,
                skip_front_matter=skip_front_matter,
                intro_text=intro_text if intro_text else None,
                no_intro=not add_intro,
                cover_path=cover_file.name if cover_file else None,
                title=title if title else None,
                author=author if author else None,
                narrator=narrator if narrator else None,
                year=year if year else None,
                genre=genre if genre else None,
                description=description if description else None
            )

            # Progress tracking
            progress_log = []

            def log_progress(msg: str):
                progress_log.append(msg)

            def format_progress_log():
                """Format progress log with clear header and structure."""
                if not progress_log:
                    return "Starting audiobook creation..."
                return "PROGRESS LOG:\n" + "=" * 50 + "\n" + "\n".join(progress_log)

            # Initial yield - show we're starting
            # Output format: (file_download, info_panel, progress_log)
            yield None, "", format_progress_log()

            # Use AudiobookCreator context manager
            with AudiobookCreator(input_path, audiobook_opts) as creator:
                temp_dir_created = creator.temp_dir

                # Step 1: Extract metadata
                progress(0.1, desc="[1/7] Extracting metadata...")
                metadata = creator.extract_metadata()

                log_progress("✓ [1/7] Metadata extracted")
                if metadata.get('title'):
                    log_progress(f"  - Title: \"{metadata['title']}\"")
                if metadata.get('author'):
                    log_progress(f"  - Author: \"{metadata['author']}\"")
                if metadata.get('cover'):
                    log_progress(f"  - Cover: Found ({len(metadata['cover'])} bytes)")

                yield None, "", format_progress_log()

                # Step 2: Extract and select chapters
                progress(0.15, desc="[2/7] Extracting chapters...")

                if input_path.endswith('.epub'):
                    all_chapters = extract_chapters_from_epub(
                        input_path,
                        debug=False,
                        skip_confirmation=True,
                        skip_front_matter=audiobook_opts.skip_front_matter
                    )
                else:  # PDF
                    parser = PdfParser(input_path, debug=False, skip_confirmation=True)
                    all_chapters = parser.get_chapters()

                if not all_chapters:
                    return None, "", "✗ Error: No chapters found in file"

                # Convert to Chapter objects
                chapter_objects = [
                    Chapter(title=ch['title'], content=ch['content'], order=ch['order'])
                    for ch in all_chapters
                ]

                selected_chapters = creator.select_chapters_from_list(chapter_objects)

                log_progress(f"✓ [2/7] Chapters extracted")
                log_progress(f"  - Selected {len(selected_chapters)} chapters")

                # Add introduction if requested
                if not audiobook_opts.no_intro:
                    if audiobook_opts.intro_text:
                        intro_content = audiobook_opts.intro_text
                    else:
                        intro_content = generate_audiobook_intro(metadata)

                    if intro_content:
                        intro_chapter = Chapter(title="Introduction", content=intro_content, order=0)
                        selected_chapters = [intro_chapter] + selected_chapters
                        log_progress("  - Added introduction chapter")

                yield None, "", format_progress_log()

                # Step 3: Generate audio for each chapter
                progress(0.20, desc="[3/7] Generating audio...")
                log_progress(f"✓ [3/7] Generating audio ({len(selected_chapters)} chapters)")

                chapter_files = []
                chapter_titles = []

                for idx, chapter in enumerate(selected_chapters, 1):
                    log_progress(f"  - [{idx}/{len(selected_chapters)}] {chapter.title}")

                    # Generate audio for this chapter
                    chapter_file = os.path.join(temp_dir_created, f"chapter_{idx:03d}.m4a")

                    options = ProcessingOptions(
                        voice=voice,
                        speed=speed,
                        lang=language,
                        format=AudioFormat.M4A
                    )

                    samples, sr = self.engine.generate_audio(chapter.content, options)

                    if samples is not None:
                        self.engine.save_audio(samples, sr, chapter_file, AudioFormat.M4A)
                        chapter_files.append(chapter_file)
                        chapter_titles.append(chapter.title)
                    else:
                        log_progress(f"    ⚠ Warning: No audio generated for chapter {idx}")

                    # Update progress bar and yield every chapter to keep displays in sync
                    chapter_progress = 0.20 + (0.50 * idx / len(selected_chapters))
                    progress(chapter_progress, desc=f"[3/7] Processing chapter {idx}/{len(selected_chapters)}: {chapter.title[:30]}...")
                    yield None, "", format_progress_log()

                if not chapter_files:
                    yield None, "", "✗ Error: No audio generated"
                    return

                # Step 4: Merge chapters
                progress(0.72, desc="[4/7] Merging chapters...")
                log_progress(f"✓ [4/7] Merging {len(chapter_files)} chapters")

                temp_merged = os.path.join(temp_dir_created, "_temp_merged.m4a")

                import subprocess
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                    filelist_path = f.name

                    # Create concat list
                    for chapter_file in chapter_files:
                        if os.path.exists(chapter_file):
                            abs_path = os.path.abspath(chapter_file)
                            escaped_path = abs_path.replace("'", "'\\''")
                            f.write(f"file '{escaped_path}'\n")

                try:
                    ffmpeg_cmd = [
                        'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                        '-i', filelist_path,
                        '-c:a', 'aac', '-b:a', '128k',
                        temp_merged
                    ]

                    result = subprocess.run(
                        ffmpeg_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )

                    if result.returncode != 0:
                        raise Exception(f"FFmpeg failed: {result.stderr}")

                finally:
                    if os.path.exists(filelist_path):
                        os.unlink(filelist_path)

                yield None, "", format_progress_log()

                # Step 5: Embed metadata
                if not no_chapters:
                    progress(0.85, desc="[5/7] Embedding metadata...")
                    log_progress("✓ [5/7] Embedding metadata and chapter markers")

                    # Calculate chapter timings
                    chapters_info = calculate_chapter_timings(
                        chapter_files,
                        chapter_titles
                    )

                    # Add narrator if not specified
                    if not metadata.get('narrator') and voice:
                        metadata['narrator'] = voice

                    # Embed metadata
                    try:
                        embed_audiobook_metadata(
                            temp_merged,
                            output_path,
                            metadata,
                            metadata.get('cover'),
                            chapters_info
                        )
                        log_progress(f"  - {len(chapters_info)} chapter markers added")
                        log_progress(f"  - Cover art embedded" if metadata.get('cover') else "  - No cover art")
                    except Exception as e:
                        log_progress(f"  ⚠ Warning: Could not embed metadata: {e}")
                        log_progress(f"  - Copying file without metadata")
                        shutil.copy(temp_merged, output_path)
                else:
                    progress(0.85, desc="[5/7] Skipping metadata...")
                    log_progress("✓ [5/7] Skipping metadata embedding (as requested)")
                    shutil.copy(temp_merged, output_path)

                yield None, "", format_progress_log()

            # Step 6: Calculate file info
            progress(0.95, desc="[6/7] Finalizing...")
            log_progress("✓ [6/7] Calculating file information")

            from pydub import AudioSegment
            file_size = os.path.getsize(output_path) / (1024 * 1024)
            audio = AudioSegment.from_file(output_path, format='mp4')
            duration_sec = len(audio) / 1000.0
            hours = int(duration_sec // 3600)
            minutes = int((duration_sec % 3600) // 60)
            seconds = int(duration_sec % 60)

            yield None, "", format_progress_log()

            # Step 7: Create final file with proper name
            progress(1.0, desc="[7/7] Complete!")
            log_progress("✓ [7/7] Audiobook creation complete!")
            log_progress(f"\nDuration: {hours}h {minutes}m {seconds}s")
            log_progress(f"Size: {file_size:.1f} MB")

            # Create a copy with the proper filename for download
            final_output_dir = tempfile.gettempdir()
            final_output_path = os.path.join(final_output_dir, output_filename)

            # Copy to final location with proper name
            shutil.copy(output_path, final_output_path)

            # Clean up the temp file with random name
            try:
                os.unlink(output_path)
            except:
                pass

            # Final info text for Audiobook Info panel
            info_text = f"""✓ Audiobook created successfully!

Duration: {hours}h {minutes}m {seconds}s
Size: {file_size:.1f} MB
Format: M4A with AAC codec
Chapters: {len(chapter_files)} included
Voice: {voice}
Speed: {speed}x
"""

            # Final yield with completed results
            yield final_output_path, info_text, format_progress_log()

        except Exception as e:
            error_msg = f"✗ Error: {str(e)}"
            progress_log.append(error_msg)
            yield None, "", format_progress_log()

        finally:
            # Clean up temporary files
            if temp_merged and os.path.exists(temp_merged):
                try:
                    os.unlink(temp_merged)
                except:
                    pass

            # AudiobookCreator context manager will handle its own cleanup
            # unless keep_temp is True


def create_ui(
    model_path: str = "kokoro-v1.0.onnx",
    voices_path: str = "voices-v1.0.bin",
    share: bool = False,
    use_gpu: bool = False
) -> gr.Blocks:
    """Create the Gradio UI interface.

    Args:
        model_path: Path to Kokoro model
        voices_path: Path to voices file
        share: Whether to create a public share link
        use_gpu: Enable GPU acceleration if available

    Returns:
        Gradio Blocks interface
    """
    ui = KokoroUI(model_path, voices_path, use_gpu=use_gpu)

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

            # ===== TAB 4: Audiobook Creator =====
            with gr.Tab("Audiobook Creator"):
                gr.Markdown("""
                ### Create Professional Audiobooks
                Convert EPUB or PDF books into M4A audiobooks with metadata and chapter markers.
                Uses disk-based processing to handle large files efficiently.
                """)

                # File upload
                with gr.Row():
                    audiobook_file = gr.File(
                        label="📚 Upload Book (EPUB/PDF)",
                        file_types=[".epub", ".pdf"]
                    )

                # Basic settings
                with gr.Accordion("⚙️ Basic Settings", open=True):
                    with gr.Row():
                        ab_voice = gr.Dropdown(
                            label="Voice",
                            choices=[],
                            value=None,
                            interactive=True
                        )
                        ab_speed = gr.Slider(
                            minimum=0.5,
                            maximum=2.0,
                            value=1.0,
                            step=0.1,
                            label="Speed"
                        )
                        ab_lang = gr.Dropdown(
                            label="Language",
                            choices=SUPPORTED_LANGUAGES,
                            value="en-us"
                        )

                # Metadata (auto-filled but editable)
                with gr.Accordion("📝 Metadata (auto-detected from file)", open=False):
                    ab_title = gr.Textbox(
                        label="Title",
                        placeholder="Auto-detected from file"
                    )
                    ab_author = gr.Textbox(
                        label="Author",
                        placeholder="Auto-detected from file"
                    )
                    ab_narrator = gr.Textbox(
                        label="Narrator",
                        placeholder="Defaults to voice name"
                    )
                    with gr.Row():
                        ab_year = gr.Textbox(
                            label="Year",
                            placeholder="e.g., 2024"
                        )
                        ab_genre = gr.Textbox(
                            label="Genre",
                            placeholder="e.g., Fiction"
                        )
                    ab_description = gr.Textbox(
                        label="Description",
                        lines=3,
                        placeholder="Auto-detected or leave empty"
                    )
                    ab_cover = gr.File(
                        label="Cover Image (optional override)",
                        file_types=[".jpg", ".jpeg", ".png"]
                    )

                # Chapter selection
                with gr.Accordion("📖 Chapter Selection", open=False):
                    ab_preview_btn = gr.Button("Preview Chapters from File", variant="secondary")
                    ab_chapters_display = gr.JSON(
                        label="Available Chapters",
                        visible=False
                    )
                    ab_select_chapters = gr.Textbox(
                        label="Select Chapters",
                        value="all",
                        placeholder="Examples: all, 1-5, 1,3,5,7-10"
                    )

                # Advanced options
                with gr.Accordion("🔧 Advanced Options", open=False):
                    ab_skip_front = gr.Checkbox(
                        label="Skip front matter (copyright, TOC, etc.)",
                        value=True
                    )
                    ab_add_intro = gr.Checkbox(
                        label="Add introduction chapter",
                        value=True
                    )
                    ab_intro_text = gr.Textbox(
                        label="Custom intro text (optional)",
                        lines=2,
                        placeholder="Leave empty for auto-generated intro"
                    )
                    with gr.Row():
                        ab_keep_temp = gr.Checkbox(
                            label="Keep temporary files",
                            value=False
                        )
                        ab_no_chapters = gr.Checkbox(
                            label="Skip chapter markers",
                            value=False
                        )

                # Generate button
                ab_generate_btn = gr.Button(
                    "🎧 Create Audiobook",
                    variant="primary",
                    size="lg"
                )

                # Output
                with gr.Row():
                    with gr.Column(scale=2):
                        ab_progress = gr.Textbox(
                            label="Progress Log",
                            lines=10,
                            interactive=False,
                            max_lines=20
                        )
                    with gr.Column(scale=1):
                        ab_info = gr.Textbox(
                            label="Audiobook Info",
                            lines=10,
                            interactive=False
                        )

                ab_output = gr.File(label="📥 Download Audiobook (M4A)")

                # Wire up events
                ab_preview_btn.click(
                    fn=ui.preview_audiobook_chapters,
                    inputs=[audiobook_file],
                    outputs=[ab_chapters_display, ab_title, ab_author]
                ).then(
                    lambda: gr.update(visible=True),
                    outputs=[ab_chapters_display]
                )

                ab_generate_btn.click(
                    fn=ui.generate_audiobook,
                    inputs=[
                        audiobook_file, ab_voice, ab_speed, ab_lang,
                        ab_title, ab_author, ab_narrator,
                        ab_year, ab_genre, ab_description, ab_cover,
                        ab_select_chapters, ab_skip_front, ab_add_intro,
                        ab_intro_text, ab_keep_temp, ab_no_chapters
                    ],
                    outputs=[ab_output, ab_info, ab_progress]
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
                gr.update(choices=voices, value=default_voice),  # ab_voice
            )

        demo.load(
            fn=load_voices,
            outputs=[
                status_box,
                simple_voice,
                file_voice,
                preview_voice,
                blend_voice1,
                blend_voice2,
                ab_voice
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
    share: bool = False,
    use_gpu: bool = False
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
        use_gpu: Enable GPU acceleration if available
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
        parser.add_argument("--gpu", action="store_true", help="Enable GPU acceleration")
        args = parser.parse_args()

        model_path = args.model
        voices_path = args.voices
        server_name = args.server_name
        server_port = args.server_port
        share = args.share
        use_gpu = args.gpu

    demo = create_ui(model_path, voices_path, share, use_gpu)
    demo.launch(
        server_name=server_name,
        server_port=server_port,
        share=share,
        show_error=True
    )


if __name__ == "__main__":
    launch_ui()
