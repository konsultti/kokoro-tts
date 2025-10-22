#!/usr/bin/env python3

# Standard library imports
import os
import sys
import shutil
import itertools
import threading
import time
import signal
import difflib
import warnings
from threading import Event
import re

# Third-party imports
import numpy as np
from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup
import soundfile as sf
import sounddevice as sd
from kokoro_onnx import Kokoro
import pymupdf4llm
import fitz
from pydub import AudioSegment

warnings.filterwarnings("ignore", category=UserWarning, module='ebooklib')
warnings.filterwarnings("ignore", category=FutureWarning, module='ebooklib')

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

# Global flag to stop the spinner and audio
stop_spinner = False
stop_audio = False

def check_gpu_availability(use_gpu=False):
    """Check if GPU is available and provide helpful information.

    Args:
        use_gpu: If True, automatically select the best available GPU provider

    Returns:
        Dictionary with GPU availability information and selected provider
    """
    import importlib.metadata
    import onnxruntime as ort

    # Get available providers from onnxruntime
    available_providers = ort.get_available_providers()

    has_cuda = 'CUDAExecutionProvider' in available_providers
    has_tensorrt = 'TensorrtExecutionProvider' in available_providers
    has_rocm = 'ROCMExecutionProvider' in available_providers
    has_coreml = 'CoreMLExecutionProvider' in available_providers

    onnx_provider_env = os.getenv('ONNX_PROVIDER')

    # If use_gpu is True and no env variable set, select best available provider
    selected_provider = onnx_provider_env
    if use_gpu and not onnx_provider_env:
        # Priority: TensorRT > CUDA > ROCm > CoreML > None
        if has_tensorrt:
            selected_provider = 'TensorrtExecutionProvider'
        elif has_cuda:
            selected_provider = 'CUDAExecutionProvider'
        elif has_rocm:
            selected_provider = 'ROCMExecutionProvider'
        elif has_coreml:
            selected_provider = 'CoreMLExecutionProvider'

    try:
        # Check if onnxruntime-gpu is installed
        gpu_version = importlib.metadata.version('onnxruntime-gpu')

        return {
            'gpu_package_installed': True,
            'gpu_package_version': gpu_version,
            'available_providers': available_providers,
            'has_cuda': has_cuda,
            'has_tensorrt': has_tensorrt,
            'has_rocm': has_rocm,
            'has_coreml': has_coreml,
            'env_provider': onnx_provider_env,
            'selected_provider': selected_provider,
            'will_use_gpu': selected_provider in ['CUDAExecutionProvider', 'TensorrtExecutionProvider', 'ROCMExecutionProvider', 'CoreMLExecutionProvider'] if selected_provider else False
        }
    except importlib.metadata.PackageNotFoundError:
        # onnxruntime-gpu not installed, but check if standard onnxruntime has CoreML
        return {
            'gpu_package_installed': False,
            'gpu_package_version': None,
            'available_providers': available_providers,
            'has_cuda': has_cuda,
            'has_tensorrt': has_tensorrt,
            'has_rocm': has_rocm,
            'has_coreml': has_coreml,
            'env_provider': onnx_provider_env,
            'selected_provider': selected_provider,
            'will_use_gpu': selected_provider in ['CoreMLExecutionProvider'] if selected_provider else False
        }

def print_gpu_info(gpu_info, auto_enabled=False, requested_gpu=False):
    """Print GPU availability information.

    Args:
        gpu_info: Dictionary with GPU availability info
        auto_enabled: Whether GPU was auto-enabled
        requested_gpu: Whether user explicitly requested GPU via --gpu flag
    """
    selected_provider = gpu_info.get('selected_provider')

    if selected_provider:
        if gpu_info['env_provider']:
            # Provider set via environment variable
            print(f"GPU acceleration: Using {selected_provider} (set via ONNX_PROVIDER)")
        elif requested_gpu:
            # Provider auto-selected due to --gpu flag
            print(f"GPU acceleration: Using {selected_provider} (auto-selected via --gpu flag)")
        elif auto_enabled:
            print(f"GPU acceleration: Using {selected_provider} (auto-enabled)")
        return

    # If user requested GPU but no provider available
    if requested_gpu:
        print("GPU acceleration: Requested but not available")
        # Check for available acceleration providers
        providers = []
        if gpu_info['has_cuda']:
            providers.append('CUDA')
        if gpu_info['has_tensorrt']:
            providers.append('TensorRT')
        if gpu_info['has_rocm']:
            providers.append('ROCm')
        if gpu_info['has_coreml']:
            providers.append('CoreML')

        if not gpu_info['gpu_package_installed'] and (gpu_info['has_cuda'] or gpu_info['has_tensorrt'] or gpu_info['has_rocm']):
            print("  Error: --gpu requires onnxruntime-gpu installation for CUDA/TensorRT/ROCm")
            print("  Install with: pip install 'kokoro-tts[gpu]'")
            print("  Or: pip install onnxruntime-gpu")
        elif not providers:
            print("  No GPU providers detected")
            if not gpu_info['gpu_package_installed']:
                print("  CUDA/ROCm users: pip install 'kokoro-tts[gpu]'")
                print("  Apple Silicon users: CoreML should be available automatically")
        return

    # No GPU selected or requested
    # Check for available acceleration providers
    providers = []
    if gpu_info['has_cuda']:
        providers.append('CUDA')
    if gpu_info['has_tensorrt']:
        providers.append('TensorRT')
    if gpu_info['has_rocm']:
        providers.append('ROCm')
    if gpu_info['has_coreml']:
        providers.append('CoreML')

    if providers:
        print(f"GPU acceleration: Available ({', '.join(providers)}) but not enabled")
        print("  To enable, use --gpu flag or set environment variable:")
        if gpu_info['has_coreml']:
            print("    export ONNX_PROVIDER=CoreMLExecutionProvider  # For Apple Silicon")
        if gpu_info['has_cuda']:
            print("    export ONNX_PROVIDER=CUDAExecutionProvider")
        if gpu_info['has_tensorrt']:
            print("    export ONNX_PROVIDER=TensorrtExecutionProvider")
        if gpu_info['has_rocm']:
            print("    export ONNX_PROVIDER=ROCMExecutionProvider")
    elif gpu_info['gpu_package_installed']:
        print("GPU acceleration: onnxruntime-gpu installed but no GPU detected")
    else:
        print("GPU acceleration: Not available")
        print("  CUDA/ROCm users: pip install 'kokoro-tts[gpu]'")
        print("  Apple Silicon users: CoreML support available in standard onnxruntime")

def check_required_files(model_path="kokoro-v1.0.onnx", voices_path="voices-v1.0.bin"):
    """Check if required model files exist and provide helpful error messages."""
    required_files = {
        model_path: "https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/kokoro-v1.0.onnx",
        voices_path: "https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/voices-v1.0.bin"
    }
    
    missing_files = []
    for filepath, download_url in required_files.items():
        if not os.path.exists(filepath):
            missing_files.append((filepath, download_url))
    
    if missing_files:
        print("Error: Required model files are missing:")
        for filepath, download_url in missing_files:
            print(f"  • {filepath}")
        print("\nYou can download the missing files using these commands:")
        for filepath, download_url in missing_files:
            print(f"  wget {download_url}")
        print(f"\nPlace the downloaded files in the same directory where you run the `kokoro-tts` command.")
        print(f"Or specify custom paths using --model and --voices options.")
        sys.exit(1)

def spinning_wheel(message="Processing...", progress=None):
    """Display a spinning wheel with a message."""
    spinner = itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'])
    while not stop_spinner:
        spin = next(spinner)
        if progress is not None:
            sys.stdout.write(f"\r{message} {progress} {spin}")
        else:
            sys.stdout.write(f"\r{message} {spin}")
        sys.stdout.flush()
        time.sleep(0.1)
    # Clear the spinner line when done
    sys.stdout.write('\r' + ' ' * (len(message) + 50) + '\r')
    sys.stdout.flush()

def list_available_voices(kokoro):
    voices = list(kokoro.get_voices())
    print("Available voices:")
    for idx, voice in enumerate(voices):
        print(f"{idx + 1}. {voice}")
    return voices

def extract_text_from_epub(epub_file):
    book = epub.read_epub(epub_file)
    full_text = ""
    for item in book.get_items():
        if item.get_type() == ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_body_content(), "html.parser")
            full_text += soup.get_text()
    return full_text

def chunk_text(text, initial_chunk_size=1000):
    """Split text into chunks at sentence boundaries with dynamic sizing."""
    sentences = text.replace('\n', ' ').split('.')
    chunks = []
    current_chunk = []
    current_size = 0
    chunk_size = initial_chunk_size

    for sentence in sentences:
        if not sentence.strip():
            continue  # Skip empty sentences

        sentence = sentence.strip() + '.'
        sentence_size = len(sentence)

        # If a single sentence is too long, split it into smaller pieces
        if sentence_size > chunk_size:
            words = sentence.split()
            current_piece = []
            current_piece_size = 0

            for word in words:
                word_size = len(word) + 1  # +1 for space
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

        # Start new chunk if current one would be too large
        if current_size + sentence_size > chunk_size and current_chunk:
            chunks.append(' '.join(current_chunk))
            current_chunk = []
            current_size = 0

        current_chunk.append(sentence)
        current_size += sentence_size

    if current_chunk:
        chunks.append(' '.join(current_chunk))

    return chunks

def save_audio_with_format(samples, sample_rate, output_file, format):
    """Save audio samples to file with specified format.

    Args:
        samples: Audio sample data
        sample_rate: Sample rate (Hz)
        output_file: Output file path
        format: Output format ('wav', 'mp3', or 'm4a')
    """
    if format == 'wav':
        # Direct WAV output
        sf.write(output_file, samples, sample_rate)
    elif format in ['mp3', 'm4a']:
        # Convert to MP3 or M4A via pydub
        import tempfile

        # First save as temporary WAV file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
            temp_wav_path = temp_wav.name
            sf.write(temp_wav_path, samples, sample_rate)

        try:
            # Load WAV and convert to target format
            audio = AudioSegment.from_wav(temp_wav_path)

            if format == 'mp3':
                audio.export(output_file, format='mp3', bitrate='128k')
            elif format == 'm4a':
                audio.export(output_file, format='mp4', codec='aac', bitrate='128k')
        finally:
            # Clean up temporary WAV file
            os.remove(temp_wav_path)

