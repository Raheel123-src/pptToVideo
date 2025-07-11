import os
from pdf2image import convert_from_path
import fitz  # PyMuPDF
from pdfminer.high_level import extract_text as pdfminer_extract_text
import pytesseract
from PIL import Image
from dotenv import load_dotenv
import openai

load_dotenv()

PDF_PATH = os.getenv('PDF_PATH')
UPLOADS_DIR = os.getenv('UPLOADS_DIR', 'uploads')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

os.makedirs(UPLOADS_DIR, exist_ok=True)

def extract_text_pymupdf(pdf_path, page_number):
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_number)
    text = page.get_text()
    doc.close()
    return text

def extract_text_pdfminer(pdf_path, page_number):
    return pdfminer_extract_text(pdf_path, page_numbers=[page_number])

def extract_text_ocr(image):
    return pytesseract.image_to_string(image)

def extract_text_openai(image):
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY must be set in the .env file.")
    openai.api_key = OPENAI_API_KEY
    import io
    import base64
    buf = io.BytesIO()
    image.save(buf, format='PNG')
    buf.seek(0)
    image_b64 = base64.b64encode(buf.read()).decode('utf-8')
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that extracts all readable text from images. Return only the text, no commentary."},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}
            ]}
        ],
        max_tokens=2048,
    )
    return response.choices[0].message.content.strip()

def pdf_to_text_and_images(pdf_path, uploads_dir, use_gpt4o=False):
    images = convert_from_path(pdf_path)
    for i, image in enumerate(images):
        # Text extraction
        text = extract_text_pymupdf(pdf_path, i).strip()
        if not text:
            text = extract_text_pdfminer(pdf_path, i).strip()
        if not text:
            text = extract_text_ocr(image).strip()
        if use_gpt4o and not text:
            text = extract_text_openai(image).strip()
        txt_filename = os.path.join(uploads_dir, f"page_{i+1}.txt")
        with open(txt_filename, 'w', encoding='utf-8') as txt_file:
            txt_file.write(text or '')
        # Save image
        img_filename = os.path.join(uploads_dir, f"page_{i+1}.png")
        image.save(img_filename, 'PNG')

if __name__ == "__main__":
    if not PDF_PATH:
        raise ValueError("PDF_PATH must be set in the .env file.")
    pdf_to_text_and_images(PDF_PATH, UPLOADS_DIR) 