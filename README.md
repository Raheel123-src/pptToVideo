# PDF/PPTX to Video Converter

A powerful FastAPI application that converts PDF documents and PowerPoint presentations into synchronized videos with audio narration. Features AI-powered content analysis, smooth animations, and automatic S3 upload for downloadable video links.

## 🚀 Features

### PDF Processing
- **PDF to Video**: Convert PDF pages to synchronized video with audio
- **AI Content Analysis**: GPT-4 powered content mapping and timing
- **Smart Page Transitions**: Automatic page-to-audio synchronization
- **Text Extraction**: Extract and analyze text content from PDF pages

### PowerPoint Processing
- **PPTX to Video**: Convert PowerPoint slides to animated videos
- **Animation States**: Before/after states with smooth text reveals
- **GPT-4 Vision Integration**: Extract actual rendered slide images
- **Fallback System**: Python-based extraction when GPT fails
- **Element Animations**: Smooth transitions between slide states

### Video Generation
- **Audio Synchronization**: Perfect timing between content and narration
- **Smooth Transitions**: Professional video transitions and effects
- **Multiple Formats**: Support for MP3, WAV, M4A audio files
- **S3 Integration**: Automatic upload with downloadable links

## 🛠️ Installation

### Prerequisites
- Python 3.8+
- FFmpeg (for video processing)
- AWS S3 bucket (for video storage)

### Setup

1. **Clone the repository**
```bash
git clone <repository-url>
cd pdfToImg
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Install FFmpeg**
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt update
sudo apt install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

4. **Configure environment variables**
Create a `.env` file in the project root:
```bash
# OpenAI API Key
OPENAI_API_KEY=your_openai_api_key_here

# Uploads directory
UPLOADS_DIR=uploads

# AWS S3 Configuration (for video uploads)
AWS_ACCESS_KEY_ID=your_aws_access_key_id_here
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key_here
AWS_REGION=us-east-1
S3_BUCKET_NAME=your_s3_bucket_name_here
```

5. **Run the application**
```bash
python -m uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

## 📖 API Endpoints

### 1. PDF to Video (`POST /upload-pdf-audio/`)

Convert a PDF document with audio narration to a synchronized video.

**Request:**
- `pdf`: PDF file (required)
- `audio`: Audio file - MP3, WAV, or M4A (required)

**Response:**
```json
{
  "message": "Successfully processed PDF and audio!",
  "video_download_url": "https://your-bucket.s3.amazonaws.com/videos/uuid.mp4?presigned-url",
  "video_filename": "uuid.mp4",
  "details": {
    "total_slides": 5,
    "audio_duration": 120.5,
    "video_path": "/path/to/local/video.mp4",
    "s3_key": "videos/uuid.mp4"
  }
}
```

### 2. PowerPoint to Video (`POST /upload-ppt-audio-animate/`)

Convert a PowerPoint presentation with audio to an animated video.

**Request:**
- `ppt`: PPTX file (required)
- `audio`: Audio file - MP3, WAV, or M4A (required)

**Response:**
```json
{
  "message": "Successfully created animated presentation!",
  "video_download_url": "https://your-bucket.s3.amazonaws.com/videos/uuid.mp4?presigned-url",
  "details": {
    "audio_sentences": 32,
    "slides_analyzed": 8,
    "animation_steps": 19,
    "frames_created": 19,
    "video_duration": 120.5
  }
}
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key for GPT-4 and Whisper | Yes |
| `UPLOADS_DIR` | Local directory for temporary files | No (default: uploads) |
| `AWS_ACCESS_KEY_ID` | AWS access key for S3 uploads | Yes |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key for S3 uploads | Yes |
| `AWS_REGION` | AWS region for S3 bucket | No (default: us-east-1) |
| `S3_BUCKET_NAME` | S3 bucket name for video storage | Yes |

### File Size Limits

- **PDF/PPTX**: Up to 25MB
- **Audio**: MP3, WAV, M4A formats
- **Video Output**: MP4 format with H.264 encoding

## 🎬 Animation Features

### PowerPoint Animations
- **Before State**: Images and shapes only (no text)
- **After State**: Complete slide with text revealed
- **Smooth Transitions**: 70/30 blend for natural text reveals
- **Element Timing**: Synchronized with audio narration

### PDF Transitions
- **Smart Page Mapping**: AI-powered content-to-page matching
- **No Repetition**: Each page appears only once
- **Optimal Timing**: Automatic duration calculation
- **Audio Sync**: Perfect synchronization with narration

## 🔄 Processing Pipeline

### PDF Processing
1. **Extract Pages**: Convert PDF to high-quality images
2. **Text Analysis**: Extract and analyze text content
3. **Audio Transcription**: Convert audio to text with timestamps
4. **Content Mapping**: AI-powered page-to-audio matching
5. **Video Generation**: Create synchronized video with transitions
6. **S3 Upload**: Upload final video and generate download link

### PowerPoint Processing
1. **Slide Analysis**: Extract slide content and structure
2. **Image Extraction**: Use GPT-4 Vision or Python fallback
3. **Animation Planning**: Create before/after states
4. **Audio Synchronization**: Match content to audio timing
5. **Video Creation**: Generate animated video with transitions
6. **S3 Upload**: Upload final video and generate download link

## 🚨 Error Handling

### Fallback Systems
- **GPT-4o-mini**: Lower token usage, tried first
- **GPT-4o**: Full model, used if mini fails
- **Python Extraction**: Local processing if GPT fails
- **S3 Fallback**: Local storage if upload fails

### Common Issues
- **File Too Large**: Automatic fallback to Python extraction
- **Token Limits**: Automatic model switching
- **S3 Upload Fail**: Returns local file path
- **Audio Sync**: Intelligent timing adjustments

## 📁 Project Structure

```
pdfToImg/
├── api.py                 # Main FastAPI application
├── pdf_to_img_and_text.py # PDF processing utilities
├── requirements.txt       # Python dependencies
├── uploads/              # Temporary file storage
└── README.md            # This file
```

## 🛡️ Security

- **Presigned URLs**: 24-hour expiry for video downloads
- **Unique Filenames**: UUID-based naming prevents conflicts
- **Environment Variables**: Secure credential management
- **File Validation**: Strict file type and size validation

## 🔍 Troubleshooting

### Common Issues

1. **FFmpeg not found**
   ```bash
   # Install FFmpeg
   brew install ffmpeg  # macOS
   sudo apt install ffmpeg  # Ubuntu
   ```

2. **S3 upload fails**
   - Check AWS credentials in `.env`
   - Verify S3 bucket exists and is accessible
   - Ensure proper IAM permissions

3. **GPT API errors**
   - Verify OpenAI API key
   - Check token limits and billing
   - Large files may trigger fallback to Python extraction

4. **Video generation fails**
   - Ensure FFmpeg is installed
   - Check available disk space
   - Verify audio file format

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📞 Support

For issues and questions:
- Create an issue in the repository
- Check the troubleshooting section
- Verify your environment configuration

---

**Made with ❤️ using FastAPI, OpenAI GPT-4, and AWS S3** 