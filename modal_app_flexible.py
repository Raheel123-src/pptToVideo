import modal
import os
from pathlib import Path
import requests
import tempfile
from fastapi import UploadFile, File, Form
from fastapi.responses import FileResponse
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
import uuid
from datetime import datetime

# Create Modal app
app = modal.App("pdf-to-video-api-flexible")

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
volume = modal.Volume.from_name("pdf-video-storage-flexible", create_if_missing=True)

def download_file_from_url(url: str) -> bytes:
    """Download file from URL"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.content
    except Exception as e:
        raise Exception(f"Failed to download file from {url}: {str(e)}")

def upload_to_s3(file_path: str, bucket_name: str = "lisa-research") -> str:
    """Upload file to S3 and return the URL"""
    try:
        s3_client = boto3.client('s3')
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"modal_videos/{timestamp}_{unique_id}_output.mp4"
        
        # Upload file
        s3_client.upload_file(file_path, bucket_name, filename)
        
        # Generate URL
        url = f"https://{bucket_name}.s3.ap-south-1.amazonaws.com/{filename}"
        print(f"Uploaded video to S3: {url}")
        
        return url
        
    except NoCredentialsError:
        raise Exception("AWS credentials not found")
    except ClientError as e:
        raise Exception(f"S3 upload failed: {str(e)}")
    except Exception as e:
        raise Exception(f"Upload error: {str(e)}")

def get_extension(filename, default_ext):
    if filename:
        ext = os.path.splitext(filename)[-1]
        if ext:
            return ext
    return default_ext

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
@modal.fastapi_endpoint(method="POST")
async def process_pdf_audio_flexible(
    pdf_file: UploadFile = File(None),
    audio_file: UploadFile = File(None),
    pdf_url: str = Form(None),
    audio_url: str = Form(None),
    transition_type: str = Form("fade"),
    transition_duration: float = Form(1.0)
):
    """
    Flexible PDF + Audio processing endpoint
    Accepts either file uploads OR URLs for both PDF and audio
    """
    import time
    from pathlib import Path
    
    start_time = time.time()
    
    try:
        # Handle PDF input (file upload OR URL)
        pdf_data = None
        pdf_filename = None
        if pdf_file is not None:
            pdf_data = await pdf_file.read()
            pdf_filename = pdf_file.filename or 'file.pdf'
            print(f"Using uploaded PDF file: {pdf_filename}")
        elif pdf_url:
            pdf_data = download_file_from_url(pdf_url)
            pdf_filename = os.path.basename(pdf_url) or 'file.pdf'
            print(f"Downloaded PDF from URL: {pdf_url}")
        else:
            return {"success": False, "error": "Either pdf_file or pdf_url must be provided"}
        
        # Handle Audio input (file upload OR URL)
        audio_data = None
        audio_filename = None
        if audio_file is not None:
            audio_data = await audio_file.read()
            audio_filename = audio_file.filename or 'file.wav'
            print(f"Using uploaded audio file: {audio_filename}")
        elif audio_url:
            audio_data = download_file_from_url(audio_url)
            audio_filename = os.path.basename(audio_url) or 'file.wav'
            print(f"Downloaded audio from URL: {audio_url}")
        else:
            return {"success": False, "error": "Either audio_file or audio_url must be provided"}
        
        # Create temporary files
        if pdf_data is None:
            raise ValueError("pdf_data is None")
        pdf_ext = get_extension(str(pdf_filename or ''), '.pdf')
        with tempfile.NamedTemporaryFile(suffix=pdf_ext, delete=False) as pdf_temp:
            pdf_temp.write(pdf_data)
            pdf_path = pdf_temp.name
        
        if audio_data is None:
            raise ValueError("audio_data is None")
        audio_ext = get_extension(str(audio_filename or ''), '.wav')
        with tempfile.NamedTemporaryFile(suffix=audio_ext, delete=False) as audio_temp:
            audio_temp.write(audio_data)
            audio_path = audio_temp.name
        
        try:
            # Set environment variables
            os.environ['UPLOADS_DIR'] = '/tmp/uploads'
            
            # Process the files (simplified version)
            result = process_pdf_audio_simple(pdf_path, audio_path, transition_type, transition_duration)
            
            # Upload video to S3 and return the link
            if result.get("local_video_path") and os.path.exists(result["local_video_path"]):
                processing_time = time.time() - start_time
                
                # Upload to S3
                video_url = upload_to_s3(result["local_video_path"])
                
                # Return JSON with S3 link
                return {
                    "success": True,
                    "video_url": video_url,
                    "filename": "output.mp4",
                    "processing_time": processing_time,
                    "details": result.get("details", {}),
                    "input_method": {
                        "pdf": "file_upload" if pdf_file else "url",
                        "audio": "file_upload" if audio_file else "url"
                    }
                }
            else:
                return {
                    "success": False,
                    "error": "Video generation failed",
                    "details": result
                }
        
        finally:
            # Clean up temporary files
            os.unlink(pdf_path)
            os.unlink(audio_path)
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "processing_time": time.time() - start_time
        }

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
@modal.fastapi_endpoint(method="POST")
async def process_ppt_audio_flexible(
    ppt_file: UploadFile = File(None),
    audio_file: UploadFile = File(None),
    ppt_url: str = Form(None),
    audio_url: str = Form(None)
):
    """
    Flexible PowerPoint + Audio processing endpoint
    Accepts either file uploads OR URLs for both PPT and audio
    """
    import time
    from pathlib import Path
    
    start_time = time.time()
    
    try:
        # Handle PPT input (file upload OR URL)
        ppt_data = None
        ppt_filename = None
        if ppt_file is not None:
            ppt_data = await ppt_file.read()
            ppt_filename = ppt_file.filename or 'file.pptx'
            print(f"Using uploaded PPT file: {ppt_filename}")
        elif ppt_url:
            ppt_data = download_file_from_url(ppt_url)
            ppt_filename = os.path.basename(ppt_url) or 'file.pptx'
            print(f"Downloaded PPT from URL: {ppt_url}")
        else:
            return {"success": False, "error": "Either ppt_file or ppt_url must be provided"}
        
        # Handle Audio input (file upload OR URL)
        audio_data = None
        audio_filename = None
        if audio_file is not None:
            audio_data = await audio_file.read()
            audio_filename = audio_file.filename or 'file.wav'
            print(f"Using uploaded audio file: {audio_filename}")
        elif audio_url:
            audio_data = download_file_from_url(audio_url)
            audio_filename = os.path.basename(audio_url) or 'file.wav'
            print(f"Downloaded audio from URL: {audio_url}")
        else:
            return {"success": False, "error": "Either audio_file or audio_url must be provided"}
        
        # Create temporary files
        if ppt_data is None:
            raise ValueError("ppt_data is None")
        ppt_ext = get_extension(str(ppt_filename or ''), '.pptx')
        with tempfile.NamedTemporaryFile(suffix=ppt_ext, delete=False) as ppt_temp:
            ppt_temp.write(ppt_data)
            ppt_path = ppt_temp.name
        
        if audio_data is None:
            raise ValueError("audio_data is None")
        audio_ext = get_extension(str(audio_filename or ''), '.wav')
        with tempfile.NamedTemporaryFile(suffix=audio_ext, delete=False) as audio_temp:
            audio_temp.write(audio_data)
            audio_path = audio_temp.name
        
        try:
            # Set environment variables
            os.environ['UPLOADS_DIR'] = '/tmp/uploads'
            
            # Process the files (simplified version)
            result = process_ppt_audio_simple(ppt_path, audio_path)
            
            # Upload video to S3 and return the link
            if result.get("local_video_path") and os.path.exists(result["local_video_path"]):
                processing_time = time.time() - start_time
                
                # Upload to S3
                video_url = upload_to_s3(result["local_video_path"])
                
                # Return JSON with S3 link
                return {
                    "success": True,
                    "video_url": video_url,
                    "filename": "output.mp4",
                    "processing_time": processing_time,
                    "details": result.get("details", {}),
                    "input_method": {
                        "ppt": "file_upload" if ppt_file else "url",
                        "audio": "file_upload" if audio_file else "url"
                    }
                }
            else:
                return {
                    "success": False,
                    "error": "Video generation failed",
                    "details": result
                }
        
        finally:
            # Clean up temporary files
            os.unlink(ppt_path)
            os.unlink(audio_path)
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "processing_time": time.time() - start_time
        }

# Health check endpoint
@app.function(image=image, min_containers=1)
@modal.fastapi_endpoint(method="GET")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "pdf-to-video-api-flexible",
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
            "Flexible input methods",
            "File uploads OR URLs",
            "Optional fields",
            "Warm instances",
            "Extended timeouts"
        ]
    }

def process_pdf_audio_simple(pdf_path, audio_path, transition_type="fade", transition_duration=1.0):
    """Simplified PDF and audio processing for Modal with transitions"""
    import subprocess
    import time
    from pdf2image import convert_from_path
    from PIL import Image
    
    start_time = time.time()
    
    try:
        # Convert PDF to images
        print("Converting PDF to images...")
        images = convert_from_path(pdf_path, dpi=200)
        print(f"Converted {len(images)} pages")
        
        # Save images with even dimensions for H.264 compatibility
        for i, image in enumerate(images):
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Ensure even dimensions for H.264 compatibility
            width, height = image.size
            if height % 2 != 0:
                # Add 1 pixel to make height even
                new_image = Image.new('RGB', (width, height + 1))
                new_image.paste((255, 255, 255), (0, 0, width, height + 1))
                new_image.paste(image, (0, 0))
                image = new_image
                print(f"Adjusted page {i+1} height from {height} to {height + 1} for H.264 compatibility")
            
            img_filename = os.path.join('/tmp/uploads', f"page_{i+1}.png")
            image.save(img_filename, 'PNG')
            print(f"Saved page {i+1} with dimensions: {image.size}")
        
        # Get audio duration
        result = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration", 
            "-of", "default=noprint_wrappers=1:nokey=1", audio_path
        ], capture_output=True, text=True, check=True)
        audio_duration = float(result.stdout.strip())
        
        # Create simple video (show each page for equal duration)
        duration_per_page = audio_duration / len(images)
        
        # Create video with transitions using complex filter
        output_path = os.path.join('/tmp/uploads', 'output.mp4')
        
        # Build complex filter for transitions
        filter_complex = []
        inputs = []
        
        # Add all images as inputs
        for i in range(len(images)):
            img_path = os.path.join('/tmp/uploads', f"page_{i+1}.png")
            inputs.append(f"-loop 1 -t {duration_per_page} -i '{img_path}'")
        
        # Add audio input
        inputs.append(f"-i '{audio_path}'")
        
        # Use provided transition parameters
        transition_duration = min(transition_duration, duration_per_page * 0.5)  # Max 50% of slide duration
        transition_type = transition_type.lower()
        
        # Validate transition type
        valid_transitions = ["fade", "zoom", "slide", "slideleft", "slideright", "slideup", "slidedown"]
        if transition_type not in valid_transitions:
            transition_type = "fade"
        
        if len(images) == 1:
            # Single image, no transitions needed
            filter_complex.append(f"[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:white[v0]")
        else:
            # Multiple images with transitions
            for i in range(len(images)):
                # Scale and pad each image to 1920x1080
                filter_complex.append(f"[{i}:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:white[v{i}]")
            
            # Create transition chain
            if transition_type == "fade":
                # Fade transition
                for i in range(len(images) - 1):
                    if i == 0:
                        filter_complex.append(f"[v{i}][v{i+1}]xfade=transition=fade:duration={transition_duration}:offset={duration_per_page - transition_duration}[t{i+1}]")
                    else:
                        filter_complex.append(f"[t{i}][v{i+1}]xfade=transition=fade:duration={transition_duration}:offset={duration_per_page - transition_duration}[t{i+1}]")
                
                # Final output
                final_video = f"[t{len(images)-1}]"
                
            elif transition_type == "zoom":
                # Zoom transition
                for i in range(len(images) - 1):
                    if i == 0:
                        filter_complex.append(f"[v{i}][v{i+1}]xfade=transition=zoom:duration={transition_duration}:offset={duration_per_page - transition_duration}[t{i+1}]")
                    else:
                        filter_complex.append(f"[t{i}][v{i+1}]xfade=transition=zoom:duration={transition_duration}:offset={duration_per_page - transition_duration}[t{i+1}]")
                
                final_video = f"[t{len(images)-1}]"
                
            elif transition_type == "slide":
                # Slide transition
                for i in range(len(images) - 1):
                    if i == 0:
                        filter_complex.append(f"[v{i}][v{i+1}]xfade=transition=slideleft:duration={transition_duration}:offset={duration_per_page - transition_duration}[t{i+1}]")
                    else:
                        filter_complex.append(f"[t{i}][v{i+1}]xfade=transition=slideleft:duration={transition_duration}:offset={duration_per_page - transition_duration}[t{i+1}]")
                
                final_video = f"[t{len(images)-1}]"
        
        # Add audio processing
        audio_input_index = len(images)
        filter_complex.append(f"[{audio_input_index}:a]aformat=sample_rates=44100:channel_layouts=stereo[a]")
        
        # Final mapping
        if len(images) == 1:
            filter_complex.append(f"[v0][a]concat=n=1:v=1:a=1[outv][outa]")
        else:
            filter_complex.append(f"{final_video}[a]concat=n=1:v=1:a=1[outv][outa]")
        
        # Build ffmpeg command
        input_args = " ".join(inputs)
        filter_str = ";".join(filter_complex)
        
        ffmpeg_cmd = f"ffmpeg -y {input_args} -filter_complex '{filter_str}' -map '[outv]' -map '[outa]' -c:v libx264 -c:a aac -pix_fmt yuv420p -shortest '{output_path}'"
        
        print(f"FFmpeg command: {ffmpeg_cmd}")
        
        try:
            result = subprocess.run(ffmpeg_cmd, shell=True, capture_output=True, text=True, check=True)
            print("FFmpeg command executed successfully with transitions")
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg error: {e}")
            print(f"FFmpeg stdout: {e.stdout}")
            print(f"FFmpeg stderr: {e.stderr}")
            
            # Fallback to simple concat if complex filter fails
            print("Falling back to simple concat...")
            input_file = os.path.join('/tmp/uploads', 'input.txt')
            with open(input_file, 'w') as f:
                for i in range(len(images)):
                    img_path = os.path.join('/tmp/uploads', f"page_{i+1}.png")
                    f.write(f"file '{img_path}'\n")
                    f.write(f"duration {duration_per_page}\n")
                last_img_path = os.path.join('/tmp/uploads', f"page_{len(images)}.png")
                f.write(f"file '{last_img_path}'\n")
            
            subprocess.run([
                'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', input_file,
                '-i', audio_path, '-c:v', 'libx264', '-c:a', 'aac',
                '-pix_fmt', 'yuv420p', '-shortest', output_path
            ], check=True)
        
        processing_time = time.time() - start_time
        
        return {
            "success": True,
            "local_video_path": output_path,
            "details": {
                "pages_processed": len(images),
                "audio_duration": audio_duration,
                "processing_time": processing_time
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "processing_time": time.time() - start_time
        }

def process_ppt_audio_simple(ppt_path, audio_path):
    """Simplified PowerPoint and audio processing for Modal"""
    import subprocess
    import time
    from pptx import Presentation
    
    start_time = time.time()
    
    try:
        # Extract slides from PowerPoint
        print("Extracting slides from PowerPoint...")
        prs = Presentation(ppt_path)
        
        # For now, create a simple video with placeholder
        # In a full implementation, you'd extract images from slides
        
        # Get audio duration
        result = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration", 
            "-of", "default=noprint_wrappers=1:nokey=1", audio_path
        ], capture_output=True, text=True, check=True)
        audio_duration = float(result.stdout.strip())
        
        # Create a simple video (placeholder)
        output_path = os.path.join('/tmp/uploads', 'output.mp4')
        
        # For now, create a simple video with a black frame
        subprocess.run([
            'ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=black:size=1920x1080:duration=' + str(audio_duration),
            '-i', audio_path, '-c:v', 'libx264', '-c:a', 'aac',
            '-pix_fmt', 'yuv420p', '-shortest', output_path
        ], check=True)
        
        processing_time = time.time() - start_time
        
        return {
            "success": True,
            "local_video_path": output_path,
            "details": {
                "slides_processed": len(prs.slides),
                "audio_duration": audio_duration,
                "processing_time": processing_time
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "processing_time": time.time() - start_time
        }

if __name__ == "__main__":
    app.run() 