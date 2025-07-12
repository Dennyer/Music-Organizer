
# 🎵 Music Organizer

A Python tool that automatically organizes your music library by identifying songs using audio fingerprinting and creating a structured folder hierarchy.

## ✨ Features

- 🔍 **Audio Fingerprinting**: Uses the Audd API to identify songs from audio clips
- 📁 **Smart Organization**: Creates Artist/Album folder structure automatically
- 🎯 **Duplicate Detection**: Identifies and handles duplicate files intelligently
- 🔄 **Multiple Format Support**: Works with MP3, WAV, FLAC, M4A, AAC, OGG, and WMA files
- 🛡️ **File Validation**: Checks for corrupted or too-short audio files
- 📊 **Progress Tracking**: Detailed logging and processing statistics
- 🚀 **Dry Run Mode**: Preview organization without moving files
- ⚡ **Rate Limiting**: Built-in API rate limiting to avoid service disruption

## 🚀 Quick Start

### Prerequisites

```bash
pip install pydub requests pathlib audioop-lts
```

You'll also need an API token from [Audd.io](https://audd.io/) and have [FFmpeg](https://ffmpeg.org/) installed.

### Basic Usage

```bash
python music_organizer.py --api-token YOUR_TOKEN --input /path/to/music --output /path/to/organized
```

### Dry Run (Recommended First)

```bash
python music_organizer.py --api-token YOUR_TOKEN --input /path/to/music --output /path/to/organized --dry-run
```

## 📋 Command Line Options

|       Option      |                   Description                | Default |
|-------------------|----------------------------------------------|---------|
| `--api-token`     | Your Audd API token (required)               | -       |
| `--input`         | Input folder containing audio files          | -       |
| `--output`        | Output folder for organized structure        | -       |
| `--delay`         | Delay between API calls (seconds)            | 1.0     |
| `--dry-run`       | Simulate without moving files                | False   |
| `--log-level`     | Logging level (DEBUG/INFO/WARNING/ERROR)     | INFO    |
| `--clip-duration` | Duration of audio clips for identification   | 10      |

## 🏗️ How It Works

1. **🔍 Discovery**: Recursively scans input folder for supported audio files
2. **✅ Validation**: Checks each file for corruption and minimum duration
3. **✂️ Clip Creation**: Creates random clips from audio files for identification
4. **🎵 Identification**: Sends clips to Audd API for song recognition
5. **📁 Organization**: Creates Artist/Album folder structure
6. **🔄 File Management**: Moves files to organized locations, handling duplicates
7. **📊 Reporting**: Generates processing statistics

## 📂 Output Structure

```
Organized_Music/
├── Artist Name/
│   ├── Album Name/
│   │   ├── Song 1.mp3
│   │   └── Song 2.mp3
│   └── Single Songs/
│       └── Song Without Album.mp3
└── organization_results.json
```

## 🔧 Configuration

### Supported Audio Formats

- 🎵 MP3 (`.mp3`)
- 🎵 WAV (`.wav`) 
- 🎵 FLAC (`.flac`)
- 🎵 M4A (`.m4a`)
- 🎵 AAC (`.aac`)
- 🎵 OGG (`.ogg`)
- 🎵 WMA (`.wma`)

### Duplicate Handling

The tool uses MD5 hashing to detect duplicates and handles them intelligently:
- ✅ Identical files: Keeps one copy, removes duplicates
- ⚖️ Different versions: Keeps the larger file (typically better quality)

## 📊 Results and Logging

### Processing Statistics

After completion, you'll get a summary showing:
- 📈 Total files processed
- ✅ Successfully organized files
- ❌ Failed identifications
- 🔄 Duplicates handled
- 📊 Success rate percentage

### Log Files

- `music_organizer.log`: Detailed processing log
- `organization_results.json`: Complete processing results with file mappings

## ⚠️ Important Notes

> **Note**: Not all features have been fully tested as different error conditions may not have been encountered during development. Please use the `--dry-run` option first to preview the organization before processing your entire library.

### API Rate Limiting

The Audd API has rate limits, so the tool includes:
- 🕐 Configurable delays between requests
- 🔄 Retry logic for failed requests
- 🛡️ Proper error handling for rate limit responses

### File Safety

- 🔒 Original files are moved (not copied) to save disk space
- 🔍 Duplicate detection prevents data loss
- 📝 Comprehensive logging for troubleshooting

## 🛠️ Advanced Usage

### Custom Clip Duration

For better identification accuracy, you can adjust the clip duration:

```bash
python music_organizer.py --api-token YOUR_TOKEN --input /path/to/music --output /path/to/organized --clip-duration 15
```

### Debug Mode

For troubleshooting, enable debug logging:

```bash
python music_organizer.py --api-token YOUR_TOKEN --input /path/to/music --output /path/to/organized --log-level DEBUG
```

### Slower Processing (Better for Large Libraries)

Add more delay between API calls:

```bash
python music_organizer.py --api-token YOUR_TOKEN --input /path/to/music --output /path/to/organized --delay 2.0
```

## 🔧 Troubleshooting

### Common Issues

**API Token Issues**
- ❌ Error 900: Invalid API token
- ✅ Solution: Verify your token at [Audd.io](https://audd.io/)

**File Issues**
- ❌ Error 400: File too large
- ❌ Error 300: File too small
- ❌ Error 500: Invalid file format
- ✅ Solution: Check file format and size requirements

**Rate Limiting**
- ❌ Error 901: Rate limited
- ✅ Solution: Increase `--delay` parameter or purchase more requests

### File Validation Failures

The tool validates audio files and will skip:
- 🚫 Corrupted files
- 🚫 Files shorter than 10 seconds
- 🚫 Unsupported formats

## 🤝 Contributing

Feel free to submit issues and enhancement requests! Areas that could use improvement:

- 🧪 More comprehensive error testing
- 🎨 Additional metadata extraction
- 🔄 Resume functionality for interrupted processing
- 🌐 Support for additional identification APIs
