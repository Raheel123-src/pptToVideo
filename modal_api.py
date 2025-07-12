import os
import re
import json
import math
import subprocess
import requests
import urllib.parse
import time
import concurrent.futures
from tempfile import NamedTemporaryFile
from pdf2image import convert_from_path
from PIL import Image, ImageDraw, ImageFont
import whisper
import openai
from pdf_to_img_and_text import extract_text_openai
from pptx import Presentation
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
import uuid
from datetime import datetime, timedelta

# Pro tier configuration
UPLOADS_DIR = "/tmp/uploads"
CACHE_DIR = "/tmp/cache"
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# Enhanced font paths for Pro tier
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/arial.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/noto/NotoSansCJK-Regular.ttc"
]

def get_audio_duration(audio_path):
    """Get audio duration using ffprobe with Pro tier optimization"""
    try:
        result = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration", 
            "-of", "default=noprint_wrappers=1:nokey=1", audio_path
        ], capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
        return duration
    except (subprocess.CalledProcessError, ValueError) as e:
        print(f"Warning: Could not get audio duration with ffprobe: {e}")
        return 30.0

def upload_pdf_audio_internal_pro(pdf_path, audio_path):
    """Pro tier optimized PDF and audio processing"""
    start_time = time.time()
    
    try:
        # Set environment variables for Modal
        openai.api_key = os.getenv('OPENAI_API_KEY')
        
        # Enhanced PDF processing with parallel execution
        print("Starting PDF processing with Pro tier resources...")
        
        # Convert PDF to images with higher quality
        images = convert_from_path(
            pdf_path,
            dpi=300,  # Higher DPI for better quality
            thread_count=4  # Use all 4 CPU cores
        )
        print(f"Successfully converted PDF to {len(images)} images")
        
        page_texts = []
        
        # Process images in parallel for faster text extraction
        def process_page(args):
            i, image = args
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            width, height = image.size
            # Ensure height is even for h264 compatibility
            if height % 2 != 0:
                new_image = Image.new('RGB', (width, height + 1), (255, 255, 255))
                new_image.paste(image, (0, 0))
                image = new_image
            
            img_filename = os.path.join(UPLOADS_DIR, f"page_{i+1}.png")
            image.save(img_filename, 'PNG', quality=95)  # Higher quality
            
            try:
                text = extract_text_openai(image)
                print(f"Extracted text for page {i+1}")
            except Exception as e:
                print(f"Text extraction error for page {i+1}: {e}")
                try:
                    import pytesseract
                    text = pytesseract.image_to_string(image).strip()
                    if not text:
                        text = f"Page {i+1} content (text extraction failed)"
                except:
                    text = f"Page {i+1} content (text extraction failed)"
            
            txt_filename = os.path.join(UPLOADS_DIR, f"page_{i+1}.txt")
            with open(txt_filename, 'w', encoding='utf-8') as txt_file:
                txt_file.write(text)
            
            return text
        
        # Use ThreadPoolExecutor for parallel processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            page_texts = list(executor.map(process_page, enumerate(images)))
        
        # Enhanced audio transcription with larger model
        print("Starting audio transcription...")
        model = whisper.load_model("medium")  # Use medium model for better accuracy
        result = model.transcribe(audio_path, word_timestamps=True)
        segments = result["segments"]
        print(f"Successfully transcribed audio with {len(segments)} segments")
        
        # Combine all segment texts
        full_transcription = ' '.join([str(seg.get('text', '')) for seg in segments if isinstance(seg, dict)])
        sentences = re.split(r'(?<=[.!?])\s+', full_transcription.strip())
        sentences = [s.strip() for s in sentences if s.strip()]
        
        print(f"Extracted {len(sentences)} sentences from audio")
        print(f"Found {len(page_texts)} pages in PDF")
        
        # Get audio duration
        audio_duration = get_audio_duration(audio_path)
        
        # Enhanced mapping with GPT-4o analysis (Pro tier can afford more API calls)
        print("Creating intelligent content mapping...")
        
        # Use GPT-4o for better content analysis
        mapping_prompt = f"""
        Analyze this audio transcription and PDF content to create an intelligent mapping.
        
        Audio transcription:
        {full_transcription[:2000]}...
        
        PDF pages content:
        {json.dumps([{"page": i+1, "text": text[:500]} for i, text in enumerate(page_texts)], indent=2)}
        
        Create a mapping that matches audio content to the most relevant PDF pages.
        Return a JSON array with page numbers for each sentence.
        """
        
        try:
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert at matching audio content to document pages."},
                    {"role": "user", "content": mapping_prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            mapping_result = json.loads(response.choices[0].message.content)
            segment_to_page = mapping_result.get("mapping", [])
            
            # Ensure we have enough mappings
            while len(segment_to_page) < len(sentences):
                segment_to_page.append((len(segment_to_page) % len(page_texts)) + 1)
                
        except Exception as e:
            print(f"GPT mapping failed, using fallback: {e}")
            # Fallback mapping
            segment_to_page = [(i % len(page_texts)) + 1 for i in range(len(sentences))]
        
        # Create optimized video sequence
        print("Creating optimized video sequence...")
        used_pages = set()
        slide_sequence = []
        slide_durations = []
        
        for i, sentence in enumerate(sentences):
            mapped_page = segment_to_page[i]
            
            if mapped_page not in used_pages:
                slide_sequence.append(mapped_page)
                used_pages.add(mapped_page)
                
                sentence_count = segment_to_page.count(mapped_page)
                duration = (sentence_count / len(sentences)) * audio_duration
                slide_durations.append(duration)
        
        # Fill remaining time with unused pages
        remaining_pages = [p for p in range(1, len(page_texts) + 1) if p not in used_pages]
        remaining_time = audio_duration - sum(slide_durations)
        
        if remaining_pages and remaining_time > 0:
            time_per_remaining_slide = remaining_time / len(remaining_pages)
            for page in remaining_pages:
                slide_sequence.append(page)
                slide_durations.append(time_per_remaining_slide)
        
        # Create high-quality video with Pro tier resources
        print("Generating high-quality video...")
        ffmpeg_input_txt = os.path.join(UPLOADS_DIR, "single_video_input.txt")
        with open(ffmpeg_input_txt, 'w') as f:
            for i, (page_num, duration) in enumerate(zip(slide_sequence, slide_durations)):
                img_filename = f"page_{page_num}.png"
                f.write(f"file '{img_filename}'\n")
                f.write(f"duration {duration}\n")
            f.write(f"file 'page_{slide_sequence[-1]}.png'\n")
        
        # Generate video with higher quality settings
        video_path = os.path.join(UPLOADS_DIR, "output.mp4")
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "single_video_input.txt",
            "-vsync", "vfr", "-pix_fmt", "yuv420p", "-crf", "18",  # Higher quality
            "-preset", "medium",  # Balance between speed and quality
            "output.mp4"
        ], check=True, cwd=UPLOADS_DIR)
        
        # Combine with audio using high-quality settings
        final_video_path = os.path.join(UPLOADS_DIR, "final_output.mp4")
        subprocess.run([
            "ffmpeg", "-y", "-i", "output.mp4", "-i", audio_path, 
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",  # Higher audio quality
            "-shortest", "final_output.mp4"
        ], check=True, cwd=UPLOADS_DIR)
        
        processing_time = time.time() - start_time
        
        return {
            "local_video_path": final_video_path,
            "processing_time": processing_time,
            "details": {
                "total_slides": len(slide_sequence),
                "audio_duration": audio_duration,
                "slide_sequence": slide_sequence,
                "slide_durations": slide_durations,
                "quality": "pro_tier_enhanced"
            }
        }
        
    except Exception as e:
        print(f"Error in PDF processing: {e}")
        raise

