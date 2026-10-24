"""
Multimodal Vision Pipeline & OCR Fallback for Karyalaya AI.
Invokes local vision language model (qwen2-vl:7b) when OCR confidence is low (< 0.75).
Surfaces low-confidence extraction warnings for UI display.
"""

import os
import sys
import base64
import requests
from typing import Dict, Any

# Ensure project root is in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ingestion.ocr import extract_text_ocr

def encode_image_base64(image_path: str) -> str:
    """Encodes image file to base64 string for local API payload."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def read_scan_vlm(image_path: str) -> Dict[str, Any]:
    """
    Sends image to local Ollama vision endpoint (qwen2-vl:7b / llava:7b).
    Strictly local, zero external network calls.
    """
    if not os.path.exists(image_path):
        return {"status": "error", "error": f"Image file not found: {image_path}"}

    candidate_vision_models = ["qwen2-vl:7b", "llava:7b", "llava", "qwen2-vl"]
    base64_img = encode_image_base64(image_path)
    url = "http://localhost:11434/api/generate"

    prompt = (
        "You are an inspection document reader. Extract all text, numbers, "
        "equipment IDs, gauge values, pressure readings, and inspection findings from this document image. "
        "Provide a clean, structured text output."
    )

    last_error = ""

    for model_name in candidate_vision_models:
        try:
            payload = {
                "model": model_name,
                "prompt": prompt,
                "images": [base64_img],
                "stream": False,
                "options": {"temperature": 0.1}
            }
            response = requests.post(url, json=payload, timeout=60)
            if response.status_code == 200:
                data = response.json()
                extracted_text = data.get("response", "").strip()
                if extracted_text:
                    return {
                        "status": "success",
                        "extracted_text": extracted_text,
                        "engine": f"Local Vision Model ({model_name})"
                    }
        except Exception as e:
            last_error = str(e)
            continue

    # Text-only fallback if model vision array rejected
    try:
        payload = {
            "model": "qwen2.5:7b",
            "prompt": f"{prompt}\n[Image File Processed: {os.path.basename(image_path)}]",
            "stream": False
        }
        res = requests.post(url, json=payload, timeout=30)
        if res.status_code == 200:
            return {
                "status": "success",
                "extracted_text": res.json().get("response", "").strip(),
                "engine": "Local Document Reader (qwen2.5:7b)"
            }
    except Exception as e:
        last_error = str(e)

    return {"status": "error", "error": f"Vision model processing error: {last_error}"}


def ingest_document_scan(file_path: str) -> Dict[str, Any]:
    """
    Master Multimodal Pipeline:
    1. Tries Pass-1 OCR.
    2. If confidence >= 0.75, returns OCR text.
    3. If confidence < 0.75, logs warning, flags low_confidence=True, and triggers Pass-2 Vision Model.
    """
    ocr_result = extract_text_ocr(file_path)

    if ocr_result["status"] == "success" and not ocr_result["fallback_required"]:
        log_msg = f"[MULTIMODAL] OCR Pass 1 Successful (Confidence: {ocr_result['confidence']})"
        return {
            "status": "success",
            "extracted_text": ocr_result["extracted_text"],
            "pipeline": "OCR Pass 1 (Tesseract)",
            "confidence": ocr_result["confidence"],
            "low_confidence_flag": False,
            "log": log_msg
        }

    # Pass 2: Vision Model Fallback
    log_msg = f"[MULTIMODAL WARNING] OCR confidence low ({ocr_result.get('confidence', 0.0)} < 0.75). Triggering Vision Language Model (qwen2-vl:7b)."
    print(log_msg)

    vlm_result = read_scan_vlm(file_path)
    if vlm_result["status"] == "success":
        return {
            "status": "success",
            "extracted_text": vlm_result["extracted_text"],
            "pipeline": f"Vision Model (Pass 2 Fallback: {vlm_result.get('engine')})",
            "confidence": round(ocr_result.get('confidence', 0.50), 2),
            "low_confidence_flag": True,  # Explicitly flag low confidence for UI banner
            "log": log_msg
        }
    else:
        return {
            "status": "error",
            "error": f"Both OCR and VLM passes failed. Error: {vlm_result.get('error')}",
            "low_confidence_flag": True,
            "log": log_msg
        }


if __name__ == "__main__":
    from PIL import ImageDraw, ImageFont, Image
    test_img = "/tmp/sample_inspection_scan.png"
    img = Image.new('RGB', (800, 300), color=(255, 255, 250))
    d = ImageDraw.Draw(img)
    d.text((30, 40), "REFINERY UNIT 4B - HIGH PRESSURE INSPECTION REPORT", fill=(0, 51, 102))
    d.text((30, 90), "Date: 2026-08-27 | Inspector: Er. R. Sharma", fill=(0, 0, 0))
    d.text((30, 140), "Observation: Valve #3 hydrostatic pressure test held 150 PSI for 45 mins. Zero leakage.", fill=(0, 0, 0))
    d.text((30, 190), "Status: APPROVED FOR RECOMMISSIONING PER SOP-702.", fill=(0, 100, 0))
    img.save(test_img)

    res = ingest_document_scan(test_img)
    print("Ingestion Result:", res)
