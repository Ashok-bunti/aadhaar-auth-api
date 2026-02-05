import os
import re
import cv2
import uuid
import base64
import zipfile
import numpy as np
from datetime import datetime
from lxml import etree
from fastapi import HTTPException, UploadFile
from PyPDF2 import PdfReader
from app.core.config import SAVE_DIR, HAS_SCANNER, HAS_OCR, HAS_PDF2IMAGE, HAS_DEEPFACE
from app.utils.helpers import calculate_address_perfection
from app.utils.image_utils import image_to_base64
from app.core.db import kyc_records

if HAS_DEEPFACE:
    from deepface import DeepFace
if HAS_SCANNER:
    from pyzbar.pyzbar import decode
if HAS_OCR:
    import pytesseract
if HAS_PDF2IMAGE:
    from pdf2image import convert_from_bytes

async def save_to_db(method, data, file_path, photo_path):
    """Helper to save KYC record to MongoDB with Base64 image."""
    # Convert photo to base64
    photo_base64 = image_to_base64(photo_path)
    
    record = {
        "timestamp": datetime.now(),
        "method": method,
        "uid": data.get("uid"),
        "full_name": data.get("full_name"),
        "dob": data.get("dob"),
        "gender": data.get("gender"),
        "address": data.get("address"),
        "pincode": data.get("pincode"),
        "perfection_score": data.get("perfection_score"),
        "photo_base64": photo_base64
    }
    await kyc_records.insert_one(record)
    
    # After saving base64 to DB, we can delete the local photo to keep storage clean
    if photo_path and os.path.exists(photo_path) and not photo_path.startswith("http"):
        try:
            os.remove(photo_path)
        except: pass
        
    return photo_base64