def validate_language(lang, kokoro=None):
    """Validate if the language is supported.

    Note: kokoro parameter is kept for backward compatibility but not used.
    Languages are now hardcoded as kokoro-onnx 0.4.9+ doesn't expose get_languages().
    """
    if lang not in SUPPORTED_LANGUAGES:
        supported_langs = ', '.join(sorted(SUPPORTED_LANGUAGES))
        raise ValueError(f"Unsupported language: {lang}\nSupported languages are: {supported_langs}")
    return lang

def print_usage():
    print("""
Usage: kokoro-tts <input_text_file> [<output_audio_file>] [options]

Commands:
    -h, --help         Show this help message
    --help-languages   List all supported languages
    --help-voices      List all available voices
    --merge-chunks     Merge existing chunks in split-output directory into chapter files

Options:
    --stream            Stream audio instead of saving to file
    --speed <float>     Set speech speed (default: 1.0)
    --lang <str>        Set language (default: en-us)
    --voice <str>       Set voice or blend voices (default: interactive selection)
    --split-output <dir> Save each chunk as separate file in directory
    --chapters <dir>    Save one audio file per chapter in directory (memory efficient)
    --format <str>      Audio format: wav, mp3, or m4a (default: wav)
    --gpu               Enable GPU acceleration (requires onnxruntime-gpu installation)
    --debug             Show detailed debug information
    --model <path>      Path to kokoro-v1.0.onnx model file (default: ./kokoro-v1.0.onnx)
    --voices <path>     Path to voices-v1.0.bin file (default: ./voices-v1.0.bin)

Audiobook Creation (EPUB/PDF only):
    --audiobook <output.m4a>     Create M4A audiobook with metadata and chapters
    --select-chapters <sel>      Chapter selection: "all", "1,3,5", "1-5" (default: all)
    --keep-temp                  Keep temporary files after creation
    --temp-dir <dir>             Custom temporary directory
    --no-metadata                Skip metadata embedding
    --no-chapters                Skip chapter marker embedding
    --cover <path>               Custom cover image path
    --title <str>                Override book title
    --author <str>               Override book author
    --narrator <str>             Set narrator name
    --year <str>                 Set publication year
    --genre <str>                Set genre/category
    --description <str>          Set book description

Input formats:
    .txt               Text file input
    .epub              EPUB book input (will process chapters)
    .pdf               PDF document input (extracts chapters from TOC or content)

Examples:
    # Basic text-to-speech
    kokoro-tts input.txt output.wav --speed 1.2 --lang en-us --voice af_sarah
    kokoro-tts input.txt --stream --speed 0.8
    kokoro-tts input.txt output.wav --voice "af_sarah:60,am_adam:40"

    # Chapter-based processing
    kokoro-tts input.epub --chapters ./audiobook/ --format m4a
    kokoro-tts input.epub --split-output ./chunks/ --format mp3
    kokoro-tts input.pdf --chapters ./chapters/ --format m4a

    # Audiobook creation (NEW!)
    kokoro-tts book.epub --audiobook audiobook.m4a
    kokoro-tts book.epub --audiobook output.m4a --select-chapters "1-5,10"
    kokoro-tts book.epub --audiobook output.m4a --title "My Book" --author "John Doe"
    kokoro-tts book.pdf --audiobook output.m4a --narrator "Sarah" --keep-temp

    # Voice blending
    kokoro-tts input.txt --stream --voice "am_adam,af_sarah"  # 50-50 blend

    # Utilities
    kokoro-tts --merge-chunks --split-output ./chunks/ --format wav
    kokoro-tts --help-voices
    kokoro-tts --help-languages

    # Custom model paths
    kokoro-tts input.txt output.wav --model /path/to/model.onnx --voices /path/to/voices.bin
    """)

def print_supported_languages(model_path="kokoro-v1.0.onnx", voices_path="voices-v1.0.bin"):
    """Print all supported languages.

    Note: model_path and voices_path parameters are kept for backward compatibility
    but not used. Languages are now hardcoded as kokoro-onnx 0.4.9+ doesn't expose
    get_languages().
    """
    print("\nSupported languages:")
    for lang in sorted(SUPPORTED_LANGUAGES):
        print(f"    {lang}")
    print()

def print_supported_voices(model_path="kokoro-v1.0.onnx", voices_path="voices-v1.0.bin"):
    """Print all supported voices from Kokoro."""
    check_required_files(model_path, voices_path)
    try:
        kokoro = Kokoro(model_path, voices_path)
        voices = sorted(kokoro.get_voices())
        print("\nSupported voices:")
        for idx, voice in enumerate(voices):
            print(f"    {idx + 1}. {voice}")
        print()
    except Exception as e:
        print(f"Error loading model to get supported voices: {e}")
        sys.exit(1)

def validate_voice(voice, kokoro):
    """Validate if the voice is supported and handle voice blending.
    
    Format for blended voices: "voice1:weight,voice2:weight"
    Example: "af_sarah:60,am_adam:40" for 60-40 blend
    """
    try:
        supported_voices = set(kokoro.get_voices())
        
        # Parse comma seperated voices for blend
        if ',' in voice:
            voices = []
            weights = []
            
            # Parse voice:weight pairs
            for pair in voice.split(','):
                if ':' in pair:
                    v, w = pair.strip().split(':')
                    voices.append(v.strip())
                    weights.append(float(w.strip()))
                else:
                    voices.append(pair.strip())
                    weights.append(50.0)  # Default to 50% if no weight specified
            
            if len(voices) != 2:
                raise ValueError("voice blending needs two comma separated voices")
                 
            # Validate voice
            for v in voices:
                if v not in supported_voices:
                    supported_voices_list = ', '.join(sorted(supported_voices))
                    raise ValueError(f"Unsupported voice: {v}\nSupported voices are: {supported_voices_list}")
             
            # Normalize weights to sum to 100
            total = sum(weights)
            if total != 100:
                weights = [w * (100/total) for w in weights]
            
            # Create voice blend style
            style1 = kokoro.get_voice_style(voices[0])
            style2 = kokoro.get_voice_style(voices[1])
            blend = np.add(style1 * (weights[0]/100), style2 * (weights[1]/100))
            return blend
             
        # Single voice validation
        if voice not in supported_voices:
            supported_voices_list = ', '.join(sorted(supported_voices))
            raise ValueError(f"Unsupported voice: {voice}\nSupported voices are: {supported_voices_list}")
        return voice
    except Exception as e:
        print(f"Error getting supported voices: {e}")
        sys.exit(1)

