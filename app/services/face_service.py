import os
import uuid
import base64
from datetime import datetime
from fastapi import HTTPException, UploadFile
from app.core.config import SAVE_DIR, HAS_DEEPFACE
from app.core.db import verification_logs
from app.utils.image_utils import image_to_base64

if HAS_DEEPFACE:
    from deepface import DeepFace

async def verify_face_logic(live_file: UploadFile, aadhaar_path_or_base64: str):
    # Determine if input is a local path or a base64 string
    temp_aadhaar_path = None
    live_path = None
    
    try:
        if not aadhaar_path_or_base64:
             raise HTTPException(status_code=400, detail="Aadhaar photo missing")
             
        if aadhaar_path_or_base64.startswith("data:"):
            # If it's base64 from frontend, we temporarily save it for DeepFace to read
            try:
                temp_aadhaar_path = os.path.join(SAVE_DIR, f"temp_aadhaar_{uuid.uuid4()}.jpg")
                header, encoded = aadhaar_path_or_base64.split(",", 1)
                with open(temp_aadhaar_path, "wb") as f:
                    f.write(base64.b64decode(encoded))
                process_path = temp_aadhaar_path
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid Base64 Image: {str(e)}")
        else:
            process_path = aadhaar_path_or_base64
    
        if not os.path.exists(process_path):
            raise HTTPException(status_code=400, detail="Aadhaar photo file not found")
        
        live_path = os.path.join(SAVE_DIR, f"live_{uuid.uuid4()}.jpg")
        with open(live_path, "wb") as buffer:
            buffer.write(await live_file.read())
        
        if HAS_DEEPFACE:
            result = DeepFace.verify(
                img1_path=process_path, 
                img2_path=live_path, 
                model_name="Facenet512", 
                detector_backend="opencv",
                enforce_detection=False
            )
            
            threshold = 0.58
            is_verified = result["distance"] < threshold

            # Convert live selfie to Base64 for DB
            live_base64 = image_to_base64(live_path)

            # SAVE TO MONGODB
            log_entry = {
                "timestamp": datetime.now(),
                "live_photo_base64": live_base64,
                "distance": result["distance"],
                "verified": is_verified,
                "model": "Facenet512"
            }
            await verification_logs.insert_one(log_entry)

            return {
                "verified": is_verified,
                "confidence": 1 - result["distance"],
                "distance": result["distance"]
            }
        else:
            raise HTTPException(status_code=500, detail="DeepFace not initialized")
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"VERIFICATION ERROR: {str(e)}") 
        raise HTTPException(status_code=500, detail=f"AI Verification Failed: {str(e)}")
    finally:
        # CLEANUP LOCAL FILES
        if temp_aadhaar_path and os.path.exists(temp_aadhaar_path):
            try: os.remove(temp_aadhaar_path)
            except: pass
        if live_path and os.path.exists(live_path):
            try: os.remove(live_path)
            except: pass