def extract_aadhaar_data(image_path):
    """
    Enhanced extraction logic for OCR and QR code fallback.
    """
    try:
        img_cv = cv2.imread(image_path)
        if img_cv is None: return {"is_aadhaar": False}
        
        h, w = img_cv.shape[:2]
        if w < 1000:
            scale = 1000 / w
            img_cv = cv2.resize(img_cv, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
        
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # 1. QR Code
        if HAS_SCANNER:
            qr_codes = decode(gray)
            for qr in qr_codes:
                qr_data = qr.data.decode("utf-8")
                if "uid=" in qr_data:
                    uid = re.search(r'uid="(\d{12})"', qr_data)
                    name = re.search(r'name="([^"]+)"', qr_data)
                    house = re.search(r'house="([^"]+)"', qr_data)
                    vtc = re.search(r'vtc="([^"]+)"', qr_data)
                    state = re.search(r'state="([^"]+)"', qr_data)
                    pc = re.search(r'pc="(\d{6})"', qr_data)
                    full_addr = ", ".join([p.group(1) for p in [house, vtc, state, pc] if p])
                    score, status, _ = calculate_address_perfection({"pincode": pc.group(1) if pc else None, "state": state.group(1) if state else None, "house": house.group(1) if house else None})
                    return {
                        "is_aadhaar": True,
                        "uid": uid.group(1) if uid else "Verified",
                        "full_name": name.group(1) if name else "Verified",
                        "address": full_addr,
                        "pincode": pc.group(1) if pc else "Detected",
                        "perfection_score": score,
                        "address_status": status
                    }

        # 2. OCR
        if HAS_OCR:
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            text = pytesseract.image_to_string(thresh, config=r'--oem 3 --psm 3')
            text_upper = text.upper()
            
            keywords = ["AADHAAR", "GOVERNMENT", "INDIA", "UIDAI", "MALE", "FEMALE", "DOB", "ADDRESS", "VID"]
            is_valid_doc = any(k in text_upper for k in keywords)
            pincode = re.search(r'(\d{6})(?!.*\d{6})', text)
            pincode_val = pincode.group(1) if pincode else None
            
            if not is_valid_doc and not pincode_val:
                 return {"is_aadhaar": False}

            uid_match = re.search(r'\d{4}[\s\.\-]\d{4}[\s\.\-]\d{4}', text) or re.search(r'\b\d{12}\b', text)
            uid_val = uid_match.group(0) if uid_match else "Verified Document"
            
            addr_text = "N/A"
            addr_start_idx = -1
            addr_match = re.search(r'(ADDRESS|ADDR|TO)\s*[:\-\.]', text, re.IGNORECASE)
            if addr_match:
                addr_start_idx = addr_match.end()
            else:
                addr_idx = text_upper.find("ADDRESS")
                if addr_idx != -1:
                    addr_start_idx = addr_idx + 7
            
            if addr_start_idx != -1 and pincode_val:
                pin_idx = text.find(pincode_val)
                if pin_idx > addr_start_idx:
                    raw_block = text[addr_start_idx:pin_idx]
                    lines = raw_block.split('\n')
                    clean_lines = []
                    for line in lines:
                        line = line.strip()
                        if not line: continue
                        disclaimer_triggers = ["should", "updated", "updeted", "enrollment", "enrolment", "validity", "government", "aadhaar"]
                        if any(t in line.lower() for t in disclaimer_triggers):
                            continue
                        if len(line) > 40 and not any(c.isdigit() for c in line):
                             continue
                        clean_lines.append(line)
                    if clean_lines:
                        addr_text = ", ".join(clean_lines) + f" - {pincode_val}"
            
            elif pincode_val:
                lines = text.split('\n')
                pin_line_idx = -1
                for i, line in enumerate(lines):
                    if pincode_val in line:
                        pin_line_idx = i
                        break
                
                if pin_line_idx != -1:
                    address_lines = []
                    banned_words = ["should", "updated", "updeted", "enrolment", "years", "date", "government", "validity", "help", "download", "www", "identity", "information"]
                    for i in range(pin_line_idx, max(-1, pin_line_idx - 6), -1):
                        line = lines[i].strip()
                        if not line: continue
                        if any(w in line.lower() for w in banned_words): continue
                        is_valid_structure = any(x in line.lower() for x in ["s/o", "w/o", "h.no", "no.", "sector", "road", "dist", "state", "vtc"])
                        if i == pin_line_idx or is_valid_structure or len(line) < 40:
                             address_lines.insert(0, line)
                    if address_lines:
                         addr_text = ", ".join(address_lines)

            addr_text = re.sub(r'\s+', ' ', addr_text)
            addr_text = re.sub(r'^(S/O|W/O|D/O|C/O)\s*[:\.]?\s*', '', addr_text, flags=re.IGNORECASE).strip()
            addr_text = re.sub(r'^[:\-\,]+', '', addr_text).strip()

            score, status, _ = calculate_address_perfection({"pincode": pincode_val, "address": addr_text})

            return {
                "is_aadhaar": True,
                "uid": uid_val,
                "address": addr_text,
                "pincode": pincode_val,
                "perfection_score": score,
                "address_status": status,
                "gender": "Female" if "FEMALE" in text_upper else "Male",
                "dob": re.search(r'\d{2}/\d{2}/\d{4}', text).group(0) if re.search(r'\d{2}/\d{2}/\d{4}', text) else "N/A"
            }

        return {"is_aadhaar": False}
    except Exception:
        return {"is_aadhaar": False}

async def process_offline_xml(file: UploadFile, password: str):
    file_ext = file.filename.lower().split('.')[-1]
    file_path = os.path.join(SAVE_DIR, f"{uuid.uuid4()}.{file_ext}")
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    
    try:
        if file_ext == 'zip':
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                xml_files = [f for f in zip_ref.namelist() if f.endswith('.xml')]
                if not xml_files: raise HTTPException(status_code=400, detail="No XML file found in ZIP")
                try:
                    xml_content = zip_ref.read(xml_files[0], pwd=password.encode())
                except RuntimeError:
                    raise HTTPException(status_code=400, detail="Incorrect password.")
            
            root = etree.fromstring(xml_content)
            uid = root.get('uid', 'N/A')
            name = root.get('name', 'N/A')
            gender_code = root.get('gender', 'M')
            dob = root.get('dob', 'N/A')
            house = root.get('house', '')
            street = root.get('street', '')
            vtc = root.get('vtc', '')
            dist = root.get('dist', '')
            state = root.get('state', '')
            pc = root.get('pc', '')
            full_address = ", ".join(filter(None, [house, street, vtc, dist, state, pc]))
            
            photo_b64 = root.get('photo', '')
            photo_path = None
            if photo_b64:
                photo_data = base64.b64decode(photo_b64)
                photo_path = os.path.join(SAVE_DIR, f"offline_{uuid.uuid4()}.jpg")
                with open(photo_path, "wb") as photo_file:
                    photo_file.write(photo_data)
            
            score, status, _ = calculate_address_perfection({"pincode": pc, "state": state, "address": full_address})
            
            details = {
                "is_aadhaar": True,
                "uid": f"XXXX XXXX {uid[-4:]}",
                "full_name": name,
                "gender": "Male" if gender_code == "M" else "Female",
                "dob": dob,
                "address": full_address,
                "pincode": pc,
                "perfection_score": score,
                "address_status": status
            }

            # SAVE TO MONGODB (Converts to Base64 and deletes local file)
            photo_result = await save_to_db("offline_xml_zip", details, file_path, photo_path)

            return {
                "status": "success",
                "aadhaar_photo": photo_result or "https://placehold.co/400x400?text=No+Photo",
                "details": details
            }
        
        else:  # PDF
            reader = PdfReader(file_path)
            if reader.is_encrypted:
                if reader.decrypt(password) == 0:
                    raise HTTPException(status_code=400, detail="Incorrect PDF password.")
            
            pdf_text = ""
            for page in reader.pages:
                pdf_text += page.extract_text() or ""
            
            if "Aadhaar" in pdf_text or "UIDAI" in pdf_text:
                pdf_data = {}
                clean_text = re.sub(r'\s+', ' ', pdf_text)

                # 1. Precise UID Extraction
                uid_match = re.search(r'(?:Your\s*Aadhaar\s*No\.?\s*[:\.]?\s*|)(\d{4}\s+\d{4}\s+\d{4})(?=\s*VID|\s*Virtual)', clean_text, re.IGNORECASE)
                if not uid_match:
                    uid_match = re.search(r'(\d{4}\s+\d{4}\s+\d{4})', clean_text)
                pdf_data["uid"] = uid_match.group(1) if uid_match else "Detected"
                
                # 2. Name Extraction
                name_match = re.search(r'To\s+([^\n]+)\n([^\n]+)', pdf_text)
                if name_match:
                    name_candidate = name_match.group(2).strip()
                    if not any(x in name_candidate.upper() for x in ["S/O", "W/O", "D/O", "C/O"]):
                        pdf_data["full_name"] = name_candidate
                    else:
                        pdf_data["full_name"] = name_match.group(1).strip()
                
                # 3. Address Extraction
                addr_match = re.search(r'Address:?(.*?)(?:\b\d{6}\b)', pdf_text, re.DOTALL | re.IGNORECASE)
                if addr_match:
                    raw_addr = addr_match.group(1).replace('\n', ' ').strip()
                    raw_addr = re.sub(r'^[:\s,]+', '', raw_addr)
                    raw_addr = re.sub(r'^(S/O|W/O|D/O|C/O)\s*[:\.]?\s*[^,]+,\s*', '', raw_addr, flags=re.IGNORECASE).strip()
                    pdf_data["address"] = raw_addr
                
                # 4. Pincode
                pc_match = re.search(r'\b\d{6}\b', pdf_text)
                if pc_match:
                    pdf_data["pincode"] = pc_match.group(0)
                    if pdf_data.get("address") and pdf_data["pincode"] not in pdf_data["address"]:
                        pdf_data["address"] += f" - {pdf_data['pincode']}"

                if "FEMALE" in pdf_text.upper(): pdf_data["gender"] = "Female"
                elif "MALE" in pdf_text.upper(): pdf_data["gender"] = "Male"
                
                dob_match = re.search(r'DOB\s*:\s*(\d{2}/\d{2}/\d{4})', pdf_text) or re.search(r'Year of Birth\s*:\s*(\d{4})', pdf_text)
                if dob_match: pdf_data["dob"] = dob_match.group(1)

                face_path = None
                if HAS_PDF2IMAGE:
                    pages = convert_from_bytes(open(file_path, "rb").read(), userpw=password)
                    image_path = file_path.replace(".pdf", ".jpg")
                    pages[0].save(image_path, "JPEG")
                    face_path = image_path
                    
                    if HAS_DEEPFACE:
                        try:
                            faces = DeepFace.extract_faces(img_path=image_path, detector_backend="opencv", enforce_detection=True)
                            temp_face_path = os.path.join(SAVE_DIR, f"pdf_face_{uuid.uuid4()}.jpg")
                            face_img = (faces[0]["face"] * 255).astype(np.uint8)
                            face_img = cv2.cvtColor(face_img, cv2.COLOR_RGB2BGR)
                            if cv2.imwrite(temp_face_path, face_img):
                                # If extraction successful, we can delete the full page image now
                                if os.path.exists(image_path):
                                    try: os.remove(image_path)
                                    except: pass
                                face_path = temp_face_path
                        except: pass
                    
                    if not pdf_data.get("address") or pdf_data["address"] == "N/A":
                        ocr_details = extract_aadhaar_data(image_path)
                        pdf_data.update({k: v for k, v in ocr_details.items() if v and v != "N/A"})

                score, status, _ = calculate_address_perfection({"pincode": pdf_data.get("pincode"), "address": pdf_data.get("address")})
                
                details = {
                    "is_aadhaar": True,
                    "uid": pdf_data.get("uid", "Detected"),
                    "full_name": pdf_data.get("full_name", "Verified User"),
                    "gender": pdf_data.get("gender", "N/A"),
                    "dob": pdf_data.get("dob", "N/A"),
                    "address": pdf_data.get("address", "N/A"),
                    "pincode": pdf_data.get("pincode", "N/A"),
                    "perfection_score": score,
                    "address_status": status
                }

                # SAVE TO MONGODB (Converts to Base64 and deletes local file)
                photo_result = await save_to_db("offline_pdf", details, file_path, face_path)

                return {
                    "status": "success",
                    "aadhaar_photo": photo_result or "https://placehold.co/400x400?text=No+Photo",
                    "details": details
                }
            
            raise HTTPException(status_code=400, detail="Could not process PDF")

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
