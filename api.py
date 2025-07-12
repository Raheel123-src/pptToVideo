import os
import re
import json
import math
import subprocess
from tempfile import NamedTemporaryFile
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from pdf2image import convert_from_path
from PIL import Image, ImageDraw, ImageFont
from pydub import AudioSegment
from dotenv import load_dotenv
import whisper
import openai
from pdf_to_img_and_text import extract_text_openai
from pptx import Presentation

load_dotenv()
UPLOADS_DIR = os.getenv('UPLOADS_DIR', 'uploads')
os.makedirs(UPLOADS_DIR, exist_ok=True)

def extract_slide_images_with_python(pptx_path, slide_num):
    """Extract slide images using Python-based approach (fallback when GPT fails)."""
    try:
        from pptx import Presentation
        from PIL import Image, ImageDraw, ImageFont
        import io
        
        # Load the presentation
        prs = Presentation(pptx_path)
        
        if slide_num < 1 or slide_num > len(prs.slides):
            raise Exception(f"Slide {slide_num} does not exist. Presentation has {len(prs.slides)} slides.")
        
        # Get the specific slide (0-indexed)
        slide = prs.slides[slide_num - 1]
        
        # Get slide dimensions (default to 1920x1080 if not specified)
        slide_width = int(prs.slide_width * 96 / 914400) if prs.slide_width else 1920  # Convert EMU to pixels
        slide_height = int(prs.slide_height * 96 / 914400) if prs.slide_height else 1080  # Convert EMU to pixels
        
        if slide_width == 0 or slide_height == 0:
            slide_width, slide_height = 1920, 1080
        
        # Create a white background image
        img = Image.new('RGB', (slide_width, slide_height), color=0xFFFFFF)
        draw = ImageDraw.Draw(img)
        
        # Try to use a default font
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 24)
        except:
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
            except:
                font = ImageFont.load_default()
        
        # Process each shape in the slide
        for shape in slide.shapes:
            try:
                # Handle text shapes
                if hasattr(shape, 'text') and getattr(shape, 'text', '').strip():
                    # Get shape position and size
                    left = int(shape.left * 96 / 914400)
                    top = int(shape.top * 96 / 914400)
                    width = int(shape.width * 96 / 914400)
                    height = int(shape.height * 96 / 914400)
                    
                    # Draw text
                    draw.text((left, top), getattr(shape, 'text', ''), fill=(0, 0, 0), font=font)
                
                # Handle image shapes
                elif hasattr(shape, 'image'):
                    try:
                        # Get image data
                        image_stream = getattr(shape, 'image').blob
                        image_data = Image.open(io.BytesIO(image_stream))
                        
                        # Get position and size
                        left = int(shape.left * 96 / 914400)
                        top = int(shape.top * 96 / 914400)
                        width = int(shape.width * 96 / 914400)
                        height = int(shape.height * 96 / 914400)
                        
                        # Resize and paste image
                        image_data = image_data.resize((width, height))
                        img.paste(image_data, (left, top))
                    except Exception as e:
                        print(f"Warning: Could not process image shape: {e}")
                        continue
                
                # Handle other shapes (rectangles, etc.)
                elif hasattr(shape, 'shape_type'):
                    try:
                        left = int(shape.left * 96 / 914400)
                        top = int(shape.top * 96 / 914400)
                        width = int(shape.width * 96 / 914400)
                        height = int(shape.height * 96 / 914400)
                        
                        # Draw a simple rectangle
                        draw.rectangle([left, top, left + width, top + height], 
                                     outline=(0, 0, 0), fill=(240, 240, 240))
                    except Exception as e:
                        print(f"Warning: Could not process shape: {e}")
                        continue
                        
            except Exception as e:
                print(f"Warning: Could not process shape: {e}")
                continue
        
        # Save the image
        filename = f"slide_{slide_num}_python.png"
        filepath = os.path.join(UPLOADS_DIR, filename)
        img.save(filepath, 'PNG')
        
        print(f"Extracted slide {slide_num} using Python: {filepath}")
        return [filepath]
        
    except Exception as e:
        raise Exception(f"Python-based extraction failed for slide {slide_num}: {e}")

