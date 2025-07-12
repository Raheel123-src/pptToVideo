import modal
import os
from pathlib import Path

# Create Modal app
app = modal.App("pdf-to-video-api-pro")

# Define the image with all dependencies optimized for Pro tier
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
    "fonts-dejavu-core",
    "fonts-noto-cjk"
]).run_commands([
    "mkdir -p /tmp/uploads",
    "mkdir -p /tmp/cache"
])

# Create volume for persistent storage (100GB available on Pro)
volume = modal.Volume.from_name("pdf-video-storage-pro", create_if_missing=True)

# Pro tier optimized function configuration
@app.function(
    image=image,
    volumes={"/tmp/uploads": volume},
    timeout=600,  # 10 minutes (increased for Pro tier)
    memory=8192,  # 8GB RAM (Pro tier max)
    cpu=4.0,      # 4 CPU cores (Pro tier max)
    secrets=[
        modal.Secret.from_name("openai-api-key"),
        modal.Secret.from_name("aws-credentials")
    ],
    keep_warm=1   # Keep 1 instance warm for faster response
)
def process_pdf_audio_pro(pdf_data: bytes, audio_data: bytes, pdf_filename: str, audio_filename: str):
    """Process PDF and audio with Pro tier resources"""
    import tempfile
    import subprocess
    from pathlib import Path
    import concurrent.futures
    
    # Create temporary files
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as pdf_file:
        pdf_file.write(pdf_data)
        pdf_path = pdf_file.name
    
    with tempfile.NamedTemporaryFile(suffix=os.path.splitext(audio_filename)[-1], delete=False) as audio_file:
        audio_file.write(audio_data)
        audio_path = audio_file.name
    
    try:
        # Import your processing functions
        from modal_api import upload_pdf_audio_internal_pro
        
        # Process the files with enhanced resources
        result = upload_pdf_audio_internal_pro(pdf_path, audio_path)
        
        # Read the generated video
        if result.get("local_video_path") and os.path.exists(result["local_video_path"]):
            with open(result["local_video_path"], "rb") as f:
                video_data = f.read()
            
            return {
                "success": True,
                "video_data": video_data,
                "filename": "output.mp4",
                "details": result.get("details", {}),
                "processing_time": result.get("processing_time", 0)
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
    keep_warm=1
)
def process_ppt_audio_pro(ppt_data: bytes, audio_data: bytes, ppt_filename: str, audio_filename: str):
    """Process PowerPoint and audio with Pro tier resources"""
    import tempfile
    import subprocess
    from pathlib import Path
    
    # Create temporary files
    with tempfile.NamedTemporaryFile(suffix='.pptx', delete=False) as ppt_file:
        ppt_file.write(ppt_data)
        ppt_path = ppt_file.name
    
    with tempfile.NamedTemporaryFile(suffix=os.path.splitext(audio_filename)[-1], delete=False) as audio_file:
        audio_file.write(audio_data)
        audio_path = audio_file.name
    
    try:
        # Import your processing functions
        from modal_api import upload_ppt_audio_animate_internal_pro
        
        # Process the files with enhanced resources
        result = upload_ppt_audio_animate_internal_pro(ppt_path, audio_path)
        
        # Read the generated video
        if result.get("local_video_path") and os.path.exists(result["local_video_path"]):
            with open(result["local_video_path"], "rb") as f:
                video_data = f.read()
            
            return {
                "success": True,
                "video_data": video_data,
                "filename": "output.mp4",
                "details": result.get("details", {}),
                "processing_time": result.get("processing_time", 0)
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

# Web endpoints with Pro tier configuration
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
    keep_warm=1
)
@modal.web_endpoint(method="POST")
async def upload_pdf_audio_endpoint_pro(
    pdf: modal.File = modal.File(...),
    audio: modal.File = modal.File(...)
):
    """Pro tier web endpoint for PDF + audio processing"""
    from fastapi import HTTPException
    from fastapi.responses import Response
    import time
    
    start_time = time.time()
    
    try:
        # Validate file types
        if not pdf.name.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="PDF file required")
        
        if not audio.name.lower().endswith(('.mp3', '.wav', '.m4a')):
            raise HTTPException(status_code=400, detail="Audio file required (.mp3, .wav, .m4a)")
        
        # Validate file sizes (Pro tier can handle larger files)
        if len(pdf.data) > 50 * 1024 * 1024:  # 50MB limit
            raise HTTPException(status_code=400, detail="PDF file too large (max 50MB)")
        
        if len(audio.data) > 100 * 1024 * 1024:  # 100MB limit
            raise HTTPException(status_code=400, detail="Audio file too large (max 100MB)")
        
        # Process files
        result = process_pdf_audio_pro.remote(
            pdf.data,
            audio.data,
            pdf.name,
            audio.name
        )
        
        processing_time = time.time() - start_time
        
        if result["success"]:
            return Response(
                content=result["video_data"],
                media_type="video/mp4",
                headers={
                    "Content-Disposition": f"attachment; filename={result['filename']}",
                    "X-Processing-Time": str(processing_time),
                    "X-Total-Slides": str(result["details"].get("total_slides", 0))
                }
            )
        else:
            raise HTTPException(status_code=500, detail=result["error"])
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@stub.function(
    image=image,
    volumes={"/tmp/uploads": volume},
    timeout=600,
    memory=8192,
    cpu=4.0,
    secrets=[
        modal.Secret.from_name("openai-api-key"),
        modal.Secret.from_name("aws-credentials")
    ],
    keep_warm=1
)
@modal.web_endpoint(method="POST")
async def upload_ppt_audio_endpoint_pro(
    ppt: modal.File = modal.File(...),
    audio: modal.File = modal.File(...)
):
    """Pro tier web endpoint for PowerPoint + audio processing"""
    from fastapi import HTTPException
    from fastapi.responses import Response
    import time
    
    start_time = time.time()
    
    try:
        # Validate file types
        if not ppt.name.lower().endswith('.pptx'):
            raise HTTPException(status_code=400, detail="PowerPoint file required")
        
        if not audio.name.lower().endswith(('.mp3', '.wav', '.m4a')):
            raise HTTPException(status_code=400, detail="Audio file required (.mp3, .wav, .m4a)")
        
        # Validate file sizes
        if len(ppt.data) > 50 * 1024 * 1024:  # 50MB limit
            raise HTTPException(status_code=400, detail="PowerPoint file too large (max 50MB)")
        
        if len(audio.data) > 100 * 1024 * 1024:  # 100MB limit
            raise HTTPException(status_code=400, detail="Audio file too large (max 100MB)")
        
        # Process files
        result = process_ppt_audio_pro.remote(
            ppt.data,
            audio.data,
            ppt.name,
            audio.name
        )
        
        processing_time = time.time() - start_time
        
        if result["success"]:
            return Response(
                content=result["video_data"],
                media_type="video/mp4",
                headers={
                    "Content-Disposition": f"attachment; filename={result['filename']}",
                    "X-Processing-Time": str(processing_time),
                    "X-Total-Slides": str(result["details"].get("total_slides", 0))
                }
            )
        else:
            raise HTTPException(status_code=500, detail=result["error"])
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Health check and monitoring endpoints
@stub.function(image=image, keep_warm=1)
@modal.web_endpoint(method="GET")
async def health_pro():
    """Pro tier health check endpoint"""
    import psutil
    import os
    
    return {
        "status": "healthy",
        "service": "pdf-to-video-api-pro",
        "tier": "pro",
        "resources": {
            "memory_gb": 8,
            "cpu_cores": 4,
            "storage_gb": 100,
            "bandwidth_tb": 1
        },
        "system": {
            "memory_available_gb": round(psutil.virtual_memory().available / (1024**3), 2),
            "cpu_count": psutil.cpu_count()
        }
    }

@stub.function(image=image)
@modal.web_endpoint(method="GET")
async def status_pro():
    """Detailed status endpoint for Pro tier"""
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
            "GPU acceleration (T4)",
            "Warm instances",
            "Extended timeouts",
            "Large file support",
            "Priority support"
        ]
    }

if __name__ == "__main__":
    stub.serve() 