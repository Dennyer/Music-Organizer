import os
import json
import shutil
import random
import requests
from pathlib import Path
from pydub import AudioSegment
import tempfile
import argparse
import time
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import hashlib


@dataclass
class ProcessingStats:
    """Statistics for processing results"""
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    duplicates: int = 0


class AudioOrganizer:
    def __init__(self, api_token: str, input_folder: str, output_folder: str,
                 dry_run: bool = False, log_level: str = "INFO", clip_duration: int = 10):
        """
        Initialize the Audio Organizer

        Args:
            api_token: Your Audd API token
            input_folder: Path to folder containing audio files to scan
            output_folder: Path to output folder where organized structure will be created
            dry_run: If True, only simulate the organization without moving files
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        """
        self.api_token = api_token
        self.input_folder = Path(input_folder)
        self.output_folder = Path(output_folder)
        self.dry_run = dry_run
        self.clip_duration = clip_duration
        self.supported_formats = {'.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg', '.wma'}

        # Setup logging
        self.setup_logging(log_level)

        # Create output folder if it doesn't exist (unless dry run)
        if not dry_run:
            self.output_folder.mkdir(parents=True, exist_ok=True)

        # Progress tracking
        self.processed_files = []
        self.failed_files = []

        # Cache for file hashes to detect duplicates
        self.file_hashes = {}

    def setup_logging(self, log_level: str):
        """Setup logging configuration"""
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('audio_organizer.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def get_file_hash(self, file_path: Path) -> str:
        """Generate hash for file to detect duplicates"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def get_audio_files(self) -> List[Path]:
        """Get all supported audio files from input folder recursively"""
        audio_files = []
        for file_path in self.input_folder.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in self.supported_formats:
                audio_files.append(file_path)

        self.logger.info(f"Found {len(audio_files)} audio files")
        return audio_files

    def validate_audio_file(self, file_path: Path) -> bool:
        """Validate if audio file is not corrupted"""
        try:
            audio = AudioSegment.from_file(str(file_path))
            if len(audio) < 10000:  # Less than 10 second
                self.logger.warning(f"Audio file too short: {file_path.name}")
                return False
            return True
        except Exception as e:
            self.logger.error(f"Corrupted audio file {file_path.name}: {e}")
            return False

    def create_random_clip(self, audio_path: Path, duration: int = 10) -> Optional[str]:
        """
        Create a random clip from audio file, with better error handling

        Args:
            audio_path: Path to the audio file
            duration: Duration of clip in seconds (default: 10)

        Returns:
            Path to temporary clip file or None if failed
        """
        try:
            # Load audio file
            audio = AudioSegment.from_file(str(audio_path))
            total_duration = len(audio)  # in milliseconds

            # If audio is too short, use the whole file
            if total_duration < duration * 1000:
                self.logger.warning(f"{audio_path.name} is shorter than {duration} seconds, using full file")
                clip = audio
            else:
                # Calculate safe zone (exclude first and last 15% for better results)
                safe_start = int(total_duration * 0.15)
                safe_end = int(total_duration * 0.85)

                # Ensure we have enough space for the clip
                if safe_end - safe_start < duration * 1000:
                    # If safe zone is too small, use middle portion
                    middle = total_duration // 2
                    clip_start = max(0, middle - (duration * 500))
                else:
                    # Random start position within safe zone
                    max_start = safe_end - (duration * 1000)
                    clip_start = random.randint(safe_start, max_start)

                clip_end = clip_start + (duration * 1000)
                clip = audio[clip_start:clip_end]

            # Save clip to temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
            clip.export(temp_file.name, format="mp3", bitrate="128k")
            return temp_file.name

        except Exception as e:
            self.logger.error(f"Error creating clip for {audio_path}: {e}")
            return None

    def identify_song(self, clip_path: str, retries: int = 3) -> Optional[Dict[Any, Any]]:
        """
        Identify song using Audd API with retry logic

        Args:
            clip_path: Path to audio clip
            retries: Number of retries on failure

        Returns:
            API response data or None if failed
        """
        for attempt in range(retries):
            try:
                data = {
                    'api_token': self.api_token,
                    'return': 'apple_music,spotify',
                }

                with open(clip_path, 'rb') as audio_file:
                    files = {'file': audio_file}
                    response = requests.post('https://api.audd.io/', data=data, files=files, timeout=30)

                if response.status_code == 200:
                    result = response.json()
                    if result.get('status') == 'success' and result.get('result'):
                        return result['result']
                    else:
                        self.logger.debug(f"Song not identified: {result.get('error', 'Unknown error')}")
                        return None
                elif response.status_code == 901:  # Rate limited or API limited
                    wait_time = 2 ** attempt
                    self.logger.warning(f"Rate limited, waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                elif response.status_code == 900:  # Invalid API Token
                    self.logger.warning(f"Invalid API token.")
                    return None
                elif response.status_code == 700:  # No file
                    self.logger.warning(f"Missing file attached to request.")
                    return None
                elif response.status_code == 500:  # Invalid file
                    self.logger.warning(f"Invalid file.")
                    return None
                elif response.status_code == 400:  # File too big
                    self.logger.warning(f"File size too large.")
                    return None
                elif response.status_code == 300:  # File too small
                    self.logger.warning(f"File too small to recognize song.")
                    return None
                else:
                    self.logger.error(f"API request failed with status code: {response.status_code}")
                    return None

            except requests.exceptions.Timeout:
                self.logger.warning(f"Request timeout, attempt {attempt + 1}/{retries}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
            except Exception as e:
                self.logger.error(f"Error identifying song: {e}")
                return None

        return None

    def sanitize_filename(self, name: str) -> str:
        """Remove or replace invalid characters for file/folder names"""
        # Characters that are invalid in most file systems
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, '_')

        # Remove content in parentheses and brackets
        import re
        name = re.sub(r'\([^)]*\)', '', name)
        name = re.sub(r'\[[^\]]*\]', '', name)

        # Remove leading/trailing spaces and dots
        name = name.strip('. ')

        # Limit length to avoid issues
        if len(name) > 100:
            name = name[:100]

        return name or "Unknown"

    def create_folder_structure(self, song_info: Dict[Any, Any], original_file: Path) -> Path:
        """
        Create folder structure and return target path

        Args:
            song_info: Song information from API
            original_file: Original audio file

        Returns:
            Target path for the organized file
        """
        # Extract information
        artist = song_info.get('artist', 'Unknown Artist')
        title = song_info.get('title', 'Unknown Title')

        # Try to get album info from Apple Music or Spotify data
        album = None
        if 'apple_music' in song_info and song_info['apple_music'].get('albumName'):
            album = song_info['apple_music']['albumName']
        elif 'spotify' in song_info and song_info['spotify'].get('album', {}).get('name'):
            album = song_info['spotify']['album']['name']
        elif song_info.get('album'):
            album = song_info['album']

        # Sanitize names
        artist = self.sanitize_filename(artist)
        title = self.sanitize_filename(title)

        # Create folder structure
        artist_folder = self.output_folder / artist

        if album and album.strip():
            album = self.sanitize_filename(album)
            target_folder = artist_folder / album
        else:
            target_folder = artist_folder

        # Create directories (unless dry run)
        if not self.dry_run:
            target_folder.mkdir(parents=True, exist_ok=True)

        # Create target file path
        file_extension = original_file.suffix
        target_file = target_folder / f"{title}{file_extension}"

        return target_file

    def move_file(self, source: Path, target: Path) -> bool:
        """
        Move file from source to target, handling duplicates

        Args:
            source: Source file path
            target: Target file path

        Returns:
            True if successful, False otherwise
        """
        if self.dry_run:
            self.logger.info(f"DRY RUN: Would move {source.name} -> {target.relative_to(self.output_folder)}")
            return True

        try:
            # Handle duplicates by comparing file hashes
            if target.exists():
                source_hash = self.get_file_hash(source)
                target_hash = self.get_file_hash(target)

                if source_hash == target_hash:
                    self.logger.info(f"Identical file already exists, removing duplicate: {source.name}")
                    os.remove(source)
                    return True

                # If different files, keep the larger one
                self.logger.info(f"Found different versions of {target.name}")
                if os.path.getsize(source) > os.path.getsize(target):
                    os.remove(target)
                    shutil.move(str(source), str(target))
                    self.logger.info(f"Replaced with larger version: {source.name}")
                else:
                    os.remove(source)
                    self.logger.info(f"Kept existing larger version: {target.name}")
                return True

            shutil.move(str(source), str(target))
            self.logger.info(f"Moved: {source.name} -> {target.relative_to(self.output_folder)}")
            return True

        except Exception as e:
            self.logger.error(f"Error moving file {source} to {target}: {e}")
            return False

    def process_file(self, file_path: Path) -> bool:
        """
        Process a single audio file

        Args:
            file_path: Path to audio file

        Returns:
            True if successful, False otherwise
        """
        self.logger.info(f"Processing: {file_path.name}")

        # Validate audio file first
        if not self.validate_audio_file(file_path):
            self.failed_files.append(str(file_path))
            return False

        # Check if file is a duplicate
        file_hash = self.get_file_hash(file_path)
        if file_hash in self.file_hashes:
            self.logger.info(f"Duplicate file detected: {file_path.name}")
            if not self.dry_run:
                os.remove(file_path)
            return True

        self.file_hashes[file_hash] = str(file_path)

        # Create random clip
        clip_path = self.create_random_clip(file_path, self.clip_duration)
        if not clip_path:
            self.failed_files.append(str(file_path))
            return False

        try:
            # Identify song
            song_info = self.identify_song(clip_path)
            if not song_info:
                self.logger.warning(f"Could not identify {file_path.name}")
                self.failed_files.append(str(file_path))
                return False

            # Create folder structure and move file
            target_path = self.create_folder_structure(song_info, file_path)
            success = self.move_file(file_path, target_path)

            if success:
                self.processed_files.append({
                    'original_path': str(file_path),
                    'target_path': str(target_path),
                    'artist': song_info.get('artist', 'Unknown'),
                    'title': song_info.get('title', 'Unknown'),
                    'album': song_info.get('album', '')
                })
                self.logger.info(
                    f"Successfully organized: {song_info.get('artist', 'Unknown')} - {song_info.get('title', 'Unknown')}")

            return success

        finally:
            # Clean up temporary clip
            try:
                os.unlink(clip_path)
            except:
                pass

    def save_results(self, stats: ProcessingStats):
        """Save processing results to JSON file"""
        results = {
            'stats': {
                'total': stats.total,
                'success': stats.success,
                'failed': stats.failed,
                'skipped': stats.skipped,
                'duplicates': stats.duplicates
            },
            'processed_files': self.processed_files,
            'failed_files': self.failed_files
        }

        results_file = self.output_folder / 'organization_results.json'
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        self.logger.info(f"Results saved to {results_file}")

    def organize_library(self, delay: float = 1.0, max_workers: int = 1) -> ProcessingStats:
        """
        Organize entire music library

        Args:
            delay: Delay between API calls to avoid rate limiting
            max_workers: Number of parallel workers (set to 1 for API rate limiting)

        Returns:
            ProcessingStats object with processing statistics
        """
        audio_files = self.get_audio_files()
        stats = ProcessingStats(total=len(audio_files))

        self.logger.info(f"Starting to process {len(audio_files)} audio files")

        # Process files sequentially to respect API rate limits
        for i, file_path in enumerate(audio_files, 1):
            self.logger.info(f"[{i}/{len(audio_files)}] Processing: {file_path.name}")

            try:
                success = self.process_file(file_path)
                if success:
                    stats.success += 1
                else:
                    stats.failed += 1

            except Exception as e:
                self.logger.error(f"Unexpected error processing {file_path.name}: {e}")
                stats.failed += 1

            # Add delay to avoid overwhelming the API
            if i < len(audio_files) and delay > 0:
                time.sleep(delay)

        # Save results
        self.save_results(stats)
        return stats


def main():
    parser = argparse.ArgumentParser(description='Organize audio files using Audd API')
    parser.add_argument('--api-token', required=True, help='Your Audd API token')
    parser.add_argument('--input', required=True, help='Input folder containing audio files')
    parser.add_argument('--output', required=True, help='Output folder for organized structure')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between API calls (seconds)')
    parser.add_argument('--dry-run', action='store_true', help='Simulate organization without moving files')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='Set logging level')
    parser.add_argument('--clip-duration', type=int, default=10, help='Duration of audio clips for identification')

    args = parser.parse_args()

    # Validate input folder
    if not os.path.exists(args.input):
        print(f"Error: Input folder '{args.input}' does not exist")
        return

    # Initialize organizer
    organizer = AudioOrganizer(
        api_token=args.api_token,
        input_folder=args.input,
        output_folder=args.output,
        dry_run=args.dry_run,
        log_level=args.log_level,
        clip_duration=args.clip_duration
    )

    # Process files
    if args.dry_run:
        print("DRY RUN MODE: No files will be moved")

    print(f"Starting to organize files from '{args.input}' to '{args.output}'")
    stats = organizer.organize_library(delay=args.delay)

    # Print summary
    print(f"\n=== SUMMARY ===")
    print(f"Total files: {stats.total}")
    print(f"Successfully organized: {stats.success}")
    print(f"Failed: {stats.failed}")
    print(f"Duplicates handled: {stats.duplicates}")
    print(f"Success rate: {stats.success / stats.total * 100:.1f}%" if stats.total > 0 else "0%")


if __name__ == "__main__":
    main()