def extract_slide_images_with_gpt(pptx_path, slide_num):
    """
    Use GPT-4o to extract actual rendered slide images from PowerPoint file.
    This preserves all fonts, images, and formatting exactly as they appear.
    """
    import base64
    
    # Read the PowerPoint file as base64
    with open(pptx_path, 'rb') as f:
        pptx_data = f.read()
    pptx_base64 = base64.b64encode(pptx_data).decode('utf-8')
    
    # Create a comprehensive prompt for GPT to extract slide images
    gpt_prompt = f"""
    You are an expert at extracting PowerPoint slide images with perfect accuracy.
    
    I have provided you with a PowerPoint file (base64 encoded). Please extract slide {slide_num} and create the following images:

    1. **Initial State (Before Animations)**: 
       - Filename: slide_{slide_num:02d}_before.png
       - Show the slide exactly as it appears when first displayed, before any animations trigger
       - Include all text, images, shapes, and formatting exactly as rendered in PowerPoint
       - Preserve all fonts, colors, sizes, and positioning

    2. **Final State (After All Animations)**:
       - Filename: slide_{slide_num:02d}_after.png  
       - Show the slide after all animations have completed
       - Display all elements in their final animated state
       - Maintain exact visual fidelity to PowerPoint rendering

    3. **Animation Transition States** (if animations exist):
       - For each animation step, create an image showing the slide at that specific moment
       - Filename pattern: slide_{slide_num:02d}_transition_X.png (where X is the transition number)
       - Capture the exact visual state at each animation transition

    Requirements:
    - Extract the actual rendered images from the PowerPoint file
    - Preserve ALL visual elements: fonts, images, shapes, colors, positioning
    - Maintain exact pixel-perfect accuracy to PowerPoint rendering
    - Use high resolution (1920x1080 or higher)
    - Save as PNG format with transparency support
    - Do NOT recreate or redraw elements - extract the actual rendered images

    PowerPoint File (base64): {pptx_base64}
    
    Please return a JSON object with:
    {{
        "slide_{slide_num}_before": "base64_encoded_png_data",
        "slide_{slide_num}_after": "base64_encoded_png_data", 
        "slide_{slide_num}_transition_1": "base64_encoded_png_data",
        "slide_{slide_num}_transition_2": "base64_encoded_png_data",
        ...
        "total_transitions": number_of_transitions_found
    }}
    """
    
    try:
        # Call GPT-4o to extract the actual slide images
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert PowerPoint slide image extractor. Your job is to extract actual rendered images from PowerPoint files with perfect accuracy, preserving all fonts, images, and formatting exactly as they appear in PowerPoint."},
                {"role": "user", "content": gpt_prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # Parse the response
        response_content = response.choices[0].message.content
        if not response_content:
            raise Exception("Empty response from GPT")
        response_data = json.loads(response_content)
        
        extracted_images = []
        
        # Save each extracted image
        for key, base64_data in response_data.items():
            if key.startswith(f"slide_{slide_num}") and base64_data:
                try:
                    # Decode and save the image
                    image_data = base64.b64decode(base64_data)
                    filename = f"{key}.png"
                    filepath = os.path.join(UPLOADS_DIR, filename)
                    
                    with open(filepath, 'wb') as f:
                        f.write(image_data)
                    
                    extracted_images.append(filepath)
                    print(f"Extracted {key}: {filepath}")
                    
                except Exception as e:
                    raise Exception(f"Error saving {key}: {e}")
        
        return extracted_images
        
    except openai.BadRequestError as e:
        if "string too long" in str(e):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "FILE_TOO_LARGE",
                    "message": "PowerPoint file is too large for GPT processing. Please use a smaller file (under 10MB).",
                    "gpt_error": str(e)
                }
            )
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "GPT_BAD_REQUEST",
                    "message": "Invalid request to GPT API",
                    "gpt_error": str(e)
                }
            )
    except openai.AuthenticationError as e:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "GPT_AUTH_ERROR",
                "message": "Authentication failed with GPT API. Please check your API key.",
                "gpt_error": str(e)
            }
        )
    except openai.RateLimitError as e:
        # Check if it's a file size issue (tokens per min limit)
        if "Request too large" in str(e) or "tokens per min" in str(e):
            print(f"File too large for GPT-4o, falling back to Python-based extraction: {e}")
            # Fall back to Python-based extraction
            return extract_slide_images_with_python(pptx_path, slide_num)
        else:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "GPT_RATE_LIMIT",
                    "message": "Rate limit exceeded for GPT API. Please try again later.",
                    "gpt_error": str(e)
                }
            )
    except openai.APIError as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "GPT_API_ERROR",
                "message": "GPT API error occurred",
                "gpt_error": str(e)
            }
        )
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INVALID_JSON_RESPONSE",
                "message": "Invalid JSON response from GPT",
                "gpt_error": str(e)
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "EXTRACTION_FAILED",
                "message": f"Failed to extract slide {slide_num}",
                "gpt_error": str(e)
            }
        )

def validate_pptx_file_size(pptx_path):
    """Validate that the PowerPoint file is not too large for GPT processing."""
    file_size = os.path.getsize(pptx_path)
    max_size = 25 * 1024 * 1024  # 25MB limit for GPT-4o
    
    if file_size > max_size:
        raise HTTPException(
            status_code=400, 
            detail={
                "error": "FILE_TOO_LARGE",
                "message": f"PowerPoint file is too large ({file_size / 1024 / 1024:.1f}MB). Maximum size is 25MB.",
                "file_size_mb": round(file_size / 1024 / 1024, 1),
                "max_size_mb": 25
            }
        )

