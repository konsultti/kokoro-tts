"""Audiobook creation functionality for Kokoro TTS.

This module provides tools for creating professional M4A audiobooks with
embedded metadata, cover art, and chapter markers.
"""

# Standard library imports
import os
import sys
import shutil
import tempfile
import subprocess
from datetime import datetime
from typing import Optional, List, Dict, Tuple

# Third-party imports
import fitz  # PyMuPDF
from ebooklib import epub, ITEM_DOCUMENT, ITEM_COVER
from pydub import AudioSegment

# Local imports
from kokoro_tts.core import Chapter, ProcessingOptions, AudiobookOptions


def parse_chapter_selection(selection: str, total_chapters: int) -> List[int]:
    """Parse chapter selection string into list of indices.

    Args:
        selection: Selection string (e.g., "all", "1,3,5", "1-5", "1-3,7,10-12")
        total_chapters: Total number of chapters available

    Returns:
        List of chapter indices (0-based)

    Raises:
        ValueError: If selection format is invalid

    Examples:
        >>> parse_chapter_selection("all", 10)
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        >>> parse_chapter_selection("1,3,5", 10)
        [0, 2, 4]
        >>> parse_chapter_selection("1-3", 10)
        [0, 1, 2]
        >>> parse_chapter_selection("1-3,7,10-12", 15)
        [0, 1, 2, 6, 9, 10, 11]
    """
    # Handle special cases
    if selection in ["all", "*"]:
        return list(range(total_chapters))

    if selection in ["-1", "last"]:
        return [total_chapters - 1]

    # Parse comma-separated parts
    indices = []
    try:
        for part in selection.split(','):
            part = part.strip()
            if '-' in part:
                # Handle range (e.g., "1-5")
                start_str, end_str = part.split('-', 1)
                start = int(start_str.strip())
                end = int(end_str.strip())

                if start < 1 or end > total_chapters:
                    raise ValueError(
                        f"Range {start}-{end} out of bounds (1-{total_chapters})"
                    )
                if start > end:
                    raise ValueError(f"Invalid range: {start}-{end} (start > end)")

                # Convert to 0-based and add to list
                indices.extend(range(start - 1, end))
            else:
                # Handle single chapter
                chapter_num = int(part)
                if chapter_num < 1 or chapter_num > total_chapters:
                    raise ValueError(
                        f"Chapter {chapter_num} out of bounds (1-{total_chapters})"
                    )
                indices.append(chapter_num - 1)  # Convert to 0-based
    except ValueError as e:
        if "invalid literal" in str(e):
            raise ValueError(f"Invalid chapter selection format: '{selection}'")
        raise

    # Remove duplicates and sort
    indices = sorted(set(indices))

    if not indices:
        raise ValueError("Chapter selection resulted in empty list")

    return indices


def extract_epub_metadata(epub_path: str) -> Dict[str, any]:
    """Extract metadata and cover from EPUB file.

    Args:
        epub_path: Path to EPUB file

    Returns:
        Dictionary with metadata fields and cover bytes
    """
    book = epub.read_epub(epub_path)

    metadata = {
        'title': None,
        'author': None,
        'language': None,
        'date': None,
        'description': None,
        'publisher': None,
        'rights': None,
        'cover': None  # bytes of cover image
    }

    # Extract text metadata
    for key, value in book.metadata.items():
        if not value:
            continue

        # Extract first value from list of tuples
        text_value = value[0][0] if isinstance(value, list) and value else None

        if 'title' in key.lower():
            metadata['title'] = text_value
        elif 'creator' in key.lower():
            metadata['author'] = text_value
        elif 'language' in key.lower():
            metadata['language'] = text_value
        elif 'date' in key.lower():
            metadata['date'] = text_value
        elif 'description' in key.lower():
            metadata['description'] = text_value
        elif 'publisher' in key.lower():
            metadata['publisher'] = text_value
        elif 'rights' in key.lower():
            metadata['rights'] = text_value

    # Extract cover image
    for item in book.get_items():
        item_type = item.get_type()
        item_name = item.get_name().lower()

        if item_type == ITEM_COVER or 'cover' in item_name:
            cover_data = item.get_content()
            # Validate that it's a real image format (PNG/JPEG), not SVG/XML
            if cover_data and len(cover_data) > 8:
                # Check magic bytes for common image formats
                is_png = cover_data[:8] == b'\x89PNG\r\n\x1a\n'
                is_jpeg = cover_data[:3] == b'\xff\xd8\xff'
                is_webp = cover_data[:4] == b'RIFF' and cover_data[8:12] == b'WEBP'

                if is_png or is_jpeg or is_webp:
                    metadata['cover'] = cover_data
                    break

    return metadata


