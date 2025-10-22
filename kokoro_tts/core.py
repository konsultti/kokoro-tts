"""Core business logic for Kokoro TTS.

This module contains the main TTS engine and audio processing functionality,
separated from CLI-specific code to enable reuse in web UI and other interfaces.
"""

# Standard library imports
import os
import sys
import tempfile
import asyncio
from typing import Optional, Callable, List, Dict, Any, Tuple, AsyncIterator
from dataclasses import dataclass
from enum import Enum

# Third-party imports
import numpy as np
from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup
import soundfile as sf
from kokoro_onnx import Kokoro
import pymupdf4llm
import fitz

# Supported languages (hardcoded as kokoro-onnx 0.4.9+ doesn't expose get_languages())
SUPPORTED_LANGUAGES = [
    'en-us',   # American English
    'en-gb',   # British English
    'ja',      # Japanese
    'zh',      # Mandarin Chinese
    'ko',      # Korean
    'es',      # Spanish
    'fr',      # French
    'hi',      # Hindi
    'it',      # Italian
    'pt-br',   # Brazilian Portuguese
]


class AudioFormat(Enum):
    """Supported audio output formats."""
    WAV = "wav"
    MP3 = "mp3"
    M4A = "m4a"


@dataclass
class Chapter:
    """Represents a chapter or section of text to be converted to speech."""
    title: str
    content: str
    order: int


@dataclass
class ProcessingOptions:
    """Options for text-to-speech processing."""
    voice: Optional[str] = None
    speed: float = 1.0
    lang: str = "en-us"
    format: AudioFormat = AudioFormat.WAV
    debug: bool = False


@dataclass
class AudiobookOptions:
    """Options for audiobook creation."""
    select_chapters: str = "all"
    keep_temp: bool = False
    temp_dir: Optional[str] = None
    no_metadata: bool = False
    no_chapters: bool = False
    cover_path: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    narrator: Optional[str] = None
    year: Optional[str] = None
    genre: Optional[str] = None
    description: Optional[str] = None
    skip_front_matter: bool = True
    intro_text: Optional[str] = None
    no_intro: bool = False
    chapter_pause_seconds: float = 0.0