app = FastAPI()

@app.post("/upload-pdf-audio/")
async def upload_pdf_audio(pdf: UploadFile = File(...), audio: UploadFile = File(...)):
    if not pdf.filename or not pdf.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")
    if not audio.filename or not (audio.filename.lower().endswith('.mp3') or audio.filename.lower().endswith('.wav') or audio.filename.lower().endswith('.m4a')):
        raise HTTPException(status_code=400, detail="Only audio files (.mp3, .wav, .m4a) are allowed.")
    try:
        # Save PDF
        with NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_pdf:
            tmp_pdf.write(await pdf.read())
            pdf_path = tmp_pdf.name
        # Save audio
        with NamedTemporaryFile(delete=False, suffix=os.path.splitext(audio.filename)[-1]) as tmp_audio:
            tmp_audio.write(await audio.read())
            audio_path = tmp_audio.name
        # PDF to images and GPT-4o text
        images = convert_from_path(pdf_path)
        page_texts = []
        for i, image in enumerate(images):
            if image.mode != 'RGB':
                image = image.convert('RGB')
            width, height = image.size
            # Ensure height is even for h264 compatibility
            if height % 2 != 0:
                # Create a new image with even height
                new_image = Image.new('RGB', (width, height + 1), (255, 255, 255))
                new_image.paste(image, (0, 0))
                image = new_image
            img_filename = os.path.join(UPLOADS_DIR, f"page_{i+1}.png")
            image.save(img_filename, 'PNG')
            text = extract_text_openai(image)
            print(f"Extracted text for page {i+1}:\n{text}\n{'-'*40}")
            txt_filename = os.path.join(UPLOADS_DIR, f"page_{i+1}.txt")
            with open(txt_filename, 'w', encoding='utf-8') as txt_file:
                txt_file.write(text)
            page_texts.append(text)
        # Audio transcription with segments
        model = whisper.load_model("base")
        result = model.transcribe(audio_path, word_timestamps=True)
        segments = result["segments"]
        # Combine all segment texts into one transcription
        full_transcription = ' '.join([str(seg.get('text', '')) for seg in segments if isinstance(seg, dict)])
        # Split transcription into sentences using regex
        sentences = re.split(r'(?<=[.!?])\s+', full_transcription.strip())
        sentences = [s.strip() for s in sentences if s.strip()]
        
        print(f"Extracted {len(sentences)} sentences from audio")
        print(f"Found {len(page_texts)} pages in PDF")
        
        # Use GPT-4o mini to analyze content and create mapping plan
        openai.api_key = os.getenv('OPENAI_API_KEY')
        
        # First, get a high-level analysis of the audio content
        audio_analysis_prompt = f"""
        Analyze this audio transcription and break it down into logical sections that would correspond to different pages or page elements.
        
        Audio transcription:
        {full_transcription}
        
        Return a JSON array where each element contains:
        - "section": A brief description of what this section covers
        - "sentences": Array of sentence indices (0-based) that belong to this section
        - "key_topics": Array of key topics or concepts mentioned
        
        Focus on natural breaks in the content and logical groupings.
        """
        
        audio_analysis_response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert at analyzing presentation content and matching it to page structures."},
                {"role": "user", "content": audio_analysis_prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # Parse audio sections with error handling
        audio_content = audio_analysis_response.choices[0].message.content
        print(f"Raw audio analysis response: {audio_content}")
        
        try:
            if audio_content:
                audio_sections = json.loads(audio_content)
            else:
                audio_sections = []
        except json.JSONDecodeError as e:
            print(f"Failed to parse audio sections JSON: {e}")
            audio_sections = []
        
        # Now analyze PDF content
        pdf_analysis_prompt = f"""
        Analyze this PDF document structure and provide a detailed breakdown of each page's content and purpose.
        
        Pages content:
        {json.dumps([{"page_number": i+1, "text": text} for i, text in enumerate(page_texts)], indent=2)}
        
        Return a JSON array where each element contains:
        - "page_number": The page number (1-based)
        - "main_topic": The main topic or theme of this page
        - "key_elements": Array of key text elements on this page
        - "purpose": What this page is trying to communicate
        - "content_summary": A brief summary of the page's content
        """
        
        pdf_analysis_response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert at analyzing PDF documents and understanding their structure."},
                {"role": "user", "content": pdf_analysis_prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # Parse PDF pages with error handling
        pdf_content = pdf_analysis_response.choices[0].message.content
        print(f"Raw PDF analysis response: {pdf_content}")
        
        try:
            if pdf_content:
                pdf_pages = json.loads(pdf_content)
            else:
                pdf_pages = []
        except json.JSONDecodeError as e:
            print(f"Failed to parse PDF pages JSON: {e}")
            pdf_pages = []
        
        # Create detailed mapping plan using GPT-4o mini
        mapping_plan_prompt = f"""
        Create a detailed mapping plan that matches audio sections to PDF pages.
        
        Audio sections: {json.dumps(audio_sections, indent=2)}
        PDF pages: {json.dumps(pdf_pages, indent=2)}
        
        Rules:
        1. Each audio section should be matched to the most relevant page
        2. If the context doesn't change significantly, keep the same page active
        3. Only transition to a new page when the audio content clearly moves to a new topic
        4. For each sentence, specify which page should be shown
        
        Return a JSON array where each element contains:
        - "sentence_index": Index of the sentence (0-based)
        - "sentence_text": The actual sentence text
        - "page_number": Which page should be shown (1-based)
        - "transition_type": "new_page", "same_page", or "content_reveal"
        - "reasoning": Brief explanation of why this match was chosen
        """
        
        mapping_plan_response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert at creating synchronized presentations where audio content drives page transitions."},
                {"role": "user", "content": mapping_plan_prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # Parse mapping plan with error handling
        mapping_plan_content = mapping_plan_response.choices[0].message.content
        print(f"Raw mapping plan response: {mapping_plan_content}")
        
        try:
            if mapping_plan_content:
                parsed_content = json.loads(mapping_plan_content)
                # Handle nested structure where mapping_plan, content_mapping, or page_mapping is a key
                if isinstance(parsed_content, dict):
                    if "mapping_plan" in parsed_content:
                        mapping_plan = parsed_content["mapping_plan"]
                    elif "content_mapping" in parsed_content:
                        mapping_plan = parsed_content["content_mapping"]
                    elif "page_mapping" in parsed_content:
                        mapping_plan = parsed_content["page_mapping"]
                    else:
                        mapping_plan = []
                elif isinstance(parsed_content, list):
                    mapping_plan = parsed_content
                else:
                    mapping_plan = []
            else:
                mapping_plan = []
        except json.JSONDecodeError as e:
            print(f"Failed to parse mapping plan JSON: {e}")
            print(f"Raw content: {mapping_plan_content}")
            # Fallback: create a simple mapping plan
            mapping_plan = []
            for i, sentence in enumerate(sentences):
                # Simple fallback: cycle through pages
                page_num = (i % len(page_texts)) + 1
                mapping_plan.append({
                    "sentence_index": i,
                    "sentence_text": sentence,
                    "page_number": page_num,
                    "transition_type": "new_page" if i == 0 or (i > 0 and mapping_plan[i-1]["page_number"] != page_num) else "same_page",
                    "reasoning": "Fallback mapping"
                })
        
        # Ensure the mapping plan covers all sentences
        if len(mapping_plan) < len(sentences):
            print(f"Warning: Mapping plan only covers {len(mapping_plan)} sentences, but there are {len(sentences)} sentences")
            # Extend the mapping plan to cover all sentences
            for i in range(len(mapping_plan), len(sentences)):
                # Use intelligent cycling through pages
                if mapping_plan:
                    last_page = mapping_plan[-1]["page_number"]
                    next_page = (last_page % len(page_texts)) + 1
                else:
                    next_page = 1
                
                mapping_plan.append({
                    "sentence_index": i,
                    "sentence_text": sentences[i] if i < len(sentences) else "",
                    "page_number": next_page,
                    "transition_type": "new_page" if i == 0 or (i > 0 and mapping_plan[i-1]["page_number"] != next_page) else "same_page",
                    "reasoning": "Extended mapping to cover all sentences"
                })
        
        # Extract page numbers from mapping plan
        segment_to_page = []
        for item in mapping_plan:
            if isinstance(item, dict) and "page_number" in item:
                segment_to_page.append(item["page_number"])
            else:
                # Fallback if structure is unexpected
                segment_to_page.append(1)
        
        # Ensure we have a mapping for each sentence
        while len(segment_to_page) < len(sentences):
            # Use intelligent fallback: cycle through pages or use the last mapped page
            if segment_to_page:
                last_page = segment_to_page[-1]
                # Try to cycle to next page, but stay within bounds
                next_page = (last_page % len(page_texts)) + 1
                segment_to_page.append(next_page)
            else:
                segment_to_page.append(1)
        
        print(f"Created mapping for {len(segment_to_page)} sentences to {len(page_texts)} pages")
        print(f"Page distribution: {[segment_to_page.count(i+1) for i in range(len(page_texts))]}")
        
        # Clean segment_to_page to ensure no None values and valid page numbers
        cleaned_segment_to_page = []
        for i, page_num in enumerate(segment_to_page):
            if page_num is None or page_num < 1 or page_num > len(page_texts):
                page_num = segment_to_page[i-1] if i > 0 and segment_to_page[i-1] else 1
            cleaned_segment_to_page.append(page_num)
        segment_to_page = cleaned_segment_to_page
        
        # Save detailed mapping plan
        mapping_filename = os.path.join(UPLOADS_DIR, "detailed_mapping_plan.json")
        with open(mapping_filename, 'w', encoding='utf-8') as f:
            json.dump(mapping_plan, f, ensure_ascii=False, indent=2)
        
        # Save simple segment-to-page mapping (for backward compatibility)
        simple_mapping_filename = os.path.join(UPLOADS_DIR, "sentence_to_page.json")
        with open(simple_mapping_filename, 'w', encoding='utf-8') as f:
            json.dump(segment_to_page, f, ensure_ascii=False, indent=2)
        # Create ONE single video with NO slide repetition and proper audio sync
        print("Creating ONE single video with NO slide repetition...")
        
        # Get audio duration
        audio = AudioSegment.from_file(audio_path)
        audio_duration = len(audio) / 1000.0
        
        # Create optimal slide sequence with NO repetition
        # Use each page only once in the best order for content
        used_pages = set()
        slide_sequence = []
        slide_durations = []
        
        # First pass: use mapped pages in order, but only if not used
        for i, sentence in enumerate(sentences):
            mapped_page = segment_to_page[i]
            
            if mapped_page not in used_pages:
                # Use this page for the first time
                slide_sequence.append(mapped_page)
                used_pages.add(mapped_page)
                
                # Calculate duration for this slide based on how many sentences map to it
                sentence_count = segment_to_page.count(mapped_page)
                duration = (sentence_count / len(sentences)) * audio_duration
                slide_durations.append(duration)
                
                print(f"Slide {len(slide_sequence)}: Page {mapped_page} for {duration:.2f}s ({sentence_count} sentences)")
        
        # Second pass: fill remaining time with unused pages
        remaining_pages = [p for p in range(1, len(page_texts) + 1) if p not in used_pages]
        remaining_time = audio_duration - sum(slide_durations)
        
        if remaining_pages and remaining_time > 0:
            time_per_remaining_slide = remaining_time / len(remaining_pages)
            for page in remaining_pages:
                slide_sequence.append(page)
                slide_durations.append(time_per_remaining_slide)
                print(f"Slide {len(slide_sequence)}: Page {page} for {time_per_remaining_slide:.2f}s (remaining)")
        
        print(f"Final sequence: {slide_sequence}")
        print(f"Durations: {[f'{d:.2f}s' for d in slide_durations]}")
        
        # Create ONE single video with the optimal sequence
        ffmpeg_input_txt = os.path.join(UPLOADS_DIR, "single_video_input.txt")
        with open(ffmpeg_input_txt, 'w') as f:
            for i, (page_num, duration) in enumerate(zip(slide_sequence, slide_durations)):
                img_filename = f"page_{page_num}.png"
                f.write(f"file '{img_filename}'\n")
                f.write(f"duration {duration}\n")
            # Add the last slide again to ensure proper duration
            f.write(f"file 'page_{slide_sequence[-1]}.png'\n")
        
        # Generate the single video
        video_path = os.path.join(UPLOADS_DIR, "output.mp4")
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "single_video_input.txt",
            "-vsync", "vfr", "-pix_fmt", "yuv420p", "output.mp4"
        ], check=True, cwd=UPLOADS_DIR)
        
        # Combine video with audio
        final_video_path = os.path.join(UPLOADS_DIR, "final_output.mp4")
        subprocess.run([
            "ffmpeg", "-y", "-i", "output.mp4", "-i", audio_path, 
            "-c:v", "copy", "-c:a", "aac", "-shortest", "final_output.mp4"
        ], check=True, cwd=UPLOADS_DIR)
        
        # Save slide sequence information
        sequence_info = {
            'total_slides': len(slide_sequence),
            'audio_duration': audio_duration,
            'slide_sequence': slide_sequence,
            'slide_durations': slide_durations,
            'slides': [
                {
                    'slide_index': i,
                    'page_number': page_num,
                    'duration': duration,
                    'start_time': sum(slide_durations[:i]),
                    'end_time': sum(slide_durations[:i+1])
                }
                for i, (page_num, duration) in enumerate(zip(slide_sequence, slide_durations))
            ]
        }
        
        sequence_filename = os.path.join(UPLOADS_DIR, "slide_sequence_info.json")
        with open(sequence_filename, 'w', encoding='utf-8') as f:
            json.dump(sequence_info, f, ensure_ascii=False, indent=2)
        return JSONResponse({"message": f"Processed PDF and audio. Text, images, and video saved to '{UPLOADS_DIR}'."})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-ppt-audio-animate/")
async def upload_ppt_audio_animate(ppt: UploadFile = File(...), audio: UploadFile = File(...)):
    if not ppt.filename or not ppt.filename.lower().endswith('.pptx'):
        raise HTTPException(status_code=400, detail="Only PPTX files are allowed.")
    if not audio.filename or not (audio.filename.lower().endswith('.mp3') or audio.filename.lower().endswith('.wav') or audio.filename.lower().endswith('.m4a')):
        raise HTTPException(status_code=400, detail="Only audio files (.mp3, .wav, .m4a) are allowed.")
    
    try:
        # Save PPTX and audio files
        with NamedTemporaryFile(delete=False, suffix='.pptx') as tmp_ppt:
            tmp_ppt.write(await ppt.read())
            pptx_path = tmp_ppt.name
        
        with NamedTemporaryFile(delete=False, suffix=os.path.splitext(audio.filename)[-1]) as tmp_audio:
            tmp_audio.write(await audio.read())
            audio_path = tmp_audio.name
        
        # Extract PPTX content using GPT-4o mini
        from pptx import Presentation
        prs = Presentation(pptx_path)
        slides_content = []
        
        for i, slide in enumerate(prs.slides):
            slide_data = {
                'slide_number': i + 1,
                'shapes': [],
                'text_content': []
            }
            
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    slide_data['shapes'].append({
                        'text': shape.text.strip(),
                        'shape_type': str(type(shape).__name__)
                    })
                    slide_data['text_content'].append(shape.text.strip())
            
            slides_content.append(slide_data)
        
        # Transcribe audio with Whisper
        model = whisper.load_model("base")
        result = model.transcribe(audio_path, word_timestamps=True)
        segments = result["segments"]
        
        # Extract full transcription and split into sentences
        full_transcription = ' '.join([str(seg.get('text', '')) for seg in segments if isinstance(seg, dict)])
        sentences = re.split(r'(?<=[.!?])\s+', full_transcription.strip())
        sentences = [s.strip() for s in sentences if s.strip()]
        
        print(f"Extracted {len(sentences)} sentences from audio")
        print(f"Found {len(slides_content)} slides in PPTX")
        
        # Use GPT-4o mini to analyze content and create animation plan
        openai.api_key = os.getenv('OPENAI_API_KEY')
        
        # First, get a high-level analysis of the audio content
        audio_analysis_prompt = f"""
        Analyze this audio transcription and break it down into logical sections that would correspond to different slides or slide elements.
        
        Audio transcription:
        {full_transcription}
        
        Return a JSON array where each element contains:
        - "section": A brief description of what this section covers
        - "sentences": Array of sentence indices (0-based) that belong to this section
        - "key_topics": Array of key topics or concepts mentioned
        
        Focus on natural breaks in the content and logical groupings.
        """
        
        audio_analysis_response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert at analyzing presentation content and matching it to slide structures."},
                {"role": "user", "content": audio_analysis_prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # Parse audio sections with error handling
        audio_content = audio_analysis_response.choices[0].message.content
        print(f"Raw audio analysis response: {audio_content}")
        
        try:
            if audio_content:
                audio_sections = json.loads(audio_content)
            else:
                audio_sections = []
        except json.JSONDecodeError as e:
            print(f"Failed to parse audio sections JSON: {e}")
            audio_sections = []
        
        # Now analyze PPTX content
        pptx_analysis_prompt = f"""
        Analyze this PowerPoint presentation structure and provide a detailed breakdown of each slide's content and purpose.
        
        Slides content:
        {json.dumps(slides_content, indent=2)}
        
        Return a JSON array where each element contains:
        - "slide_number": The slide number (1-based)
        - "main_topic": The main topic or theme of this slide
        - "key_elements": Array of key text elements on this slide
        - "purpose": What this slide is trying to communicate
        - "content_summary": A brief summary of the slide's content
        """
        
        pptx_analysis_response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert at analyzing PowerPoint presentations and understanding their structure."},
                {"role": "user", "content": pptx_analysis_prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # Parse PPTX slides with error handling
        pptx_content = pptx_analysis_response.choices[0].message.content
        print(f"Raw PPTX analysis response: {pptx_content}")
        
        try:
            if pptx_content:
                pptx_slides = json.loads(pptx_content)
            else:
                pptx_slides = []
        except json.JSONDecodeError as e:
            print(f"Failed to parse PPTX slides JSON: {e}")
            pptx_slides = []
        
        # Create detailed animation plan using GPT-4o mini
        animation_plan_prompt = f"""
        Create a detailed animation plan that matches audio sections to PowerPoint slides and elements.
        
        Audio sections: {json.dumps(audio_sections, indent=2)}
        PowerPoint slides: {json.dumps(pptx_slides, indent=2)}
        
        Rules:
        1. Each audio section should be matched to the most relevant slide
        2. Within each slide, determine which elements should be revealed based on the audio content
        3. If the context doesn't change significantly, keep the same slide active
        4. Only transition to a new slide when the audio content clearly moves to a new topic
        5. For each sentence, specify which slide and which elements should be visible
        
        Return a JSON array where each element contains:
        - "sentence_index": Index of the sentence (0-based)
        - "sentence_text": The actual sentence text
        - "slide_number": Which slide should be shown (1-based)
        - "visible_elements": Array of element indices (0-based) that should be visible
        - "transition_type": "new_slide", "same_slide", or "element_reveal"
        - "reasoning": Brief explanation of why this match was chosen
        """
        
        animation_plan_response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert at creating synchronized presentations where audio content drives slide animations."},
                {"role": "user", "content": animation_plan_prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # Parse animation plan with error handling
        animation_plan_content = animation_plan_response.choices[0].message.content
        print(f"Raw animation plan response: {animation_plan_content}")
        
        try:
            if animation_plan_content:
                parsed_content = json.loads(animation_plan_content)
                # Handle nested structure where animation_plan, presentation_animation_plan, presentation_animations, animationPlan, or presentation_plan is a key
                if isinstance(parsed_content, dict):
                    if "animation_plan" in parsed_content:
                        animation_plan = parsed_content["animation_plan"]
                    elif "presentation_animation_plan" in parsed_content:
                        animation_plan = parsed_content["presentation_animation_plan"]
                    elif "presentation_animations" in parsed_content:
                        animation_plan = parsed_content["presentation_animations"]
                    elif "animationPlan" in parsed_content:
                        animation_plan = parsed_content["animationPlan"]
                    elif "presentation_plan" in parsed_content:
                        animation_plan = parsed_content["presentation_plan"]
                    else:
                        animation_plan = []
                elif isinstance(parsed_content, list):
                    animation_plan = parsed_content
                else:
                    animation_plan = []
            else:
                animation_plan = []
        except json.JSONDecodeError as e:
            print(f"Failed to parse animation plan JSON: {e}")
            print(f"Raw content: {animation_plan_content}")
            # Fallback: create a simple animation plan
            animation_plan = []
            for i, sentence in enumerate(sentences):
                # Simple fallback: cycle through slides
                slide_num = (i % len(slides_content)) + 1
                animation_plan.append({
                    "sentence_index": i,
                    "sentence_text": sentence,
                    "slide_number": slide_num,
                    "visible_elements": [0],  # Show first element
                    "transition_type": "new_slide" if i == 0 else "same_slide",
                    "reasoning": "Fallback mapping"
                })
        
        print(f"Created animation plan with {len(animation_plan)} steps")
        
        # Save the animation plan for debugging
        with open(os.path.join(UPLOADS_DIR, "animation_plan.json"), 'w', encoding='utf-8') as f:
            json.dump(animation_plan, f, ensure_ascii=False, indent=2)
        
        # Create animation frames based on the plan
        audio = AudioSegment.from_file(audio_path)
        audio_duration = len(audio) / 1000.0
        step_duration = audio_duration / len(animation_plan) if animation_plan else 1.0
        
        # Validate PowerPoint file size before processing
        validate_pptx_file_size(pptx_path)
        
        # Extract slides as images using GPT-4o or Python fallback
        print("Extracting PowerPoint slides as images...")
        slide_images = []
        
        # Load the original presentation
        original_prs = Presentation(pptx_path)
        
        # Try GPT extraction first, fall back to Python if file is too large
        use_python_extraction = False
        
        try:
            # Try to extract the first slide with GPT to test if it works
            print("Testing GPT extraction with first slide...")
            test_images = extract_slide_images_with_gpt(pptx_path, 1)
            slide_images.extend(test_images)
            print(f"GPT extraction successful for slide 1, continuing with GPT...")
            
            # If first slide worked, continue with GPT for remaining slides
            for i in range(1, len(original_prs.slides)):
                slide_num = i + 1
                print(f"Extracting slide {slide_num} using GPT-4o...")
                extracted_images = extract_slide_images_with_gpt(pptx_path, slide_num)
                slide_images.extend(extracted_images)
                print(f"Successfully extracted {len(extracted_images)} images for slide {slide_num}")
            
            print(f"Successfully extracted {len(slide_images)} slides using GPT-4 Vision")
            
        except Exception as e:
            print(f"GPT extraction failed, falling back to Python-based extraction: {e}")
            use_python_extraction = True
        
        # If GPT failed, use Python-based extraction for all slides
        if use_python_extraction or not slide_images:
            print("Using Python-based extraction for all slides...")
            slide_images = []  # Clear any partial results
            
            for i in range(len(original_prs.slides)):
                slide_num = i + 1
                print(f"Extracting slide {slide_num} using Python...")
                extracted_images = extract_slide_images_with_python(pptx_path, slide_num)
                slide_images.extend(extracted_images)
                print(f"Successfully extracted {len(extracted_images)} images for slide {slide_num}")
            
            print(f"Successfully extracted {len(slide_images)} slides using Python")
        
        # Now create animation frames using the extracted slide images
        animation_frames = []
        
        for i, step in enumerate(animation_plan):
            slide_num = step['slide_number']
            
            # Use the corresponding slide image
            slide_idx = slide_num - 1
            if slide_idx < len(slide_images):
                # Copy the slide image for this frame
                slide_image_path = slide_images[slide_idx]
                frame_filename = os.path.join(UPLOADS_DIR, f"anim_frame_{i+1:04d}.png")
                
                # Copy the slide image to the frame
                import shutil
                shutil.copy2(slide_image_path, frame_filename)
                animation_frames.append(frame_filename)
                
                print(f"Created frame {i+1}: Using slide {slide_num} image")
            else:
                # Fallback if slide doesn't exist
                print(f"Warning: Slide {slide_num} not found, using slide 1")
                if slide_images:
                    frame_filename = os.path.join(UPLOADS_DIR, f"anim_frame_{i+1:04d}.png")
                    shutil.copy2(slide_images[0], frame_filename)
                    animation_frames.append(frame_filename)
        
        # Create video from animation frames
        if not animation_frames:
            raise Exception("No animation frames were created")
        
        # Create ffmpeg input file
        ffmpeg_input_txt = os.path.join(UPLOADS_DIR, "animation_input.txt")
        with open(ffmpeg_input_txt, 'w') as f:
            for frame_file in animation_frames:
                f.write(f"file '{os.path.basename(frame_file)}'\n")
                f.write(f"duration {step_duration}\n")
            # Add the last frame again to ensure proper duration
            f.write(f"file '{os.path.basename(animation_frames[-1])}'\n")
        
        # Generate video
        video_path = os.path.join(UPLOADS_DIR, "animation_output.mp4")
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "animation_input.txt",
            "-pix_fmt", "yuv420p", "-r", "30", "animation_output.mp4"
        ], check=True, cwd=UPLOADS_DIR)
        
        # Check video duration and pad if needed
        ffprobe_cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration", 
            "-of", "default=noprint_wrappers=1:nokey=1", "animation_output.mp4"
        ]
        result = subprocess.run(ffprobe_cmd, cwd=UPLOADS_DIR, capture_output=True, text=True)
        video_duration = float(result.stdout.strip()) if result.returncode == 0 else 0.0
        
        if video_duration < audio_duration:
            pad_duration = audio_duration - video_duration
            last_frame = os.path.basename(animation_frames[-1])
            last_frame_video = "last_frame.mp4"
            
            subprocess.run([
                "ffmpeg", "-y", "-loop", "1", "-i", last_frame, 
                "-c:v", "libx264", "-t", str(pad_duration), "-pix_fmt", "yuv420p", 
                "-r", "30", last_frame_video
            ], check=True, cwd=UPLOADS_DIR)
            
            # Concatenate original video with padding
            concat_list = os.path.join(UPLOADS_DIR, "final_concat.txt")
            with open(concat_list, 'w') as f:
                f.write("file 'animation_output.mp4'\n")
                f.write(f"file '{last_frame_video}'\n")
            
            padded_video = os.path.join(UPLOADS_DIR, "animation_output_padded.mp4")
            subprocess.run([
                "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "final_concat.txt", 
                "-c", "copy", "animation_output_padded.mp4"
            ], check=True, cwd=UPLOADS_DIR)
            video_path = padded_video
        
        # Combine video with audio
        final_video_path = os.path.join(UPLOADS_DIR, "final_animated_presentation.mp4")
        subprocess.run([
            "ffmpeg", "-y", "-i", os.path.basename(video_path), "-i", audio_path, 
            "-c:v", "copy", "-c:a", "aac", "-shortest", "final_animated_presentation.mp4"
        ], check=True, cwd=UPLOADS_DIR)
        
        return JSONResponse({
            "message": f"Successfully created animated presentation! Video saved to '{UPLOADS_DIR}/final_animated_presentation.mp4'",
            "details": {
                "audio_sentences": len(sentences),
                "slides_analyzed": len(slides_content),
                "animation_steps": len(animation_plan),
                "frames_created": len(animation_frames),
                "video_duration": audio_duration
            }
        })
        
    except Exception as e:
        import traceback
        print(f"Error in PPTX animation: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e)) 