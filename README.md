# PDF to Image and Audio Synchronization API

This API converts PDFs and PowerPoint presentations to images and synchronizes them with audio to create animated videos.

## Features

- PDF to image conversion with text extraction
- PowerPoint to image conversion with animation states
- Audio transcription using Whisper
- GPT-powered content analysis and animation planning
- Video generation with synchronized audio
- S3 upload for final videos

## Deployment on Render

### Prerequisites

1. Create a Render account
2. Set up environment variables in Render dashboard:
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `AWS_ACCESS_KEY_ID`: AWS access key for S3
   - `AWS_SECRET_ACCESS_KEY`: AWS secret key for S3
   - `AWS_DEFAULT_REGION`: AWS region (e.g., us-east-1)
   - `S3_BUCKET_NAME`: S3 bucket name for video storage

### Deployment Steps

1. **Connect your repository** to Render
2. **Use the render.yaml configuration** (already included)
3. **Set environment variables** in the Render dashboard
4. **Deploy** - Render will automatically:
   - Install Python 3.12
   - Install ffmpeg system dependencies
   - Install Python packages from requirements.txt
   - Start the FastAPI server

### API Endpoints

- `POST /upload-pdf-audio/`: Upload PDF + audio, get synchronized video
- `POST /upload-ppt-audio-animate/`: Upload PowerPoint + audio, get animated video

### File Size Limits

- Maximum file size: 25MB per file
- Supported formats: PDF, PPTX, MP3, WAV, M4A

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Install ffmpeg (macOS)
brew install ffmpeg

# Install ffmpeg (Ubuntu/Debian)
sudo apt-get install ffmpeg

# Run the API
uvicorn api:app --reload
```

## Troubleshooting

- **Python 3.12**: Explicitly configured for compatibility with all dependencies
- **Font issues**: Cross-platform font paths are included for Linux deployment
- **System dependencies**: ffmpeg and tesseract-ocr are automatically installed on Render
- **Missing modules**: All required Python packages are included in requirements.txt 