class KokoroEngine:
    """Main TTS engine for Kokoro text-to-speech conversion.

    This class provides high-level methods for converting text to speech,
    handling both simple text and complex documents (EPUB, PDF) with progress callbacks.
    """

    def __init__(
        self,
        model_path: str = "kokoro-v1.0.onnx",
        voices_path: str = "voices-v1.0.bin",
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        use_gpu: bool = False,
        provider: Optional[str] = None
    ):
        """Initialize the Kokoro TTS engine.

        Args:
            model_path: Path to the Kokoro ONNX model file
            voices_path: Path to the voices binary file
            progress_callback: Optional callback for progress updates (message, current, total)
            use_gpu: If True, automatically select the best available GPU provider
            provider: Explicit provider name (e.g., 'CUDAExecutionProvider'). Takes precedence over use_gpu.

        Raises:
            FileNotFoundError: If model or voices files don't exist
            Exception: If model fails to load
        """
        self.model_path = model_path
        self.voices_path = voices_path
        self.progress_callback = progress_callback
        self.kokoro: Optional[Kokoro] = None
        self.use_gpu = use_gpu
        self.provider = provider

        # Check files exist
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
        if not os.path.exists(voices_path):
            raise FileNotFoundError(f"Voices file not found: {voices_path}")

    def load_model(self):
        """Load the Kokoro model.

        Sets up GPU provider if requested before loading the model.

        Raises:
            Exception: If model fails to load
        """
        if self.kokoro is None:
            # Setup GPU provider if requested
            if self.provider:
                # Explicit provider specified
                os.environ['ONNX_PROVIDER'] = self.provider
            elif self.use_gpu:
                # Auto-select best GPU provider
                selected_provider = self._select_gpu_provider()
                if selected_provider:
                    os.environ['ONNX_PROVIDER'] = selected_provider
                else:
                    raise RuntimeError("GPU requested but no compatible GPU provider found")

            self.kokoro = Kokoro(self.model_path, self.voices_path)

    def _select_gpu_provider(self) -> Optional[str]:
        """Select the best available GPU provider.

        Returns:
            Provider name or None if no GPU available
        """
        try:
            import onnxruntime as ort
            available_providers = ort.get_available_providers()

            # Priority: CUDA > TensorRT > ROCm > CoreML
            # CUDA is prioritized as it's more commonly available than TensorRT
            # (TensorRT requires additional libraries beyond CUDA)
            if 'CUDAExecutionProvider' in available_providers:
                return 'CUDAExecutionProvider'
            elif 'TensorrtExecutionProvider' in available_providers:
                return 'TensorrtExecutionProvider'
            elif 'ROCMExecutionProvider' in available_providers:
                return 'ROCMExecutionProvider'
            elif 'CoreMLExecutionProvider' in available_providers:
                return 'CoreMLExecutionProvider'
        except Exception:
            pass
        return None

    def get_voices(self) -> List[str]:
        """Get list of available voices.

        Returns:
            List of voice names
        """
        if self.kokoro is None:
            self.load_model()
        return list(self.kokoro.get_voices())

    def validate_language(self, lang: str) -> str:
        """Validate if language is supported.

        Args:
            lang: Language code

        Returns:
            Validated language code

        Raises:
            ValueError: If language is not supported
        """
        if lang not in SUPPORTED_LANGUAGES:
            supported = ', '.join(sorted(SUPPORTED_LANGUAGES))
            raise ValueError(f"Unsupported language: {lang}\nSupported: {supported}")
        return lang

    def validate_voice(self, voice: str) -> str | np.ndarray:
        """Validate voice and handle voice blending.

        Args:
            voice: Voice name or blend specification (e.g., "voice1:60,voice2:40")

        Returns:
            Voice name string or blended voice style array

        Raises:
            ValueError: If voice is invalid
        """
        if self.kokoro is None:
            self.load_model()

        supported_voices = set(self.kokoro.get_voices())

        # Parse comma-separated voices for blend
        if ',' in voice:
            voices = []
            weights = []

            for pair in voice.split(','):
                if ':' in pair:
                    v, w = pair.strip().split(':')
                    voices.append(v.strip())
                    weights.append(float(w.strip()))
                else:
                    voices.append(pair.strip())
                    weights.append(50.0)

            if len(voices) != 2:
                raise ValueError("Voice blending requires exactly two voices")

            # Validate voices
            for v in voices:
                if v not in supported_voices:
                    raise ValueError(f"Unsupported voice: {v}")

            # Normalize weights
            total = sum(weights)
            if total != 100:
                weights = [w * (100/total) for w in weights]

            # Create blended style
            style1 = self.kokoro.get_voice_style(voices[0])
            style2 = self.kokoro.get_voice_style(voices[1])
            return np.add(style1 * (weights[0]/100), style2 * (weights[1]/100))

        # Single voice validation
        if voice not in supported_voices:
            raise ValueError(f"Unsupported voice: {voice}")
        return voice

    def chunk_text(self, text: str, chunk_size: int = 1000) -> List[str]:
        """Split text into chunks at sentence boundaries.

        Args:
            text: Text to chunk
            chunk_size: Target chunk size in characters

        Returns:
            List of text chunks
        """
        sentences = text.replace('\n', ' ').split('.')
        chunks = []
        current_chunk = []
        current_size = 0

        for sentence in sentences:
            if not sentence.strip():
                continue

            sentence = sentence.strip() + '.'
            sentence_size = len(sentence)

            # Split long sentences
            if sentence_size > chunk_size:
                words = sentence.split()
                current_piece = []
                current_piece_size = 0

                for word in words:
                    word_size = len(word) + 1
                    if current_piece_size + word_size > chunk_size:
                        if current_piece:
                            chunks.append(' '.join(current_piece).strip() + '.')
                        current_piece = [word]
                        current_piece_size = word_size
                    else:
                        current_piece.append(word)
                        current_piece_size += word_size

                if current_piece:
                    chunks.append(' '.join(current_piece).strip() + '.')
                continue

            # Start new chunk if needed
            if current_size + sentence_size > chunk_size and current_chunk:
                chunks.append(' '.join(current_chunk))
                current_chunk = []
                current_size = 0

            current_chunk.append(sentence)
            current_size += sentence_size

        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return chunks

    def process_chunk(
        self,
        chunk: str,
        voice: str | np.ndarray,
        speed: float,
        lang: str,
        retry_count: int = 0,
        debug: bool = False
    ) -> Tuple[Optional[List[float]], Optional[int]]:
        """Process a single text chunk with automatic subdivision on errors.

        Args:
            chunk: Text to process
            voice: Voice name or blended style
            speed: Speech speed multiplier
            lang: Language code
            retry_count: Current retry attempt
            debug: Enable debug output

        Returns:
            Tuple of (samples, sample_rate) or (None, None) on error
        """
        if self.kokoro is None:
            self.load_model()

        try:
            samples, sample_rate = self.kokoro.create(
                chunk, voice=voice, speed=speed, lang=lang
            )
            return samples, sample_rate
        except Exception as e:
            error_msg = str(e)

            # Handle phoneme length error by subdividing
            if "index 510 is out of bounds" in error_msg:
                current_size = len(chunk)
                new_size = int(current_size * 0.6)

                # Split into smaller pieces
                words = chunk.split()
                pieces = []
                current_piece = []
                current_piece_size = 0

                for word in words:
                    word_size = len(word) + 1
                    if current_piece_size + word_size > new_size:
                        if current_piece:
                            pieces.append(' '.join(current_piece).strip())
                        current_piece = [word]
                        current_piece_size = word_size
                    else:
                        current_piece.append(word)
                        current_piece_size += word_size

                if current_piece:
                    pieces.append(' '.join(current_piece).strip())

                # Process each piece recursively
                all_samples = []
                last_sample_rate = None

                for piece in pieces:
                    samples, sr = self.process_chunk(
                        piece, voice, speed, lang, retry_count + 1, debug
                    )
                    if samples is not None:
                        all_samples.extend(samples)
                        last_sample_rate = sr

                if all_samples:
                    return all_samples, last_sample_rate

            return None, None

    def generate_audio(
        self,
        text: str,
        options: ProcessingOptions
    ) -> Tuple[Optional[np.ndarray], Optional[int]]:
        """Generate audio from text.

        Args:
            text: Text to convert
            options: Processing options

        Returns:
            Tuple of (audio samples, sample rate) or (None, None) on error
        """
        if self.kokoro is None:
            self.load_model()

        # Validate and prepare
        lang = self.validate_language(options.lang)
        voice = self.validate_voice(options.voice) if options.voice else "af_sarah"

        # Chunk and process
        chunks = self.chunk_text(text)
        all_samples = []
        sample_rate = None

        for i, chunk in enumerate(chunks, 1):
            if self.progress_callback:
                self.progress_callback("Processing", i, len(chunks))

            samples, sr = self.process_chunk(
                chunk, voice, options.speed, lang, debug=options.debug
            )

            if samples is not None:
                all_samples.extend(samples)
                if sample_rate is None:
                    sample_rate = sr

        if all_samples:
            return np.array(all_samples), sample_rate
        return None, None

    def save_audio(
        self,
        samples: np.ndarray,
        sample_rate: int,
        output_path: str,
        format: AudioFormat = AudioFormat.WAV
    ):
        """Save audio samples to file.

        Args:
            samples: Audio sample data
            sample_rate: Sample rate in Hz
            output_path: Output file path
            format: Audio format
        """
        if format == AudioFormat.WAV:
            sf.write(output_path, samples, sample_rate)
        elif format in [AudioFormat.MP3, AudioFormat.M4A]:
            from pydub import AudioSegment

            # Write to temp WAV first
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp_path = tmp.name
                sf.write(tmp_path, samples, sample_rate)

            try:
                audio = AudioSegment.from_wav(tmp_path)
                if format == AudioFormat.MP3:
                    audio.export(output_path, format='mp3', bitrate='128k')
                else:  # M4A
                    audio.export(output_path, format='mp4', codec='aac', bitrate='128k')
            finally:
                os.unlink(tmp_path)

    def extract_chapters_from_epub(
        self,
        epub_path: str,
        debug: bool = False
    ) -> List[Chapter]:
        """Extract chapters from EPUB file.

        Args:
            epub_path: Path to EPUB file
            debug: Enable debug output

        Returns:
            List of Chapter objects
        """
        from kokoro_tts import extract_chapters_from_epub as legacy_extract
        chapters_data = legacy_extract(epub_path, debug)
        return [
            Chapter(
                title=ch['title'],
                content=ch['content'],
                order=ch['order']
            )
            for ch in chapters_data
        ]

    def extract_chapters_from_pdf(
        self,
        pdf_path: str,
        debug: bool = False
    ) -> List[Chapter]:
        """Extract chapters from PDF file.

        Args:
            pdf_path: Path to PDF file
            debug: Enable debug output

        Returns:
            List of Chapter objects
        """
        from kokoro_tts import PdfParser
        parser = PdfParser(pdf_path, debug=debug)
        chapters_data = parser.get_chapters()
        return [
            Chapter(
                title=ch['title'],
                content=ch['content'],
                order=ch['order']
            )
            for ch in chapters_data
        ]

    def process_file(
        self,
        input_path: str,
        output_path: str,
        options: ProcessingOptions,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> bool:
        """Process an entire file (text, EPUB, or PDF) to audio.

        Args:
            input_path: Path to input file
            output_path: Path to output audio file
            options: Processing options
            progress_callback: Optional progress callback

        Returns:
            True if successful, False otherwise
        """
        # Store callback
        old_callback = self.progress_callback
        if progress_callback:
            self.progress_callback = progress_callback

        try:
            # Extract chapters based on file type
            if input_path.endswith('.epub'):
                chapters = self.extract_chapters_from_epub(input_path, options.debug)
            elif input_path.endswith('.pdf'):
                chapters = self.extract_chapters_from_pdf(input_path, options.debug)
            else:
                # Plain text file
                with open(input_path, 'r', encoding='utf-8') as f:
                    text = f.read()
                chapters = [Chapter(title="Chapter 1", content=text, order=1)]

            if not chapters:
                return False

            # Process all chapters
            all_samples = []
            sample_rate = None

            for chapter in chapters:
                samples, sr = self.generate_audio(chapter.content, options)
                if samples is not None:
                    all_samples.extend(samples)
                    if sample_rate is None:
                        sample_rate = sr

            if all_samples:
                self.save_audio(
                    np.array(all_samples),
                    sample_rate,
                    output_path,
                    options.format
                )
                return True

            return False

        finally:
            self.progress_callback = old_callback

    async def generate_audio_async(
        self,
        text: str,
        options: ProcessingOptions,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> Tuple[Optional[np.ndarray], Optional[int]]:
        """Generate audio from text asynchronously.

        Args:
            text: Text to convert
            options: Processing options
            progress_callback: Optional progress callback

        Returns:
            Tuple of (audio samples, sample rate) or (None, None) on error
        """
        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()

        # Store callback
        old_callback = self.progress_callback
        if progress_callback:
            self.progress_callback = progress_callback

        try:
            result = await loop.run_in_executor(
                None,
                self.generate_audio,
                text,
                options
            )
            return result
        finally:
            self.progress_callback = old_callback

    async def process_file_async(
        self,
        input_path: str,
        output_path: str,
        options: ProcessingOptions,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> bool:
        """Process a file asynchronously.

        Args:
            input_path: Path to input file
            output_path: Path to output audio file
            options: Processing options
            progress_callback: Optional progress callback

        Returns:
            True if successful, False otherwise
        """
        loop = asyncio.get_event_loop()

        # Store callback
        old_callback = self.progress_callback
        if progress_callback:
            self.progress_callback = progress_callback

        try:
            result = await loop.run_in_executor(
                None,
                self.process_file,
                input_path,
                output_path,
                options,
                progress_callback
            )
            return result
        finally:
            self.progress_callback = old_callback

    async def stream_audio_async(
        self,
        text: str,
        options: ProcessingOptions
    ) -> AsyncIterator[Tuple[np.ndarray, int]]:
        """Stream audio generation chunk by chunk.

        Args:
            text: Text to convert
            options: Processing options

        Yields:
            Tuples of (audio samples, sample rate) for each chunk
        """
        if self.kokoro is None:
            self.load_model()

        # Validate
        lang = self.validate_language(options.lang)
        voice = self.validate_voice(options.voice) if options.voice else "af_sarah"

        # Chunk text
        chunks = self.chunk_text(text)

        # Process chunks one at a time
        for i, chunk in enumerate(chunks, 1):
            if self.progress_callback:
                self.progress_callback("Streaming", i, len(chunks))

            # Use kokoro's stream API if available
            if hasattr(self.kokoro, 'create_stream'):
                async for samples, sample_rate in self.kokoro.create_stream(
                    chunk, voice=voice, speed=options.speed, lang=lang
                ):
                    yield np.array(samples), sample_rate
            else:
                # Fallback to regular generation
                loop = asyncio.get_event_loop()
                samples, sample_rate = await loop.run_in_executor(
                    None,
                    self.process_chunk,
                    chunk,
                    voice,
                    options.speed,
                    lang,
                    0,
                    options.debug
                )
                if samples is not None:
                    yield np.array(samples), sample_rate