def upload_ppt_audio_animate_internal_pro(pptx_path, audio_path):
    """Pro tier optimized PowerPoint and audio processing"""
    start_time = time.time()
    
    try:
        # Set environment variables for Modal
        openai.api_key = os.getenv('OPENAI_API_KEY')
        
        # Enhanced PowerPoint processing
        print("Starting PowerPoint processing with Pro tier resources...")
        
        # Extract PowerPoint content with parallel processing
        prs = Presentation(pptx_path)
        slides_content = []
        
        def process_slide(args):
            i, slide = args
            slide_data = {
                'slide_number': i + 1,
                'shapes': [],
                'text_content': [],
                'images': []
            }
            
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    slide_data['shapes'].append({
                        'text': shape.text.strip(),
                        'shape_type': str(type(shape).__name__)
                    })
                    slide_data['text_content'].append(shape.text.strip())
                
                # Extract images if present
                if hasattr(shape, 'image'):
                    try:
                        image_stream = shape.image.blob
                        slide_data['images'].append({
                            'data': image_stream,
                            'type': 'image'
                        })
                    except:
                        pass
            
            return slide_data
        
        # Process slides in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            slides_content = list(executor.map(process_slide, enumerate(prs.slides)))
        
        # Enhanced audio transcription
        print("Starting audio transcription...")
        model = whisper.load_model("medium")
        result = model.transcribe(audio_path, word_timestamps=True)
        segments = result["segments"]
        
        full_transcription = ' '.join([str(seg.get('text', '')) for seg in segments if isinstance(seg, dict)])
        sentences = re.split(r'(?<=[.!?])\s+', full_transcription.strip())
        sentences = [s.strip() for s in sentences if s.strip()]
        
        print(f"Extracted {len(sentences)} sentences from audio")
        print(f"Found {len(slides_content)} slides in PPTX")
        
        # Get audio duration
        audio_duration = get_audio_duration(audio_path)
        
        # Enhanced mapping with GPT analysis
        print("Creating intelligent slide mapping...")
        
        mapping_prompt = f"""
        Analyze this audio transcription and PowerPoint content to create an intelligent mapping.
        
        Audio transcription:
        {full_transcription[:2000]}...
        
        PowerPoint slides:
        {json.dumps([{"slide": i+1, "content": slide['text_content'][:3]} for i, slide in enumerate(slides_content)], indent=2)}
        
        Create a mapping that matches audio content to the most relevant slides.
        Return a JSON array with slide numbers for each sentence.
        """
        
        try:
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert at matching audio content to presentation slides."},
                    {"role": "user", "content": mapping_prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            mapping_result = json.loads(response.choices[0].message.content)
            segment_to_slide = mapping_result.get("mapping", [])
            
            while len(segment_to_slide) < len(sentences):
                segment_to_slide.append((len(segment_to_slide) % len(slides_content)) + 1)
                
        except Exception as e:
            print(f"GPT mapping failed, using fallback: {e}")
            segment_to_slide = [(i % len(slides_content)) + 1 for i in range(len(sentences))]
        
        # Create optimized slide sequence
        print("Creating optimized slide sequence...")
        used_slides = set()
        slide_sequence = []
        slide_durations = []
        
        for i, sentence in enumerate(sentences):
            mapped_slide = segment_to_slide[i]
            
            if mapped_slide not in used_slides:
                slide_sequence.append(mapped_slide)
                used_slides.add(mapped_slide)
                
                sentence_count = segment_to_slide.count(mapped_slide)
                duration = (sentence_count / len(sentences)) * audio_duration
                slide_durations.append(duration)
        
        # Fill remaining time
        remaining_slides = [s for s in range(1, len(slides_content) + 1) if s not in used_slides]
        remaining_time = audio_duration - sum(slide_durations)
        
        if remaining_slides and remaining_time > 0:
            time_per_remaining_slide = remaining_time / len(remaining_slides)
            for slide in remaining_slides:
                slide_sequence.append(slide)
                slide_durations.append(time_per_remaining_slide)
        
        # Create enhanced slide images
        print("Generating enhanced slide images...")
        for i, slide_num in enumerate(slide_sequence):
            slide_content = slides_content[slide_num - 1]
            
            # Create high-quality slide image
            img = Image.new('RGB', (1920, 1080), color=(255, 255, 255))
            draw = ImageDraw.Draw(img)
            
            # Use enhanced font
            font = None
            for font_path in FONT_PATHS:
                try:
                    font = ImageFont.truetype(font_path, 48)
                    break
                except:
                    continue
            
            if font is None:
                font = ImageFont.load_default()
            
            # Add slide title
            title = f"Slide {slide_num}"
            bbox = draw.textbbox((0, 0), title, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            x = (1920 - text_width) // 2
            y = 100
            
            draw.text((x, y), title, fill=(0, 0, 0), font=font)
            
            # Add slide content
            if slide_content['text_content']:
                content_font = ImageFont.truetype(font_path, 32) if font_path else ImageFont.load_default()
                y_offset = 200
                
                for text in slide_content['text_content'][:5]:  # Limit to 5 text elements
                    # Wrap text
                    words = text.split()
                    lines = []
                    current_line = []
                    
                    for word in words:
                        current_line.append(word)
                        test_line = ' '.join(current_line)
                        bbox = draw.textbbox((0, 0), test_line, font=content_font)
                        if bbox[2] - bbox[0] > 1800:  # Wrap at 1800px
                            current_line.pop()
                            lines.append(' '.join(current_line))
                            current_line = [word]
                    
                    if current_line:
                        lines.append(' '.join(current_line))
                    
                    # Draw lines
                    for line in lines:
                        if y_offset > 900:  # Don't overflow
                            break
                        draw.text((100, y_offset), line, fill=(50, 50, 50), font=content_font)
                        y_offset += 40
                    
                    y_offset += 20
            
            img_filename = os.path.join(UPLOADS_DIR, f"slide_{slide_num}.png")
            img.save(img_filename, 'PNG', quality=95)
        
        # Create high-quality video
        print("Generating high-quality PowerPoint video...")
        ffmpeg_input_txt = os.path.join(UPLOADS_DIR, "ppt_video_input.txt")
        with open(ffmpeg_input_txt, 'w') as f:
            for i, (slide_num, duration) in enumerate(zip(slide_sequence, slide_durations)):
                img_filename = f"slide_{slide_num}.png"
                f.write(f"file '{img_filename}'\n")
                f.write(f"duration {duration}\n")
            f.write(f"file 'slide_{slide_sequence[-1]}.png'\n")
        
        # Generate video with high quality
        video_path = os.path.join(UPLOADS_DIR, "ppt_output.mp4")
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "ppt_video_input.txt",
            "-vsync", "vfr", "-pix_fmt", "yuv420p", "-crf", "18",
            "-preset", "medium", "ppt_output.mp4"
        ], check=True, cwd=UPLOADS_DIR)
        
        # Combine with audio
        final_video_path = os.path.join(UPLOADS_DIR, "ppt_final_output.mp4")
        subprocess.run([
            "ffmpeg", "-y", "-i", "ppt_output.mp4", "-i", audio_path, 
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", "ppt_final_output.mp4"
        ], check=True, cwd=UPLOADS_DIR)
        
        processing_time = time.time() - start_time
        
        return {
            "local_video_path": final_video_path,
            "processing_time": processing_time,
            "details": {
                "total_slides": len(slide_sequence),
                "audio_duration": audio_duration,
                "slide_sequence": slide_sequence,
                "slide_durations": slide_durations,
                "quality": "pro_tier_enhanced"
            }
        }
        
    except Exception as e:
        print(f"Error in PowerPoint processing: {e}")
        raise 