def extract_chapters_from_epub(epub_file, debug=False, skip_confirmation=False):
    """Extract chapters from epub file using ebooklib's metadata and TOC."""
    if not os.path.exists(epub_file):
        raise FileNotFoundError(f"EPUB file not found: {epub_file}")
    
    book = epub.read_epub(epub_file)
    chapters = []
    
    if debug:
        print("\nBook Metadata:")
        for key, value in book.metadata.items():
            print(f"  {key}: {value}")
        
        print("\nTable of Contents:")
        def print_toc(items, depth=0):
            for item in items:
                indent = "  " * depth
                if isinstance(item, tuple):
                    section_title, section_items = item
                    print(f"{indent}• Section: {section_title}")
                    print_toc(section_items, depth + 1)
                elif isinstance(item, epub.Link):
                    print(f"{indent}• {item.title} -> {item.href}")
        print_toc(book.toc)
    
    def get_chapter_content(soup, start_id, next_id=None):
        """Extract content between two fragment IDs"""
        content = []
        start_elem = soup.find(id=start_id)
        
        if not start_elem:
            return ""
        
        # Skip the heading itself if it's a heading
        if start_elem.name in ['h1', 'h2', 'h3', 'h4']:
            current = start_elem.find_next_sibling()
        else:
            current = start_elem
            
        while current:
            # Stop if we hit the next chapter
            if next_id and current.get('id') == next_id:
                break
            # Stop if we hit another chapter heading
            if current.name in ['h1', 'h2', 'h3'] and 'chapter' in current.get_text().lower():
                break
            content.append(current.get_text())
            current = current.find_next_sibling()
            
        return '\n'.join(content).strip()
    
    def process_toc_items(items, depth=0):
        processed = []
        for i, item in enumerate(items):
            if isinstance(item, tuple):
                section_title, section_items = item
                if debug:
                    print(f"{'  ' * depth}Processing section: {section_title}")
                processed.extend(process_toc_items(section_items, depth + 1))
            elif isinstance(item, epub.Link):
                if debug:
                    print(f"{'  ' * depth}Processing link: {item.title} -> {item.href}")
                
                # Skip if title suggests it's front matter
                if (item.title.lower() in ['copy', 'copyright', 'title page', 'cover'] or
                    item.title.lower().startswith('by')):
                    continue
                
                # Extract the file name and fragment from href
                href_parts = item.href.split('#')
                file_name = href_parts[0]
                fragment_id = href_parts[1] if len(href_parts) > 1 else None
                
                # Find the document
                doc = next((doc for doc in book.get_items_of_type(ITEM_DOCUMENT) 
                          if doc.file_name.endswith(file_name)), None)
                
                if doc:
                    content = doc.get_content().decode('utf-8')
                    soup = BeautifulSoup(content, "html.parser")

                    # If no fragment ID, get whole document content
                    if not fragment_id:
                        text_content = soup.get_text().strip()
                    else:
                        # Get the next fragment ID if available
                        next_item = items[i + 1] if i + 1 < len(items) else None
                        next_fragment = None
                        if isinstance(next_item, epub.Link):
                            next_href_parts = next_item.href.split('#')
                            if next_href_parts[0] == file_name and len(next_href_parts) > 1:
                                next_fragment = next_href_parts[1]

                        # Extract content between fragments
                        text_content = get_chapter_content(soup, fragment_id, next_fragment)

                    # Clean up soup object to free memory
                    soup.decompose()
                    del soup, content

                    if text_content:
                        chapters.append({
                            'title': item.title,
                            'content': text_content,
                            'order': len(processed) + 1
                        })
                        processed.append(item)
                        if debug:
                            print(f"{'  ' * depth}Added chapter: {item.title}")
                            print(f"{'  ' * depth}Content length: {len(text_content)} chars")
                            print(f"{'  ' * depth}Word count: {len(text_content.split())}")
        return processed
    
    # Process the table of contents
    process_toc_items(book.toc)
    
    # If no chapters were found through TOC, try processing all documents
    if not chapters:
        if debug:
            print("\nNo chapters found in TOC, processing all documents...")
        
        # Get all document items sorted by file name
        docs = sorted(
            book.get_items_of_type(ITEM_DOCUMENT),
            key=lambda x: x.file_name
        )
        
        for doc in docs:
            if debug:
                print(f"Processing document: {doc.file_name}")

            content = doc.get_content().decode('utf-8')
            soup = BeautifulSoup(content, "html.parser")

            # Try to find chapter divisions
            chapter_divs = soup.find_all(['h1', 'h2', 'h3'], class_=lambda x: x and 'chapter' in x.lower())
            if not chapter_divs:
                chapter_divs = soup.find_all(lambda tag: tag.name in ['h1', 'h2', 'h3'] and
                                          ('chapter' in tag.get_text().lower() or
                                           'book' in tag.get_text().lower()))

            if chapter_divs:
                # Process each chapter division
                for i, div in enumerate(chapter_divs):
                    title = div.get_text().strip()

                    # Get content until next chapter heading or end
                    chapter_content = ''
                    for tag in div.find_next_siblings():
                        if tag.name in ['h1', 'h2', 'h3'] and (
                            'chapter' in tag.get_text().lower() or
                            'book' in tag.get_text().lower()):
                            break
                        chapter_content += tag.get_text() + '\n'

                    if chapter_content.strip():
                        chapters.append({
                            'title': title,
                            'content': chapter_content.strip(),
                            'order': len(chapters) + 1
                        })
                        if debug:
                            print(f"Added chapter: {title}")
            else:
                # No chapter divisions found, treat whole document as one chapter
                text_content = soup.get_text().strip()
                if text_content:
                    # Try to find a title
                    title_tag = soup.find(['h1', 'h2', 'title'])
                    title = title_tag.get_text().strip() if title_tag else f"Chapter {len(chapters) + 1}"

                    if title.lower() not in ['copy', 'copyright', 'title page', 'cover']:
                        chapters.append({
                            'title': title,
                            'content': text_content,
                            'order': len(chapters) + 1
                        })
                        if debug:
                            print(f"Added chapter: {title}")

            # Clean up soup object to free memory after processing each document
            soup.decompose()
            del soup, content
    
    # Print summary
    if chapters:
        print("\nSuccessfully extracted {} chapters:".format(len(chapters)))
        for chapter in chapters:
            print(f"  {chapter['order']}. {chapter['title']}")
        
        total_words = sum(len(chapter['content'].split()) for chapter in chapters)
        print("\nBook Summary:")
        print(f"Total Chapters: {len(chapters)}")
        print(f"Total Words: {total_words:,}")
        print(f"Total Duration: {total_words / 150:.1f} minutes")
        
        if debug:
            print("\nDetailed Chapter List:")
            for chapter in chapters:
                word_count = len(chapter['content'].split())
                print(f"  • {chapter['title']}")
                print(f"    Words: {word_count:,}")
                print(f"    Duration: {word_count / 150:.1f} minutes")
    else:
        print("\nWarning: No chapters were extracted!")
        if debug:
            print("\nAvailable documents:")
            for doc in book.get_items_of_type(ITEM_DOCUMENT):
                print(f"  • {doc.file_name}")
    
    return chapters

class PdfParser:
    """Parser for extracting chapters from PDF files.
    
    Attempts to extract chapters first from table of contents,
    then falls back to markdown-based extraction if TOC fails.
    """
    
    def __init__(self, pdf_path: str, debug: bool = False, min_chapter_length: int = 50, skip_confirmation: bool = False):
        """Initialize PDF parser.

        Args:
            pdf_path: Path to PDF file
            debug: Enable debug logging
            min_chapter_length: Minimum text length to consider as chapter
            skip_confirmation: Skip user confirmation prompt
        """
        self.pdf_path = pdf_path
        self.chapters = []
        self.debug = debug
        self.min_chapter_length = min_chapter_length
        self.skip_confirmation = skip_confirmation
        
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    def get_chapters(self):
        """Extract chapters from PDF file.
        
        Returns:
            List of chapter dictionaries with title, content and order.
        """
        if self.debug:
            print("\nDEBUG: Starting chapter extraction...")
            print(f"DEBUG: PDF file: {self.pdf_path}")
            print(f"DEBUG: Min chapter length: {self.min_chapter_length}")
        
        # Try TOC extraction first
        if self.get_chapters_from_toc():
            if self.debug:
                print(f"\nDEBUG: Successfully extracted {len(self.chapters)} chapters from TOC")
            return self.chapters
            
        # Fall back to markdown extraction
        if self.debug:
            print("\nDEBUG: TOC extraction failed, trying markdown conversion...")
        
        self.chapters = self.get_chapters_from_markdown()
        
        if self.debug:
            print(f"\nDEBUG: Markdown extraction complete")
            print(f"DEBUG: Found {len(self.chapters)} chapters")
            
        return self.chapters

    def get_chapters_from_toc(self):
        """Extract chapters using PDF table of contents.
        
        Returns:
            bool: True if chapters were found, False otherwise
        """
        doc = None
        try:
            doc = fitz.open(self.pdf_path)
            toc = doc.get_toc()
            
            if not toc:
                if self.debug:
                    print("\nDEBUG: No table of contents found")
                return False

            # Print TOC structure
            print("\nTable of Contents:")
            for level, title, page in toc:
                title = self._clean_title(title)
                indent = "  " * (level - 1)
                print(f"{indent}{'•' if level > 1 else '>'} {title} (page {page})")
            
            if self.debug:
                print(f"\nDEBUG: Found {len(toc)} TOC entries")
            
            # Get user confirmation (unless skipped)
            if not self.skip_confirmation:
                print("\nPress Enter to start processing, or Ctrl+C to cancel...")
                input()
            
            # Extract level 1 chapters, filtering out empty titles and duplicates
            seen_pages = set()
            chapter_markers = []
            
            for level, title, page in toc:
                if level == 1:
                    title = self._clean_title(title)
                    # Skip empty titles or titles that start on same page as previous entry
                    if title and page not in seen_pages:
                        chapter_markers.append((title, page))
                        seen_pages.add(page)
            
            if not chapter_markers:
                if self.debug:
                    print("\nDEBUG: No level 1 chapters found in TOC")
                return False
            
            if self.debug:
                print(f"\nDEBUG: Found {len(chapter_markers)} chapters:")
                for title, page in chapter_markers:
                    print(f"DEBUG: • {title} (page {page})")
            
            # Process each chapter
            for i, (title, start_page) in enumerate(chapter_markers):
                if self.debug:
                    print(f"\nDEBUG: Processing chapter {i+1}/{len(chapter_markers)}")
                    print(f"DEBUG: Title: {title}")
                    print(f"DEBUG: Start page: {start_page}")
                
                # Get chapter end page
                end_page = (chapter_markers[i + 1][1] - 1 
                           if i < len(chapter_markers) - 1 
                           else doc.page_count)
                
                # Extract chapter text
                chapter_text = self._extract_chapter_text(doc, start_page - 1, end_page)
                
                if len(chapter_text.strip()) > self.min_chapter_length:
                    self.chapters.append({
                        'title': title,
                        'content': chapter_text,
                        'order': i + 1
                    })
                    if self.debug:
                        print(f"DEBUG: Added chapter with {len(chapter_text.split())} words")
            
            return bool(self.chapters)
            
        except Exception as e:
            if self.debug:
                print(f"\nDEBUG: Error in TOC extraction: {str(e)}")
            return False
            
        finally:
            if doc:
                doc.close()

    def get_chapters_from_markdown(self):
        """Extract chapters by converting PDF to markdown.
        
        Returns:
            List of chapter dictionaries
        """
        chapters = []
        try:
            def progress(current, total):
                if self.debug:
                    print(f"\rConverting page {current}/{total}...", end="", flush=True)
            
            # Convert PDF to markdown
            md_text = pymupdf4llm.to_markdown(
                self.pdf_path,
                show_progress=True,
                progress_callback=progress
            )
            
            # Clean up markdown text
            md_text = self._clean_markdown(md_text)
            
            # Extract chapters
            current_chapter = None
            current_text = []
            chapter_count = 0
            
            for line in md_text.split('\n'):
                if line.startswith('#'):
                    # Save previous chapter if exists
                    if current_chapter and current_text:
                        chapter_text = ''.join(current_text)
                        if len(chapter_text.strip()) > self.min_chapter_length:
                            chapters.append({
                                'title': current_chapter,
                                'content': chapter_text,
                                'order': chapter_count
                            })
                    
                    # Start new chapter
                    chapter_count += 1
                    current_chapter = f"Chapter {chapter_count}_{line.lstrip('#').strip()}"
                    current_text = []
                else:
                    if current_chapter is not None:
                        current_text.append(line + '\n')
            
            # Add final chapter
            if current_chapter and current_text:
                chapter_text = ''.join(current_text)
                if len(chapter_text.strip()) > self.min_chapter_length:
                    chapters.append({
                        'title': current_chapter,
                        'content': chapter_text,
                        'order': chapter_count
                    })
            
            return chapters
            
        except Exception as e:
            if self.debug:
                print(f"\nDEBUG: Error in markdown extraction: {str(e)}")
            return chapters

    def _clean_title(self, title: str) -> str:
        """Clean up chapter title text."""
        return title.strip().replace('\u200b', ' ')
        
    def _clean_markdown(self, text: str) -> str:
        """Clean up converted markdown text."""
        # Remove page markers
        text = text.replace('-', '')
        # Remove other unwanted characters
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
        
    def _extract_chapter_text(self, doc, start_page: int, end_page: int) -> str:
        """Extract text from PDF pages."""
        chapter_text = []
        for page_num in range(start_page, end_page):
            try:
                page = doc[page_num]
                text = page.get_text()
                chapter_text.append(text)
            except Exception as e:
                if self.debug:
                    print(f"\nDEBUG: Error extracting page {page_num}: {str(e)}")
                continue
                
        return '\n'.join(chapter_text)