def extract_pdf_metadata(pdf_path: str) -> Dict[str, any]:
    """Extract metadata and cover from PDF file.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Dictionary with metadata fields and cover bytes
    """
    doc = fitz.open(pdf_path)

    pdf_metadata = doc.metadata or {}

    metadata = {
        'title': pdf_metadata.get('title'),
        'author': pdf_metadata.get('author'),
        'subject': pdf_metadata.get('subject'),
        'keywords': pdf_metadata.get('keywords'),
        'creator': pdf_metadata.get('creator'),
        'producer': pdf_metadata.get('producer'),
        'creationDate': pdf_metadata.get('creationDate'),
        'modDate': pdf_metadata.get('modDate'),
        'description': pdf_metadata.get('subject'),  # Use subject as description
        'cover': None
    }

    # Extract first page as cover (render to PNG)
    try:
        if len(doc) > 0:
            page = doc[0]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x scaling for quality
            metadata['cover'] = pix.tobytes("png")
    except Exception as e:
        print(f"Warning: Could not extract PDF cover: {e}")

    doc.close()
    return metadata


def calculate_chapter_timings(chapter_files: List[str], chapter_titles: List[str]) -> List[Dict]:
    """Calculate start/end times for each chapter.

    Args:
        chapter_files: List of M4A chapter file paths in order
        chapter_titles: List of chapter titles corresponding to files

    Returns:
        List of {'title': str, 'start_time': float, 'end_time': float}
    """
    chapters_info = []
    current_time = 0.0

    for i, chapter_file in enumerate(chapter_files):
        try:
            # Load audio to get duration
            audio = AudioSegment.from_file(chapter_file, format='mp4')
            duration = len(audio) / 1000.0  # Convert ms to seconds

            title = chapter_titles[i] if i < len(chapter_titles) else f"Chapter {i+1}"

            chapters_info.append({
                'title': title,
                'start_time': current_time,
                'end_time': current_time + duration
            })

            current_time += duration
        except Exception as e:
            print(f"Warning: Could not calculate timing for {chapter_file}: {e}")
            continue

    return chapters_info


