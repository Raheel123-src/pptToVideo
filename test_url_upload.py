#!/usr/bin/env python3
"""
Test script for the new URL upload functionality
"""

import requests
import json

# Replace with your actual Render app URL
BASE_URL = "https://your-render-app.onrender.com"

def test_file_upload():
    """Test traditional file upload"""
    print("Testing file upload...")
    
    files = {
        'pdf': open('test.pdf', 'rb'),
        'audio': open('test.mp3', 'rb')
    }
    
    response = requests.post(f"{BASE_URL}/upload-pdf-audio/", files=files)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    files['pdf'].close()
    files['audio'].close()

def test_url_upload():
    """Test URL upload"""
    print("\nTesting URL upload...")
    
    data = {
        'pdf_url': 'https://example.com/document.pdf',
        'audio_url': 'https://example.com/audio.mp3'
    }
    
    response = requests.post(f"{BASE_URL}/upload-pdf-audio/", data=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

def test_mixed_upload():
    """Test mixed upload (file + URL)"""
    print("\nTesting mixed upload...")
    
    files = {'pdf': open('test.pdf', 'rb')}
    data = {'audio_url': 'https://example.com/audio.mp3'}
    
    response = requests.post(f"{BASE_URL}/upload-pdf-audio/", files=files, data=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    files['pdf'].close()

def test_google_drive():
    """Test Google Drive URL"""
    print("\nTesting Google Drive URL...")
    
    # Example Google Drive URLs
    google_drive_pdf = "https://drive.google.com/file/d/1ABC123XYZ/view?usp=sharing"
    google_drive_audio = "https://drive.google.com/file/d/1DEF456UVW/view?usp=sharing"
    
    data = {
        'pdf_url': google_drive_pdf,
        'audio_url': google_drive_audio
    }
    
    response = requests.post(f"{BASE_URL}/upload-pdf-audio/", data=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

def test_s3_url():
    """Test S3 URL"""
    print("\nTesting S3 URL...")
    
    # Example S3 URLs
    s3_pdf = "https://my-bucket.s3.amazonaws.com/documents/report.pdf"
    s3_audio = "https://my-bucket.s3.amazonaws.com/audio/narration.mp3"
    
    data = {
        'pdf_url': s3_pdf,
        'audio_url': s3_audio
    }
    
    response = requests.post(f"{BASE_URL}/upload-pdf-audio/", data=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

if __name__ == "__main__":
    print("Testing PDF to Video API with URL support")
    print("=" * 50)
    
    # Uncomment the tests you want to run
    # test_file_upload()
    # test_url_upload()
    # test_mixed_upload()
    # test_google_drive()
    # test_s3_url()
    
    print("\nTo run tests, uncomment the test functions above and update BASE_URL") 