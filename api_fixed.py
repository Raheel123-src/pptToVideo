import os
import re
import json
import math
import subprocess
from tempfile import NamedTemporaryFile
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime

# Initialize FastAPI app
app = FastAPI()

# Basic health endpoints
@app.get("/")
async def root():
    return {"message": "PDF to Video API is running!", "timestamp": datetime.now().isoformat()}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# Test endpoint to check imports
@app.get("/test-imports")
async def test_imports():
    try:
        # Test basic imports
        from pdf2image import convert_from_path
        from PIL import Image, ImageDraw, ImageFont
        from dotenv import load_dotenv
        import openai
        from pptx import Presentation
        import boto3
        
        # Test optional imports
        try:
            import whisper
            whisper_status = "✅ Whisper imported successfully"
        except Exception as e:
            whisper_status = f"❌ Whisper import failed: {str(e)}"
        
        try:
            from pdf_to_img_and_text import extract_text_openai
            pdf_status = "✅ PDF module imported successfully"
        except Exception as e:
            pdf_status = f"❌ PDF module import failed: {str(e)}"
        
        return {
            "status": "success",
            "basic_imports": "✅ All basic imports successful",
            "whisper": whisper_status,
            "pdf_module": pdf_status,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

# Simple file upload test
@app.post("/test-upload")
async def test_upload(file: UploadFile = File(...)):
    try:
        # Just check if file upload works
        contents = await file.read()
        return {
            "filename": file.filename,
            "size": len(contents),
            "content_type": file.content_type,
            "status": "upload_successful"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload test failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 