def embed_audiobook_metadata(
    input_m4a: str,
    output_m4a: str,
    metadata: Dict[str, any],
    cover_bytes: Optional[bytes],
    chapters: List[Dict]
):
    """Embed metadata, cover art, and chapter markers into M4A file.

    Args:
        input_m4a: Path to input M4A file (without metadata)
        output_m4a: Path to output M4A file (with metadata)
        metadata: Dict with title, author, narrator, year, genre, description
        cover_bytes: Cover image data (PNG/JPEG)
        chapters: List of {'title': str, 'start_time': float, 'end_time': float}

    Raises:
        Exception: If FFmpeg fails
    """
    # Create temp metadata file
    with tempfile.NamedTemporaryFile(
        suffix='.txt', delete=False, mode='w', encoding='utf-8'
    ) as metadata_file:
        metadata_path = metadata_file.name
        metadata_file.write(";FFMETADATA1\n")

        # Write global metadata
        if metadata.get('title'):
            # Escape special characters for FFmpeg metadata
            title = str(metadata['title']).replace('=', '\\=').replace(';', '\\;')
            metadata_file.write(f"title={title}\n")

        if metadata.get('author'):
            author = str(metadata['author']).replace('=', '\\=').replace(';', '\\;')
            metadata_file.write(f"artist={author}\n")
            metadata_file.write(f"album_artist={author}\n")

        if metadata.get('narrator'):
            narrator = str(metadata['narrator']).replace('=', '\\=').replace(';', '\\;')
            metadata_file.write(f"composer={narrator}\n")

        if metadata.get('year'):
            metadata_file.write(f"date={metadata['year']}\n")

        if metadata.get('genre'):
            genre = str(metadata['genre']).replace('=', '\\=').replace(';', '\\;')
            metadata_file.write(f"genre={genre}\n")

        if metadata.get('description'):
            desc = str(metadata['description']).replace('=', '\\=').replace(';', '\\;')
            metadata_file.write(f"comment={desc}\n")

        # Write chapter markers
        for chapter in chapters:
            start_ms = int(chapter['start_time'] * 1000)
            end_ms = int(chapter['end_time'] * 1000)
            title = str(chapter['title']).replace('=', '\\=').replace(';', '\\;')

            metadata_file.write("\n[CHAPTER]\n")
            metadata_file.write("TIMEBASE=1/1000\n")
            metadata_file.write(f"START={start_ms}\n")
            metadata_file.write(f"END={end_ms}\n")
            metadata_file.write(f"title={title}\n")

    # Prepare FFmpeg command
    ffmpeg_cmd = [
        'ffmpeg', '-y',
        '-i', input_m4a,  # Input M4A
        '-i', metadata_path,  # Metadata file
    ]

    # Add cover art if available
    cover_path = None
    if cover_bytes:
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as cover_file:
            cover_path = cover_file.name
            cover_file.write(cover_bytes)
        ffmpeg_cmd.extend(['-i', cover_path])

    # Mapping and encoding options
    ffmpeg_cmd.extend([
        '-map', '0:a',  # Map audio from first input
        '-map_metadata', '1',  # Map metadata from metadata file
    ])

    if cover_path:
        ffmpeg_cmd.extend([
            '-map', '2:v',  # Map cover art from third input
            '-c:v', 'png',  # Encode cover as PNG
            '-disposition:v:0', 'attached_pic',  # Mark as cover
        ])

    ffmpeg_cmd.extend([
        '-c:a', 'copy',  # Copy audio stream (no re-encode)
        output_m4a
    ])

    try:
        result = subprocess.run(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:
            raise Exception(f"FFmpeg failed: {result.stderr}")
    finally:
        # Cleanup temp files
        if os.path.exists(metadata_path):
            os.unlink(metadata_path)
        if cover_path and os.path.exists(cover_path):
            os.unlink(cover_path)


class AudiobookCreator:
    """Main class for creating audiobooks with metadata and chapters."""

    def __init__(
        self,
        input_path: str,
        options: AudiobookOptions
    ):
        """Initialize audiobook creator.

        Args:
            input_path: Path to EPUB or PDF file
            options: Audiobook creation options
        """
        self.input_path = input_path
        self.options = options
        self.temp_dir = None
        self.metadata = {}
        self.selected_chapters = []

        # Determine input type
        if input_path.endswith('.epub'):
            self.input_type = 'epub'
        elif input_path.endswith('.pdf'):
            self.input_type = 'pdf'
        else:
            raise ValueError("Input must be EPUB or PDF file")

    def __enter__(self):
        """Context manager entry - create temp directory."""
        # Use custom temp dir or create timestamped one
        if self.options.temp_dir:
            self.temp_dir = self.options.temp_dir
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.temp_dir = os.path.abspath(f"./audiobook_temp_{timestamp}")

        os.makedirs(self.temp_dir, exist_ok=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup temp files."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            # Only cleanup on success (not on exception)
            if exc_type is None and not self.options.keep_temp:
                try:
                    shutil.rmtree(self.temp_dir)
                    print("✓ Cleaned up temporary files")
                except Exception as e:
                    print(f"Warning: Could not remove temp directory: {e}")
            elif self.options.keep_temp:
                print(f"Temporary files kept at: {self.temp_dir}")
            else:
                print(f"Error occurred. Temp files preserved at: {self.temp_dir}")

    def extract_metadata(self) -> Dict:
        """Extract metadata from input file.

        Returns:
            Dictionary with metadata and cover
        """
        print("[1/7] Extracting metadata and cover...")

        if self.input_type == 'epub':
            metadata = extract_epub_metadata(self.input_path)
        else:  # pdf
            metadata = extract_pdf_metadata(self.input_path)

        # Apply overrides from options
        if self.options.title:
            metadata['title'] = self.options.title
        if self.options.author:
            metadata['author'] = self.options.author
        if self.options.narrator:
            metadata['narrator'] = self.options.narrator
        if self.options.year:
            metadata['year'] = self.options.year
        if self.options.genre:
            metadata['genre'] = self.options.genre
        if self.options.description:
            metadata['description'] = self.options.description

        # Load custom cover if provided
        if self.options.cover_path and os.path.exists(self.options.cover_path):
            with open(self.options.cover_path, 'rb') as f:
                metadata['cover'] = f.read()

        # Use filename as title if no title found
        if not metadata.get('title'):
            metadata['title'] = os.path.splitext(os.path.basename(self.input_path))[0]

        # Print extracted metadata
        if metadata.get('title'):
            print(f"  Title: \"{metadata['title']}\"")
        if metadata.get('author'):
            print(f"  Author: \"{metadata['author']}\"")
        if metadata.get('cover'):
            print(f"  Cover: Found ({len(metadata['cover'])} bytes)")
        else:
            print("  Cover: Not found")

        print("  ✓ Complete\n")

        self.metadata = metadata
        return metadata

    def select_chapters_from_list(self, all_chapters: List[Chapter]) -> List[Chapter]:
        """Select chapters based on options.

        Args:
            all_chapters: List of all available chapters

        Returns:
            List of selected chapters
        """
        print(f"[2/7] Selecting chapters...")

        total = len(all_chapters)
        indices = parse_chapter_selection(self.options.select_chapters, total)

        selected = [all_chapters[i] for i in indices]

        print(f"  Processing {len(selected)} of {total} chapters")
        if len(selected) < total:
            chapter_nums = [str(i + 1) for i in indices]
            print(f"  Selected: {', '.join(chapter_nums)}")

        print("  ✓ Complete\n")

        self.selected_chapters = selected
        return selected

    def get_temp_dir(self) -> str:
        """Get temp directory path."""
        return self.temp_dir