def process_chunk_sequential(chunk: str, kokoro: Kokoro, voice: str, speed: float, lang: str, 
                           retry_count=0, debug=False) -> tuple[list[float] | None, int | None]:
    """Process a single chunk of text sequentially with automatic chunk size adjustment."""
    try:
        if debug:
            sys.stdout.write("\033[K")  # Clear to end of line
            sys.stdout.write(f"\nDEBUG: Processing chunk of length {len(chunk)}")
            if retry_count > 0:
                sys.stdout.write(f"\nDEBUG: Retry #{retry_count} - Reduced chunk size to {len(chunk)}")
            sys.stdout.write("\n")  # Move back to progress line
            sys.stdout.flush()
        
        samples, sample_rate = kokoro.create(chunk, voice=voice, speed=speed, lang=lang)
        return samples, sample_rate
    except Exception as e:
        error_msg = str(e)
        if "index 510 is out of bounds" in error_msg:
            current_size = len(chunk)
            new_size = int(current_size * 0.6)  # Reduce by 40% to converge faster
            
            if debug:
                sys.stdout.write("\033[K")  # Clear to end of line
                sys.stdout.write(f"\nDEBUG: Phoneme length error detected on chunk size {current_size}")
                sys.stdout.write(f"\nDEBUG: Attempting retry with size {new_size}")
                sys.stdout.write("\n")
            else:
                # Show a user-friendly message in non-debug mode
                sys.stdout.write("\033[K")  # Clear to end of line
                sys.stdout.write("\rNote: Automatically handling a long text segment...")
                sys.stdout.write("\n")
            sys.stdout.flush()
            
            # Split this chunk into smaller pieces
            words = chunk.split()
            current_piece = []
            current_size = 0
            pieces = []
            
            for word in words:
                word_size = len(word) + 1  # +1 for space
                if current_size + word_size > new_size:
                    if current_piece:
                        pieces.append(' '.join(current_piece).strip())
                    current_piece = [word]
                    current_size = word_size
                else:
                    current_piece.append(word)
                    current_size += word_size
            
            if current_piece:
                pieces.append(' '.join(current_piece).strip())
            
            if debug:
                sys.stdout.write("\033[K")
                sys.stdout.write(f"\nDEBUG: Split chunk into {len(pieces)} pieces")
                for i, piece in enumerate(pieces, 1):
                    sys.stdout.write(f"\nDEBUG: Piece {i} length: {len(piece)}")
                sys.stdout.write("\n")
                sys.stdout.flush()
            
            # Process each piece
            all_samples = []
            last_sample_rate = None
            
            for i, piece in enumerate(pieces, 1):
                if debug:
                    sys.stdout.write("\033[K")
                    sys.stdout.write(f"\nDEBUG: Processing piece {i}/{len(pieces)}")
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                
                samples, sr = process_chunk_sequential(piece, kokoro, voice, speed, lang, 
                                                     retry_count + 1, debug)
                if samples is not None:
                    all_samples.extend(samples)
                    last_sample_rate = sr
            
            if all_samples:
                if debug:
                    sys.stdout.write("\033[K")
                    sys.stdout.write(f"\nDEBUG: Successfully processed all {len(pieces)} pieces")
                    sys.stdout.write("\n")
                sys.stdout.flush()
                return all_samples, last_sample_rate
            
            if debug:
                sys.stdout.write("\033[K")
                sys.stdout.write(f"\nDEBUG: Failed to process any pieces after splitting")
                sys.stdout.write("\n")
            sys.stdout.flush()
            
        # Show a more user-friendly error message in non-debug mode
        if not debug:
            sys.stdout.write("\033[K")
            sys.stdout.write(f"\rError: Unable to process text segment. Try using smaller chunks or enable debug mode for details.")
        else:
            sys.stdout.write("\033[K")
            sys.stdout.write(f"\nError processing chunk: {e}")
            sys.stdout.write(f"\nDEBUG: Full error message: {error_msg}")
            sys.stdout.write(f"\nDEBUG: Chunk length: {len(chunk)}")
        sys.stdout.write("\n")
        sys.stdout.flush()
        
        return None, None

