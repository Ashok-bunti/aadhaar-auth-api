import os

SAVE_DIR = "saved_images"
os.makedirs(SAVE_DIR, exist_ok=True)

try:
    from deepface import DeepFace
    HAS_DEEPFACE = True
except ImportError as e:
    print(f"DEBUG: DeepFace import failed: {e}")
    HAS_DEEPFACE = False

try:
    from pdf2image import convert_from_bytes
    HAS_PDF2IMAGE = True
except ImportError:
    HAS_PDF2IMAGE = False

try:
    from pyzbar.pyzbar import decode
    HAS_SCANNER = True
except ImportError:
    HAS_SCANNER = False

try:
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
