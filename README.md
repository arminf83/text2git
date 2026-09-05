# GitHub OCR Uploader

A lightweight Python CLI tool that extracts text from images using Tesseract OCR and uploads the results to a GitHub repository as a single Markdown file.

## Features

* Recursively scans a directory for image files
* Supports multiple image formats
* Uses Tesseract OCR for text extraction
* Supports multiple Tesseract languages
* Combines OCR results from all images into one Markdown file
* Interactive GitHub repository selection
* Interactive branch selection
* Custom destination directory inside the repository
* Creates GitHub commits through the GitHub REST API
* Does not require the local Git CLI for uploading
* Keeps source images local and uploads only the generated Markdown file

## Supported Image Formats

* JPG / JPEG
* PNG
* BMP
* TIFF
* WEBP

## How It Works

```text
Image Directory
       │
       ▼
 Image Scanner
       │
       ▼
   Tesseract OCR
       │
       ▼
 Markdown Generator
       │
       ▼
 GitHub REST API
       │
       ├── Blob
       ├── Tree
       ├── Commit
       └── Branch Update
```

All OCR results are stored in a single Markdown file.

## Requirements

* Python 3.9+
* Tesseract OCR
* A GitHub account
* A GitHub token with permission to write to the target repository

## Installation

Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/github-ocr-uploader.git
cd github-ocr-uploader
```

Create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Install Tesseract on Ubuntu/Debian:

```bash
sudo apt update
sudo apt install tesseract-ocr
```

For English OCR:

```bash
sudo apt install tesseract-ocr-eng
```

For Persian OCR:

```bash
sudo apt install tesseract-ocr-fas
```

## Configuration

Create the environment file:

```bash
cp .env.example .env
```

Edit it:

```bash
nano .env
```

Set your GitHub token:

```env
GITHUB_TOKEN=your_github_token
```

You can also configure the OCR language:

```env
TESSERACT_LANG=eng
```

For Persian and English:

```env
TESSERACT_LANG=fas+eng
```

Do not commit `.env` to the repository.

## Usage

Run the program:

```bash
python3 github_ocr_uploader.py
```

The program will guide you through:

1. GitHub authentication
2. Repository selection
3. Branch selection
4. Local image directory selection
5. Image scanning
6. OCR processing
7. Markdown generation
8. GitHub destination selection
9. Commit message
10. Upload confirmation

Example:

```text
Image directory → Tesseract → Markdown → GitHub
```

## GitHub Upload Process

The application uses the GitHub Git Database API to create the commit.

The upload flow is:

```text
Create Blob
     ↓
Create Tree
     ↓
Create Commit
     ↓
Update Branch Reference
```

This means the application does not need to run `git add`, `git commit`, or `git push` locally.

## Security

The GitHub token is loaded from environment variables.

Never put your real token inside:

* `github_ocr_uploader.py`
* `README.md`
* `.env.example`
* Git commits
* Public posts

The `.env` file is excluded through `.gitignore`.

## Project Structure

```text
github-ocr-uploader/
├── github_ocr_uploader.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
└── LICENSE
```

## License

This project is licensed under the MIT License.
