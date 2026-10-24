"""
First-pass OCR Engine for Karyalaya AI.
Extracts text from images using Pytesseract / Pillow with confidence scoring. pytesseract/Pillow.
Computes an OCR confidence score to determine if VLM fallback is needed.
"""

import os
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
from typing import Dict, Any

def preprocess_image(image_path: str) -> Image.Image:
    """Preprocesses scan/image (grayscale, contrast, sharpness) for better OCR."""
    img = Image.open(image_path).convert("L")  # Convert to grayscale
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)                # Increase contrast
    img = img.filter(ImageFilter.SHARPEN)      # Sharpen text edges
    return img


def extract_text_ocr(image_path: str) -> Dict[str, Any]:
    """
    Performs OCR on an image and calculates extraction confidence.
    Returns extracted text, confidence (0.0 - 1.0), and fallback recommendation.
    """
    if not os.path.exists(image_path):
        return {"status": "error", "error": f"Image file not found: {image_path}"}

    try:
        img = preprocess_image(image_path)
        
        # Get OCR data including confidence scores per word
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        
        text_words = []
        confidences = []

        for i in range(len(data['text'])):
            word = data['text'][i].strip()
            conf = float(data['conf'][i])
            if word and conf > 0:
                text_words.append(word)
                confidences.append(conf)

        extracted_text = " ".join(text_words)
        avg_confidence = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.0

        # Fallback needed if confidence < 0.75 or very little text extracted
        fallback_required = (avg_confidence < 0.75) or (len(extracted_text) < 15)

        return {
            "status": "success",
            "extracted_text": extracted_text,
            "confidence": round(avg_confidence, 2),
            "fallback_required": fallback_required,
            "word_count": len(text_words),
            "engine": "Pytesseract OCR (Pass 1)"
        }

    except Exception as e:
        # If tesseract binary is not installed or errors out, trigger VLM fallback
        return {
            "status": "warning",
            "extracted_text": "",
            "confidence": 0.0,
            "fallback_required": True,
            "error": f"OCR Engine warning: {e}. Falling back to Vision Language Model."
        }


if __name__ == "__main__":
    # Test script on simple image creation
    from PIL import ImageDraw, ImageFont
    test_img_path = "/tmp/test_scan.png"
    img = Image.new('RGB', (600, 150), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((20, 40), "INSPECTION REPORT: Valve #3 Pass 150 PSI", fill=(0, 0, 0))
    img.save(test_img_path)

    res = extract_text_ocr(test_img_path)
    print("OCR Result:", res)
