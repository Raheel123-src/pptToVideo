import modal
import os
from pathlib import Path

# Create Modal app
app = modal.App("pdf-to-video-api-pro")

# Define the image with all dependencies
image = modal.Image.debian_slim(python_version="3.11").pip_install([
    "fastapi",
    "uvicorn[standard]",
    "pdf2image",
    "Pillow",
    "python-dotenv",
    "openai",
    "openai-whisper",
    "python-pptx",
    "boto3",
    "PyMuPDF",
    "pdfminer.six",
    "pytesseract",
    "python-multipart",
    "requests"
]).apt_install([
    "ffmpeg",
    "tesseract-ocr",
    "poppler-utils",
    "fonts-liberation",
    "fonts-dejavu-core"
]).run_commands([
    "mkdir -p /tmp/uploads"
])

# Create volume for persistent storage
volume = modal.Volume.from_name("pdf-video-storage-pro", create_if_missing=True)

@app.function(
    image=image,
    volumes={"/tmp/uploads": volume},
    timeout=600,
    memory=8192,
    cpu=4.0,
    secrets=[
        modal.Secret.from_name("openai-api-key"),
        modal.Secret.from_name("aws-credentials")
    ],
    min_containers=1
)
def process_pdf_audio(pdf_data: bytes, audio_data: bytes, pdf_filename: str, audio_filename: str):
    """Process PDF and audio with Pro tier resources"""
    import tempfile
    import subprocess
    import time
    from pathlib import Path
    
    start_time = time.time()
    
    # Create temporary files
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as pdf_file:
        pdf_file.write(pdf_data)
        pdf_path = pdf_file.name
    
    with tempfile.NamedTemporaryFile(suffix=os.path.splitext(audio_filename)[-1], delete=False) as audio_file:
        audio_file.write(audio_data)
        audio_path = audio_file.name
    
    try:
        # Set environment variables
        os.environ['UPLOADS_DIR'] = '/tmp/uploads'
        
        # Import processing functions
        from modal_api import upload_pdf_audio_internal_pro
        
        # Process the files
        result = upload_pdf_audio_internal_pro(pdf_path, audio_path)
        
        # Read the generated video
        if result.get("local_video_path") and os.path.exists(result["local_video_path"]):
            with open(result["local_video_path"], "rb") as f:
                video_data = f.read()
            
            processing_time = time.time() - start_time
            
            return {
                "success": True,
                "video_data": video_data,
                "filename": "output.mp4",
                "details": result.get("details", {}),
                "processing_time": processing_time
            }
        else:
            return {
                "success": False,
                "error": "Video generation failed"
            }
    
    finally:
        # Clean up temporary files
        os.unlink(pdf_path)
        os.unlink(audio_path)

@app.function(
    image=image,
    volumes={"/tmp/uploads": volume},
    timeout=600,
    memory=8192,
    cpu=4.0,
    secrets=[
        modal.Secret.from_name("openai-api-key"),
        modal.Secret.from_name("aws-credentials")
    ],
    min_containers=1
)
def process_ppt_audio(ppt_data: bytes, audio_data: bytes, ppt_filename: str, audio_filename: str):
    """Process PowerPoint and audio with Pro tier resources"""
    import tempfile
    import subprocess
    import time
    from pathlib import Path
    
    start_time = time.time()
    
    # Create temporary files
    with tempfile.NamedTemporaryFile(suffix='.pptx', delete=False) as ppt_file:
        ppt_file.write(ppt_data)
        ppt_path = ppt_file.name
    
    with tempfile.NamedTemporaryFile(suffix=os.path.splitext(audio_filename)[-1], delete=False) as audio_file:
        audio_file.write(audio_data)
        audio_path = audio_file.name
    
    try:
        # Set environment variables
        os.environ['UPLOADS_DIR'] = '/tmp/uploads'
        
        # Import processing functions
        from modal_api import upload_ppt_audio_animate_internal_pro
        
        # Process the files
        result = upload_ppt_audio_animate_internal_pro(ppt_path, audio_path)
        
        # Read the generated video
        if result.get("local_video_path") and os.path.exists(result["local_video_path"]):
            with open(result["local_video_path"], "rb") as f:
                video_data = f.read()
            
            processing_time = time.time() - start_time
            
            return {
                "success": True,
                "video_data": video_data,
                "filename": "output.mp4",
                "details": result.get("details", {}),
                "processing_time": processing_time
            }
        else:
            return {
                "success": False,
                "error": "Video generation failed"
            }
    
    finally:
        # Clean up temporary files
        os.unlink(ppt_path)
        os.unlink(audio_path)

# Health check endpoint
@app.function(image=image, min_containers=1)
@modal.fastapi_endpoint(method="GET")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "pdf-to-video-api-pro",
        "tier": "pro",
        "resources": {
            "memory_gb": 8,
            "cpu_cores": 4,
            "storage_gb": 100,
            "bandwidth_tb": 1
        }
    }

@app.function(image=image)
@modal.fastapi_endpoint(method="GET")
async def status():
    """Status endpoint"""
    return {
        "plan": "pro",
        "monthly_cost": "$25",
        "limits": {
            "function_calls_per_day": 10000,
            "memory_per_function_gb": 8,
            "cpu_cores_per_function": 4,
            "storage_gb": 100,
            "bandwidth_tb": 1
        },
        "features": [
            "Warm instances",
            "Extended timeouts",
            "Large file support",
            "Priority support"
        ]
    }

if __name__ == "__main__":
    app.run() 