def convert_text_to_audio(input_file, output_file=None, voice=None, speed=1.0, lang="en-us",
                         stream=False, split_output=None, chapters_output=None, format="wav", debug=False, stdin_indicators=None,
                         model_path="kokoro-v1.0.onnx", voices_path="voices-v1.0.bin", use_gpu=False):
    global stop_spinner
    
    # Define stdin indicators if not provided
    if stdin_indicators is None:
        stdin_indicators = ['/dev/stdin', '-', 'CONIN$']  # CONIN$ is Windows stdin
    
    # Check for required files first
    check_required_files(model_path, voices_path)
    
    # Load Kokoro model
    try:
        # Check and display GPU availability before loading model
        gpu_info = check_gpu_availability(use_gpu=use_gpu)

        # Auto-enable CoreML on macOS if available and no provider is set (unless user explicitly requested GPU)
        auto_enabled = False
        if not use_gpu and gpu_info['has_coreml'] and not gpu_info['env_provider']:
            os.environ['ONNX_PROVIDER'] = 'CoreMLExecutionProvider'
            gpu_info['selected_provider'] = 'CoreMLExecutionProvider'
            auto_enabled = True

        # If GPU was requested or auto-selected, set the environment variable
        if gpu_info.get('selected_provider') and not gpu_info.get('env_provider'):
            os.environ['ONNX_PROVIDER'] = gpu_info['selected_provider']

        print_gpu_info(gpu_info, auto_enabled, requested_gpu=use_gpu)
        print()  # Blank line for readability

        # Exit with error if --gpu was requested but no provider is available
        if use_gpu and not gpu_info.get('selected_provider'):
            print("\nError: Cannot enable GPU acceleration. No compatible GPU provider found.")
            sys.exit(1)

        kokoro = Kokoro(model_path, voices_path)

        # Validate language after loading model
        lang = validate_language(lang, kokoro)
        
        # Handle voice selection
        if voice:
            voice = validate_voice(voice, kokoro)
        else:
            # Check if we're using stdin (can't do interactive input)
            if input_file in stdin_indicators:
                print("Using stdin - automatically selecting default voice (af_sarah)")
                voice = "af_sarah"  # default voice
            else:
                # Interactive voice selection
                voices = list_available_voices(kokoro)
                print("\nHow to choose a voice:")
                print("You can use either a single voice or blend two voices together.")
                print("\nFor a single voice:")
                print("  • Just enter one number (example: '7')")
                print("\nFor blending two voices:")
                print("  • Enter two numbers separated by comma")
                print("  • Optionally add weights after each number using ':weight'")
                print("\nExamples:")
                print("  • '7'      - Use voice #7 only")
                print("  • '7,11'   - Mix voices #7 and #11 equally (50% each)")
                print("  • '7:60,11:40' - Mix 60% of voice #7 with 40% of voice #11")
                try:
                    voice_input = input("Choose voice(s) by number: ")
                    if ',' in voice_input:
                        # Handle blended voices
                        pairs = []
                        for pair in voice_input.split(','):
                            if ':' in pair:
                                num, weight = pair.strip().split(':')
                                voice_idx = int(num.strip()) - 1
                                if not (0 <= voice_idx < len(voices)):
                                    raise ValueError(f"Invalid voice number: {int(num)}")
                                pairs.append(f"{voices[voice_idx]}:{weight}")
                            else:
                                voice_idx = int(pair.strip()) - 1
                                if not (0 <= voice_idx < len(voices)):
                                    raise ValueError(f"Invalid voice number: {int(pair)}")
                                pairs.append(voices[voice_idx])
                        voice = ','.join(pairs)
                    else:
                        # Single voice
                        voice_choice = int(voice_input) - 1
                        if not (0 <= voice_choice < len(voices)):
                            raise ValueError("Invalid choice")
                        voice = voices[voice_choice]
                    # Validate and potentially convert to blend
                    voice = validate_voice(voice, kokoro)
                except (ValueError, IndexError):
                    print("Invalid choice. Using default voice.")
                    voice = "af_sarah"  # default voice
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading Kokoro model: {e}")
        sys.exit(1)
    
    # Read the input file (handle .txt or .epub)
    if input_file.endswith('.epub'):
        chapters = extract_chapters_from_epub(input_file, debug)
        if not chapters:
            print("No chapters found in EPUB file.")
            sys.exit(1)
            
            print("\nPress Enter to start processing, or Ctrl+C to cancel...")
            input()
            
            if split_output:
                os.makedirs(split_output, exist_ok=True)
                
                # First create all chapter directories and info files
                print("\nCreating chapter directories and info files...")
                for chapter_num, chapter in enumerate(chapters, 1):
                    chapter_dir = os.path.join(split_output, f"chapter_{chapter_num:03d}")
                    os.makedirs(chapter_dir, exist_ok=True)
                    
                    # Write chapter info with more details
                    info_file = os.path.join(chapter_dir, "info.txt")
                    with open(info_file, "w", encoding="utf-8") as f:
                        f.write(f"Title: {chapter['title']}\n")
                        f.write(f"Order: {chapter['order']}\n")
                        f.write(f"Words: {len(chapter['content'].split())}\n")
                        f.write(f"Estimated Duration: {len(chapter['content'].split()) / 150:.1f} minutes\n")
                
                print("Created chapter directories and info files")
                
                # Continue with existing processing code...
    elif input_file.endswith('.pdf'):
        parser = PdfParser(input_file, debug=debug)
        chapters = parser.get_chapters()
    else:
        # Handle stdin specially (cross-platform)
        if input_file in stdin_indicators:
            text = sys.stdin.read()
        else:
            with open(input_file, 'r', encoding='utf-8') as file:
                text = file.read()
        # Treat single text file as one chapter
        chapters = [{'title': 'Chapter 1', 'content': text}]

    if stream:
        import asyncio
        # Stream each chapter
        for chapter in chapters:
            print(f"\nStreaming: {chapter['title']}")
            chunks = chunk_text(chapter['content'], initial_chunk_size=1000)
            asyncio.run(stream_audio(kokoro, chapter['content'], voice, speed, lang, debug))
    else:
        if chapters_output:
            # Chapter-based output: One file per chapter (memory efficient)
            os.makedirs(chapters_output, exist_ok=True)

            for chapter_num, chapter in enumerate(chapters, 1):
                # Create sanitized filename from chapter title
                safe_title = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in chapter['title'])
                safe_title = safe_title[:100]  # Limit length
                chapter_file = os.path.join(chapters_output, f"Chapter_{chapter_num:03d}_{safe_title}.{format}")

                # Skip if chapter file already exists
                if os.path.exists(chapter_file):
                    print(f"\nSkipping {chapter['title']}: Already exists")
                    continue

                print(f"\nProcessing: {chapter['title']}")
                chunks = chunk_text(chapter['content'], initial_chunk_size=1000)
                total_chunks = len(chunks)

                # Use temporary files per chapter to avoid memory accumulation
                import tempfile
                temp_chunk_files = []
                sample_rate = None
                processed_chunks = 0

                for chunk_num, chunk in enumerate(chunks, 1):
                    if stop_audio:  # Check for interruption
                        break

                    # Create progress indicator
                    filled = "■" * processed_chunks
                    remaining = "□" * (total_chunks - processed_chunks)
                    progress_bar = f"[{filled}{remaining}] ({processed_chunks}/{total_chunks})"

                    stop_spinner = False
                    spinner_thread = threading.Thread(
                        target=spinning_wheel,
                        args=(f"Processing chunk {chunk_num}/{total_chunks}", progress_bar)
                    )
                    spinner_thread.start()

                    try:
                        samples, sr = process_chunk_sequential(
                            chunk, kokoro, voice, speed, lang,
                            retry_count=0, debug=debug
                        )
                        if samples is not None:
                            if sample_rate is None:
                                sample_rate = sr

                            # Write chunk to temporary WAV file
                            temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
                            temp_file.close()
                            sf.write(temp_file.name, samples, sr)
                            temp_chunk_files.append(temp_file.name)
                            processed_chunks += 1
                    except Exception as e:
                        print(f"\nError processing chunk {chunk_num}: {e}")

                    stop_spinner = True
                    spinner_thread.join()

                # Merge chunks into chapter file
                if temp_chunk_files and not stop_audio:
                    print(f"\nMerging {len(temp_chunk_files)} chunks into chapter file...")

                    if format == "wav":
                        # Concatenate WAV files directly (memory efficient)
                        with sf.SoundFile(chapter_file, mode='w', samplerate=sample_rate,
                                         channels=1, subtype='PCM_16') as outfile:
                            for temp_file in temp_chunk_files:
                                try:
                                    data, sr = sf.read(temp_file)
                                    outfile.write(data)
                                    os.unlink(temp_file)
                                except Exception as e:
                                    print(f"\nError reading temporary file: {e}")
                                    try:
                                        os.unlink(temp_file)
                                    except:
                                        pass
                    else:
                        # For MP3/M4A, accumulate samples for this chapter only (manageable size)
                        all_samples = []
                        for temp_file in temp_chunk_files:
                            try:
                                data, sr = sf.read(temp_file)
                                all_samples.extend(data)
                                os.unlink(temp_file)
                            except Exception as e:
                                print(f"\nError reading temporary file: {e}")
                                try:
                                    os.unlink(temp_file)
                                except:
                                    pass

                        save_audio_with_format(all_samples, sample_rate, chapter_file, format)

                    print(f"Saved: {chapter_file}")
                elif stop_audio:
                    # Clean up temp files if interrupted
                    for temp_file in temp_chunk_files:
                        try:
                            os.unlink(temp_file)
                        except:
                            pass
                    break

                print(f"\nCompleted {chapter['title']}: {processed_chunks}/{total_chunks} chunks processed")

            if not stop_audio:
                print(f"\nCreated {len(chapters)} chapter files in {chapters_output}/")

                # Combine all chapters into a single audiobook file
                print(f"\nCombining all chapters into single audiobook...")
                chapter_files = sorted([
                    os.path.join(chapters_output, f)
                    for f in os.listdir(chapters_output)
                    if f.startswith("Chapter_") and f.endswith(f".{format}")
                ])

                if chapter_files:
                    # Generate audiobook filename from input file
                    if input_file not in stdin_indicators:
                        book_name = os.path.splitext(os.path.basename(input_file))[0]
                    else:
                        book_name = "audiobook"

                    audiobook_file = os.path.join(chapters_output, f"{book_name}_Complete.{format}")

                    if format == "wav":
                        # Concatenate WAV files directly (memory efficient)
                        print(f"Merging {len(chapter_files)} chapters...")
                        with sf.SoundFile(audiobook_file, mode='w', samplerate=sample_rate,
                                         channels=1, subtype='PCM_16') as outfile:
                            for i, chapter_file in enumerate(chapter_files, 1):
                                try:
                                    data, sr = sf.read(chapter_file)
                                    outfile.write(data)
                                    print(f"  Merged chapter {i}/{len(chapter_files)}", end='\r')
                                except Exception as e:
                                    print(f"\nError reading chapter file {chapter_file}: {e}")
                        print()  # New line after progress
                    else:
                        # For MP3/M4A, use FFmpeg directly to avoid memory issues with large files
                        # pydub's export() creates intermediate WAV files which can exceed 4GB limit
                        import subprocess

                        print(f"Merging {len(chapter_files)} chapters...")

                        # Create a temporary file list for FFmpeg concat demuxer
                        import tempfile
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                            filelist_path = f.name
                            for chapter_file in chapter_files:
                                # FFmpeg concat demuxer requires absolute paths
                                abs_path = os.path.abspath(chapter_file)
                                # Escape single quotes for FFmpeg
                                escaped_path = abs_path.replace("'", "'\\''")
                                f.write(f"file '{escaped_path}'\n")

                        try:
                            print(f"Combining chapters using FFmpeg (memory efficient)...")

                            # Build FFmpeg command for concat
                            if format == 'm4a':
                                # For M4A: concat using concat demuxer, re-encode to AAC
                                ffmpeg_cmd = [
                                    'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                                    '-i', filelist_path,
                                    '-c:a', 'aac', '-b:a', '128k',
                                    audiobook_file
                                ]
                            else:  # mp3
                                # For MP3: concat using concat demuxer, copy codec (no re-encode)
                                ffmpeg_cmd = [
                                    'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                                    '-i', filelist_path,
                                    '-c', 'copy',
                                    audiobook_file
                                ]

                            # Run FFmpeg
                            result = subprocess.run(
                                ffmpeg_cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )

                            if result.returncode != 0:
                                print(f"\nFFmpeg error: {result.stderr}")
                                raise Exception(f"FFmpeg failed with return code {result.returncode}")

                            print(f"Successfully merged {len(chapter_files)} chapters")

                        finally:
                            # Clean up temporary file list
                            if os.path.exists(filelist_path):
                                os.unlink(filelist_path)

                    print(f"\nComplete audiobook saved: {audiobook_file}")

                    # Calculate total duration
                    try:
                        if format == "wav":
                            data, sr = sf.read(audiobook_file)
                            duration_sec = len(data) / sr
                        else:
                            # Use 'mp4' format for m4a files (FFmpeg requirement)
                            load_format = 'mp4' if format == 'm4a' else format
                            audio = AudioSegment.from_file(audiobook_file, format=load_format)
                            duration_sec = len(audio) / 1000.0

                        hours = int(duration_sec // 3600)
                        minutes = int((duration_sec % 3600) // 60)
                        seconds = int(duration_sec % 60)
                        print(f"Total duration: {hours}h {minutes}m {seconds}s")
                    except:
                        pass
        elif split_output:
            os.makedirs(split_output, exist_ok=True)
            
            for chapter_num, chapter in enumerate(chapters, 1):
                chapter_dir = os.path.join(split_output, f"chapter_{chapter_num:03d}")
                
                # Skip if chapter is already fully processed
                if os.path.exists(chapter_dir):
                    info_file = os.path.join(chapter_dir, "info.txt")
                    if os.path.exists(info_file):
                        chunks = chunk_text(chapter['content'], initial_chunk_size=1000)
                        total_chunks = len(chunks)
                        existing_chunks = len([f for f in os.listdir(chapter_dir) 
                                            if f.startswith("chunk_") and f.endswith(f".{format}")])
                        
                        if existing_chunks == total_chunks:
                            print(f"\nSkipping {chapter['title']}: Already completed ({existing_chunks} chunks)")
                            continue
                        else:
                            print(f"\nResuming {chapter['title']}: Found {existing_chunks}/{total_chunks} chunks")

                print(f"\nProcessing: {chapter['title']}")
                os.makedirs(chapter_dir, exist_ok=True)
                
                # Write chapter info if not exists
                info_file = os.path.join(chapter_dir, "info.txt")
                if not os.path.exists(info_file):
                    with open(info_file, "w", encoding="utf-8") as f:
                        f.write(f"Title: {chapter['title']}\n")
                
                chunks = chunk_text(chapter['content'], initial_chunk_size=1000)
                total_chunks = len(chunks)
                processed_chunks = len([f for f in os.listdir(chapter_dir) 
                                     if f.startswith("chunk_") and f.endswith(f".{format}")])
                
                for chunk_num, chunk in enumerate(chunks, 1):
                    if stop_audio:  # Check for interruption
                        break
                    
                    # Skip if chunk file already exists (regardless of position)
                    chunk_file = os.path.join(chapter_dir, f"chunk_{chunk_num:03d}.{format}")
                    if os.path.exists(chunk_file):
                        continue  # Don't increment processed_chunks here since we counted them above
                    
                    # Create progress bar
                    filled = "■" * processed_chunks
                    remaining = "□" * (total_chunks - processed_chunks)
                    progress_bar = f"[{filled}{remaining}] ({processed_chunks}/{total_chunks})"
                    
                    stop_spinner = False
                    spinner_thread = threading.Thread(
                        target=spinning_wheel,
                        args=(f"Processing {chapter['title']}", progress_bar)
                    )
                    spinner_thread.start()
                    
                    try:
                        samples, sample_rate = process_chunk_sequential(
                            chunk, kokoro, voice, speed, lang,
                            retry_count=0, debug=debug  # Add retry parameters
                        )
                        if samples is not None:
                            save_audio_with_format(samples, sample_rate, chunk_file, format)
                            processed_chunks += 1
                    except Exception as e:
                        print(f"\nError processing chunk {chunk_num}: {e}")
                    
                    stop_spinner = True
                    spinner_thread.join()
                    
                    if stop_audio:  # Check for interruption
                        break
                
                print(f"\nCompleted {chapter['title']}: {processed_chunks}/{total_chunks} chunks processed")
                
                if stop_audio:  # Check for interruption
                    break
            
            print(f"\nCreated audio files for {len(chapters)} chapters in {split_output}/")
        else:
            # Combine all chapters into one file
            # Use temporary files to avoid memory accumulation
            import tempfile
            temp_chunk_files = []
            sample_rate = None

            for chapter_num, chapter in enumerate(chapters, 1):
                print(f"\nProcessing: {chapter['title']}")
                chunks = chunk_text(chapter['content'], initial_chunk_size=1000)
                processed_chunks = 0
                total_chunks = len(chunks)

                for chunk_num, chunk in enumerate(chunks, 1):
                    if stop_audio:  # Check for interruption
                        break

                    stop_spinner = False
                    spinner_thread = threading.Thread(
                        target=spinning_wheel,
                        args=(f"Processing chunk {chunk_num}/{total_chunks}",)
                    )
                    spinner_thread.start()

                    try:
                        samples, sr = process_chunk_sequential(
                            chunk, kokoro, voice, speed, lang,
                            retry_count=0, debug=debug  # Add retry parameters
                        )
                        if samples is not None:
                            if sample_rate is None:
                                sample_rate = sr

                            # Write chunk to temporary WAV file to avoid memory accumulation
                            temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
                            temp_file.close()
                            sf.write(temp_file.name, samples, sr)
                            temp_chunk_files.append(temp_file.name)
                            processed_chunks += 1
                    except Exception as e:
                        print(f"\nError processing chunk {chunk_num}: {e}")

                    stop_spinner = True
                    spinner_thread.join()

                print(f"\nCompleted {chapter['title']}: {processed_chunks}/{total_chunks} chunks processed")

            if temp_chunk_files:
                print("\nMerging audio chunks...")
                if not output_file:
                    output_file = f"{os.path.splitext(input_file)[0]}.{format}"

                # For WAV output, we can concatenate efficiently
                # For other formats, we need to accumulate and convert
                if format == "wav":
                    # Concatenate WAV files directly using soundfile
                    # This is memory efficient as we write incrementally
                    with sf.SoundFile(output_file, mode='w', samplerate=sample_rate,
                                     channels=1, subtype='PCM_16') as outfile:
                        for i, temp_file in enumerate(temp_chunk_files):
                            try:
                                data, sr = sf.read(temp_file)
                                outfile.write(data)

                                # Clean up temp file immediately after reading
                                os.unlink(temp_file)

                                # Show progress
                                if (i + 1) % 10 == 0 or i == len(temp_chunk_files) - 1:
                                    print(f"Merged {i + 1}/{len(temp_chunk_files)} chunks...", end='\r')
                            except Exception as e:
                                print(f"\nError reading temporary file {temp_file}: {e}")
                                try:
                                    os.unlink(temp_file)
                                except:
                                    pass
                else:
                    # For MP3/M4A, need to accumulate all samples for format conversion
                    all_samples = []
                    for i, temp_file in enumerate(temp_chunk_files):
                        try:
                            data, sr = sf.read(temp_file)
                            all_samples.extend(data)

                            # Clean up temp file immediately after reading
                            os.unlink(temp_file)

                            # Show progress
                            if (i + 1) % 10 == 0 or i == len(temp_chunk_files) - 1:
                                print(f"Merged {i + 1}/{len(temp_chunk_files)} chunks...", end='\r')
                        except Exception as e:
                            print(f"\nError reading temporary file {temp_file}: {e}")
                            try:
                                os.unlink(temp_file)
                            except:
                                pass

                    print()  # New line after progress
                    print("\nSaving complete audio file...")
                    save_audio_with_format(all_samples, sample_rate, output_file, format)

                print()  # New line after progress
                print(f"Created {output_file}")

async def stream_audio(kokoro, text, voice, speed, lang, debug=False):
    global stop_spinner, stop_audio
    stop_spinner = False
    stop_audio = False
    
    print("Starting audio stream...")
    chunks = chunk_text(text, initial_chunk_size=1000)
    
    for i, chunk in enumerate(chunks, 1):
        if stop_audio:
            break
        # Update progress percentage
        progress = int((i / len(chunks)) * 100)
        spinner_thread = threading.Thread(
            target=spinning_wheel, 
            args=(f"Streaming chunk {i}/{len(chunks)}",)
        )
        spinner_thread.start()
        
        async for samples, sample_rate in kokoro.create_stream(
            chunk, voice=voice, speed=speed, lang=lang
        ):
            if stop_audio:
                break
            if debug:
                print(f"\nDEBUG: Playing chunk of {len(samples)} samples")
            sd.play(samples, sample_rate)
            sd.wait()
        
        stop_spinner = True
        spinner_thread.join()
        stop_spinner = False
    
    print("\nStreaming completed.")

def handle_ctrl_c(signum, frame):
    global stop_spinner, stop_audio
    print("\nCtrl+C detected, stopping...")
    stop_spinner = True
    stop_audio = True
    sys.exit(0)

# Register the signal handler for SIGINT (Ctrl+C)
signal.signal(signal.SIGINT, handle_ctrl_c)

def merge_chunks_to_chapters(split_output_dir, format="wav"):
    """Merge audio chunks into complete chapter files."""
    global stop_spinner

    if not os.path.exists(split_output_dir):
        print(f"Error: Directory {split_output_dir} does not exist.")
        return

    # Find all chapter directories
    chapter_dirs = sorted([d for d in os.listdir(split_output_dir) 
                          if d.startswith("chapter_") and os.path.isdir(os.path.join(split_output_dir, d))])

    if not chapter_dirs:
        print(f"No chapter directories found in {split_output_dir}")
        return

    # Track used titles to handle duplicates
    used_titles = set()

    for chapter_dir in chapter_dirs:
        chapter_path = os.path.join(split_output_dir, chapter_dir)
        chunk_files = sorted([f for f in os.listdir(chapter_path) 
                            if f.startswith("chunk_") and f.endswith(f".{format}")])
        
        if not chunk_files:
            print(f"No chunks found in {chapter_dir}")
            continue

        # Read chapter title from info.txt if available
        chapter_title = chapter_dir
        info_file = os.path.join(chapter_path, "info.txt")
        if os.path.exists(info_file):
            with open(info_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith("Title:"):
                        chapter_title = line.replace("Title:", "").strip()
                        break

        # Clean title for filesystem use
        safe_title = "".join(c for c in chapter_title if c.isalnum() or c in (' ', '-', '_')).strip()
        
        # Handle duplicate or empty titles
        if not safe_title or safe_title in used_titles:
            merged_file = os.path.join(split_output_dir, f"{chapter_dir}.{format}")
        else:
            merged_file = os.path.join(split_output_dir, f"{safe_title}.{format}")
            used_titles.add(safe_title)

        print(f"\nMerging chunks for {chapter_title}")
        
        # Initialize variables for merging
        all_samples = []
        sample_rate = None
        total_duration = 0
        
        # Create progress spinner
        total_chunks = len(chunk_files)
        processed_chunks = 0
        
        for chunk_file in chunk_files:
            chunk_path = os.path.join(chapter_path, chunk_file)
            
            # Display progress
            print(f"\rProcessing chunk {processed_chunks + 1}/{total_chunks}", end="")
            
            try:
                # Read audio data
                data, sr = sf.read(chunk_path)
                
                # Verify the audio data
                if len(data) == 0:
                    print(f"\nWarning: Empty audio data in {chunk_file}")
                    continue
                
                # Initialize sample rate or verify it matches
                if sample_rate is None:
                    sample_rate = sr
                elif sr != sample_rate:
                    print(f"\nWarning: Sample rate mismatch in {chunk_file}")
                    continue
                
                # Add chunk duration to total
                chunk_duration = len(data) / sr
                total_duration += chunk_duration
                
                # Append the audio data
                all_samples.extend(data)
                processed_chunks += 1
                
            except Exception as e:
                print(f"\nError processing {chunk_file}: {e}")
        
        print()  # New line after progress
        
        if all_samples:
            print(f"Saving merged chapter to {merged_file}")
            print(f"Total duration: {total_duration:.2f} seconds")
            
            try:
                # Ensure all_samples is a numpy array
                all_samples = np.array(all_samples)

                # Save merged audio
                save_audio_with_format(all_samples, sample_rate, merged_file, format)
                print(f"Successfully merged {processed_chunks}/{total_chunks} chunks")
                
                # Verify the output file
                if os.path.exists(merged_file):
                    output_data, output_sr = sf.read(merged_file)
                    output_duration = len(output_data) / output_sr
                    print(f"Verified output file: {output_duration:.2f} seconds")
                else:
                    print("Warning: Output file was not created")
                
            except Exception as e:
                print(f"Error saving merged file: {e}")
        else:
            print("No valid audio data to merge")

def get_valid_options():
    """Return a set of valid command line options"""
    return {
        '-h', '--help',
        '--help-languages',
        '--help-voices',
        '--merge-chunks',
        '--stream',
        '--speed',
        '--lang',
        '--voice',
        '--split-output',
        '--chapters',
        '--format',
        '--gpu',
        '--debug',
        '--model',
        '--voices',
        # Audiobook options
        '--audiobook',
        '--select-chapters',
        '--keep-temp',
        '--temp-dir',
        '--no-metadata',
        '--no-chapters',
        '--cover',
        '--title',
        '--author',
        '--narrator',
        '--year',
        '--genre',
        '--description'
    }




def main():
    """Main entry point for the kokoro-tts CLI tool."""
    # Define stdin indicators once (cross-platform)
    stdin_indicators = ['/dev/stdin', '-', 'CONIN$']  # CONIN$ is Windows stdin
    
    # Validate command line arguments
    valid_options = get_valid_options()
    
    # Check for unknown options
    unknown_options = []
    i = 0
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg.startswith('--') and arg not in valid_options:
            unknown_options.append(arg)
            # Skip the next argument if it's a value for an option that takes parameters
        elif arg in {'--speed', '--lang', '--voice', '--split-output', '--chapters', '--format', '--model', '--voices',
                     '--audiobook', '--select-chapters', '--temp-dir', '--cover', '--title', '--author',
                     '--narrator', '--year', '--genre', '--description'}:
            i += 1
        i += 1
    
    # If unknown options were found, show error and help
    if unknown_options:
        print("Error: Unknown option(s):", ", ".join(unknown_options))
        print("\nDid you mean one of these?")
        for unknown in unknown_options:
            # Find similar valid options using string similarity
            similar = difflib.get_close_matches(unknown, valid_options, n=3, cutoff=0.4)
            if similar:
                print(f"  {unknown} -> {', '.join(similar)}")
        print("\n")  # Add extra newline for spacing
        print_usage()  # Show the full help text
        sys.exit(1)
    
    # Handle help commands first (before argument parsing)
    if '--help' in sys.argv or '-h' in sys.argv:
        print_usage()
        sys.exit(0)
    elif '--help-languages' in sys.argv:
        # For help commands, we need to parse model/voices paths first
        model_path = "kokoro-v1.0.onnx"  # default model path
        voices_path = "voices-v1.0.bin"  # default voices path
        
        # Parse model/voices paths for help commands
        for i, arg in enumerate(sys.argv):
            if arg == '--model' and i + 1 < len(sys.argv):
                model_path = sys.argv[i + 1]
            elif arg == '--voices' and i + 1 < len(sys.argv):
                voices_path = sys.argv[i + 1]
        
        print_supported_languages(model_path, voices_path)
        sys.exit(0)
    elif '--help-voices' in sys.argv:
        # For help commands, we need to parse model/voices paths first
        model_path = "kokoro-v1.0.onnx"  # default model path
        voices_path = "voices-v1.0.bin"  # default voices path
        
        # Parse model/voices paths for help commands
        for i, arg in enumerate(sys.argv):
            if arg == '--model' and i + 1 < len(sys.argv):
                model_path = sys.argv[i + 1]
            elif arg == '--voices' and i + 1 < len(sys.argv):
                voices_path = sys.argv[i + 1]
        
        print_supported_voices(model_path, voices_path)
        sys.exit(0)
    
    # Parse arguments
    input_file = None
    if len(sys.argv) > 1 and not sys.argv[1].startswith('--'):
        input_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else None
    else:
        output_file = None

    stream = '--stream' in sys.argv
    speed = 1.0  # default speed
    lang = "en-us"  # default language
    voice = None  # default to interactive selection
    split_output = None
    chapters_output = None
    format = "wav"  # default format
    use_gpu = '--gpu' in sys.argv
    merge_chunks = '--merge-chunks' in sys.argv
    model_path = "kokoro-v1.0.onnx"  # default model path
    voices_path = "voices-v1.0.bin"  # default voices path

    # Audiobook options
    audiobook_output = None
    select_chapters = "all"
    keep_temp = '--keep-temp' in sys.argv
    temp_dir = None
    no_metadata = '--no-metadata' in sys.argv
    no_chapters_markers = '--no-chapters' in sys.argv
    cover_path = None
    title_override = None
    author_override = None
    narrator_override = None
    year_override = None
    genre_override = None
    description_override = None

    # Parse optional arguments
    for i, arg in enumerate(sys.argv):
        if arg == '--speed' and i + 1 < len(sys.argv):
            try:
                speed = float(sys.argv[i + 1])
            except ValueError:
                print("Error: Speed must be a number")
                sys.exit(1)
        elif arg == '--lang' and i + 1 < len(sys.argv):
            lang = sys.argv[i + 1]
        elif arg == '--voice' and i + 1 < len(sys.argv):
            voice = sys.argv[i + 1]
        elif arg == '--split-output' and i + 1 < len(sys.argv):
            split_output = sys.argv[i + 1]
        elif arg == '--chapters' and i + 1 < len(sys.argv):
            chapters_output = sys.argv[i + 1]
        elif arg == '--format' and i + 1 < len(sys.argv):
            format = sys.argv[i + 1].lower()
            if format not in ['wav', 'mp3', 'm4a']:
                print("Error: Format must be either 'wav', 'mp3', or 'm4a'")
                sys.exit(1)
        elif arg == '--model' and i + 1 < len(sys.argv):
            model_path = sys.argv[i + 1]
        elif arg == '--voices' and i + 1 < len(sys.argv):
            voices_path = sys.argv[i + 1]
        # Audiobook options
        elif arg == '--audiobook' and i + 1 < len(sys.argv):
            audiobook_output = sys.argv[i + 1]
        elif arg == '--select-chapters' and i + 1 < len(sys.argv):
            select_chapters = sys.argv[i + 1]
        elif arg == '--temp-dir' and i + 1 < len(sys.argv):
            temp_dir = sys.argv[i + 1]
        elif arg == '--cover' and i + 1 < len(sys.argv):
            cover_path = sys.argv[i + 1]
        elif arg == '--title' and i + 1 < len(sys.argv):
            title_override = sys.argv[i + 1]
        elif arg == '--author' and i + 1 < len(sys.argv):
            author_override = sys.argv[i + 1]
        elif arg == '--narrator' and i + 1 < len(sys.argv):
            narrator_override = sys.argv[i + 1]
        elif arg == '--year' and i + 1 < len(sys.argv):
            year_override = sys.argv[i + 1]
        elif arg == '--genre' and i + 1 < len(sys.argv):
            genre_override = sys.argv[i + 1]
        elif arg == '--description' and i + 1 < len(sys.argv):
            description_override = sys.argv[i + 1]
    
    # Validate mutually exclusive options
    if split_output and chapters_output:
        print("Error: Cannot use both --split-output and --chapters at the same time")
        print("  --split-output: Creates many small chunk files")
        print("  --chapters: Creates one file per chapter (recommended)")
        sys.exit(1)

    # Validate audiobook options
    if audiobook_output:
        # Audiobook requires EPUB or PDF input
        if not input_file or input_file in stdin_indicators:
            print("Error: --audiobook requires EPUB or PDF input file")
            sys.exit(1)

        if not (input_file.endswith('.epub') or input_file.endswith('.pdf')):
            print("Error: --audiobook requires EPUB or PDF input file")
            print(f"  Got: {input_file}")
            sys.exit(1)

        # Audiobook is mutually exclusive with --chapters
        if chapters_output:
            print("Error: --audiobook and --chapters are mutually exclusive")
            print("  --audiobook already creates chapter-based output with metadata")
            sys.exit(1)

        # Audiobook is mutually exclusive with --split-output
        if split_output:
            print("Error: --audiobook and --split-output are mutually exclusive")
            sys.exit(1)

        # Force M4A format for audiobook
        format = 'm4a'

        # Validate output has .m4a extension
        if not audiobook_output.endswith('.m4a'):
            print("Error: --audiobook output must have .m4a extension")
            print(f"  Got: {audiobook_output}")
            sys.exit(1)

        # Check if output file exists and prompt for overwrite
        if os.path.exists(audiobook_output):
            try:
                response = input(f"Output file '{audiobook_output}' already exists. Overwrite? [y/N]: ")
                if response.lower() not in ['y', 'yes']:
                    print("Aborted.")
                    sys.exit(0)
            except (EOFError, KeyboardInterrupt):
                print("\nAborted.")
                sys.exit(0)

    # Handle merge chunks operation
    if merge_chunks:
        if not split_output:
            print("Error: --split-output directory must be specified when using --merge-chunks")
            sys.exit(1)
        merge_chunks_to_chapters(split_output, format)
        sys.exit(0)

    # Normal processing mode
    if not input_file:
        print("Error: Input file required for text-to-speech conversion")
        print_usage()
        sys.exit(1)

    # Ensure the input file exists (skip check for stdin)
    if input_file not in stdin_indicators and not os.access(input_file, os.R_OK):
        print(f"Error: Cannot read from {input_file}. File may not exist or you may not have permission to read it.")
        sys.exit(1)
    
    # Ensure the output file has a proper extension if specified
    if output_file and not output_file.endswith(('.' + format)):
        print(f"Error: Output file must have .{format} extension.")
        sys.exit(1)
    
    # Add debug flag
    debug = '--debug' in sys.argv

    # Handle audiobook creation workflow
    if audiobook_output:
        global stop_spinner, stop_audio

        from kokoro_tts.audiobook import AudiobookCreator, parse_chapter_selection
        from kokoro_tts.core import AudiobookOptions

        # Create audiobook options
        audiobook_opts = AudiobookOptions(
            select_chapters=select_chapters,
            keep_temp=keep_temp,
            temp_dir=temp_dir,
            no_metadata=no_metadata,
            no_chapters=no_chapters_markers,
            cover_path=cover_path,
            title=title_override,
            author=author_override,
            narrator=narrator_override,
            year=year_override,
            genre=genre_override,
            description=description_override
        )

        # Import the chapter processing workflow from this module
        # (We'll use convert_text_to_audio in a special way for audiobook)
        print(f"Creating audiobook: {audiobook_output}\n")

        # Use AudiobookCreator context manager
        with AudiobookCreator(input_file, audiobook_opts) as creator:
            # Extract metadata
            metadata = creator.extract_metadata()

            # Extract chapters from file
            if input_file.endswith('.epub'):
                all_chapters = extract_chapters_from_epub(input_file, debug, skip_confirmation=True)
            else:  # PDF
                parser = PdfParser(input_file, debug=debug, skip_confirmation=True)
                all_chapters = parser.get_chapters()

            if not all_chapters:
                print("Error: No chapters found in input file")
                sys.exit(1)

            # Select chapters
            from kokoro_tts.core import Chapter
            chapter_objects = [
                Chapter(title=ch['title'], content=ch['content'], order=ch['order'])
                for ch in all_chapters
            ]
            selected_chapters = creator.select_chapters_from_list(chapter_objects)

            # Get temp directory for chapter processing
            temp_chapters_dir = creator.get_temp_dir()

            print(f"[3/7] Generating audio for {len(selected_chapters)} chapters...\n")

            # Use existing chapter processing by setting chapters_output to temp dir
            # We need to process chapters manually to maintain control
            from kokoro_onnx import Kokoro

            # Setup GPU if requested
            gpu_info = check_gpu_availability(use_gpu=use_gpu)

            # Auto-enable CoreML on macOS if available and no provider is set (unless user explicitly requested GPU)
            auto_enabled = False
            if not use_gpu and gpu_info['has_coreml'] and not gpu_info['env_provider']:
                os.environ['ONNX_PROVIDER'] = 'CoreMLExecutionProvider'
                gpu_info['selected_provider'] = 'CoreMLExecutionProvider'
                auto_enabled = True

            # If GPU was requested or auto-selected, set the environment variable
            if gpu_info.get('selected_provider') and not gpu_info.get('env_provider'):
                os.environ['ONNX_PROVIDER'] = gpu_info['selected_provider']

            print_gpu_info(gpu_info, auto_enabled, requested_gpu=use_gpu)
            print()  # Blank line for readability

            # Exit with error if --gpu was requested but no provider is available
            if use_gpu and not gpu_info.get('selected_provider'):
                print("\nError: Cannot enable GPU acceleration. No compatible GPU provider found.")
                sys.exit(1)

            # Load model
            print("Loading Kokoro model...")
            kokoro = Kokoro(model_path, voices_path)

            # Validate/select voice
            if voice is None:
                # Interactive voice selection - use default
                print("No voice specified, using default voice (af_sarah)")
                voice = "af_sarah"
            else:
                # Validate the voice
                voice = validate_voice(voice, kokoro)

            # Process each selected chapter
            chapter_files = []
            chapter_titles = []

            for chapter_idx, chapter in enumerate(selected_chapters, 1):
                chapter_title = chapter.title
                chapter_content = chapter.content
                chapter_titles.append(chapter_title)

                # Create chapter filename (sanitize title)
                safe_title = "".join(c for c in chapter_title if c.isalnum() or c in (' ', '-', '_')).strip()
                safe_title = safe_title[:50]  # Limit length
                chapter_filename = f"Chapter_{chapter_idx:03d}_{safe_title}.m4a"
                chapter_file = os.path.join(temp_chapters_dir, chapter_filename)
                chapter_files.append(chapter_file)

                print(f"\nChapter {chapter_idx}/{len(selected_chapters)}: {chapter_title}")

                # Process chapter using existing logic
                chunks = chunk_text(chapter_content, initial_chunk_size=1000)
                total_chunks = len(chunks)

                if debug:
                    print(f"  DEBUG: Chapter has {total_chunks} chunks")
                    print(f"  DEBUG: Chapter content length: {len(chapter_content)} chars")

                if total_chunks == 0:
                    print(f"  Warning: Chapter '{chapter_title}' has no content, skipping")
                    continue

                all_samples = []
                sample_rate = None

                for chunk_num, chunk in enumerate(chunks, 1):
                    if stop_audio:
                        break

                    if debug:
                        print(f"\n  DEBUG: Processing chunk {chunk_num}/{total_chunks}")
                        print(f"  DEBUG: Chunk length: {len(chunk)} chars")
                        print(f"  DEBUG: Voice: {voice}")
                        print(f"  DEBUG: Lang: {lang}")

                    # Progress indicator
                    filled = "■" * (chunk_num - 1)
                    remaining = "□" * (total_chunks - chunk_num + 1)
                    progress_bar = f"[{filled}{remaining}] ({chunk_num}/{total_chunks})"

                    stop_spinner = False
                    spinner_thread = threading.Thread(
                        target=spinning_wheel,
                        args=(f"Processing chunk {chunk_num}/{total_chunks}", progress_bar)
                    )
                    spinner_thread.start()

                    try:
                        samples, sr = process_chunk_sequential(
                            chunk, kokoro, voice, speed, lang,
                            retry_count=0, debug=debug
                        )

                        if samples is not None:
                            all_samples.extend(samples)
                            if sample_rate is None:
                                sample_rate = sr
                    except Exception as e:
                        print(f"\nError processing chunk {chunk_num}: {e}")
                        if debug:
                            import traceback
                            traceback.print_exc()

                    stop_spinner = True
                    spinner_thread.join()

                    # Debug output after spinner stops to avoid stdout conflicts
                    if debug and samples is not None:
                        print(f"  DEBUG: Chunk {chunk_num} completed: {len(samples)} samples at {sr} Hz")

                if stop_audio:
                    print("\nAudiobook creation interrupted")
                    sys.exit(1)

                # Save chapter file
                if all_samples:
                    save_audio_with_format(all_samples, sample_rate, chapter_file, 'm4a')
                    print(f"\n✓ Saved: {chapter_filename}")
                else:
                    print(f"\nWarning: No audio generated for chapter {chapter_idx}")

            if stop_audio:
                sys.exit(1)

            # Merge chapter files into single audiobook
            print(f"\n[4/7] Merging {len(chapter_files)} chapters...")

            # Create temp merged file (without metadata)
            temp_merged = os.path.join(temp_chapters_dir, "_temp_merged.m4a")

            # Use FFmpeg to concatenate
            import subprocess
            import tempfile

            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                filelist_path = f.name
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
                    print(f"FFmpeg error: {result.stderr}")
                    raise Exception(f"FFmpeg failed with return code {result.returncode}")

                print("✓ Chapters merged")
            finally:
                if os.path.exists(filelist_path):
                    os.unlink(filelist_path)

            # Embed metadata and chapters
            if not no_metadata:
                print("\n[5/7] Embedding metadata and chapter markers...")

                # Calculate chapter timings
                from kokoro_tts.audiobook import calculate_chapter_timings, embed_audiobook_metadata

                chapters_info = calculate_chapter_timings(chapter_files, chapter_titles)

                # Add narrator if not specified
                if not metadata.get('narrator') and voice:
                    metadata['narrator'] = voice

                # Skip chapter markers if requested
                if no_chapters_markers:
                    chapters_info = []

                # Embed metadata
                try:
                    embed_audiobook_metadata(
                        temp_merged,
                        audiobook_output,
                        metadata,
                        metadata.get('cover'),
                        chapters_info
                    )
                    print("✓ Metadata embedded")
                    if not no_chapters_markers and chapters_info:
                        print(f"✓ {len(chapters_info)} chapter markers added")
                except Exception as e:
                    print(f"Warning: Could not embed metadata: {e}")
                    print("Copying file without metadata...")
                    shutil.copy(temp_merged, audiobook_output)
            else:
                print("\n[5/7] Skipping metadata embedding (--no-metadata)...")
                shutil.copy(temp_merged, audiobook_output)

            # Calculate final file info
            print("\n" + "━" * 50)
            print(f"✓ Audiobook created: {audiobook_output}")

            try:
                file_size = os.path.getsize(audiobook_output) / (1024 * 1024)  # MB
                print(f"  Size: {file_size:.1f} MB")

                # Get duration
                from pydub import AudioSegment
                audio = AudioSegment.from_file(audiobook_output, format='mp4')
                duration_sec = len(audio) / 1000.0
                hours = int(duration_sec // 3600)
                minutes = int((duration_sec % 3600) // 60)
                seconds = int(duration_sec % 60)
                print(f"  Duration: {hours}h {minutes}m {seconds}s")
                print(f"  Chapters: {len(selected_chapters)}")
            except:
                pass

            print("━" * 50)

        # Exit after audiobook creation
        sys.exit(0)

    # Convert text to audio with debug flag
    convert_text_to_audio(input_file, output_file, voice=voice, stream=stream,
                         speed=speed, lang=lang, split_output=split_output,
                         chapters_output=chapters_output,
                         format=format, debug=debug, stdin_indicators=stdin_indicators,
                         model_path=model_path, voices_path=voices_path, use_gpu=use_gpu)


if __name__ == '__main__':
    main()

