import re
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request
from app.services.aadhaar_service import process_offline_xml
from app.services.face_service import verify_face_logic

router = APIRouter()

@router.post("/aadhaar-fetch-direct")
async def fetch_aadhaar_direct(req: Request):
    body = await req.json()
    aadhaar_num = body.get("aadhaar_number", "")
    
    if not re.match(r'^\d{12}$', aadhaar_num):
        raise HTTPException(status_code=400, detail="Invalid Aadhaar Number format")

    # High-Fidelity Mock for Instant Fetch
    mock_data = {
        "full_name": "ASHOK KUMAR",
        "dob": "15-08-1992",
        "gender": "Male",
        "address": "H.No 12-1/A, Kukatpally, Hyderabad, Telangana - 500001",
        "pincode": "500001",
        "uid": f"XXXX XXXX {aadhaar_num[-4:]}",
        "photo_url": "https://unavatar.io/github/ashok" 
    }
    
    return {
        "status": "success",
        "data": {
            "is_aadhaar": True,
            "uid": mock_data["uid"],
            "full_name": mock_data["full_name"],
            "gender": mock_data["gender"],
            "dob": mock_data["dob"],
            "address": mock_data["address"],
            "pincode": mock_data["pincode"],
            "perfection_score": 100,
            "address_status": "Perfect",
            "aadhaar_photo": mock_data["photo_url"]
        }
    }

@router.post("/upload-offline-xml")
async def upload_offline_xml_endpoint(file: UploadFile = File(...), password: str = Form(...)):
    return await process_offline_xml(file, password)

@router.post("/verify-face")
async def verify_face_endpoint(live_file: UploadFile = File(...), aadhaar_path: str = None):
    return await verify_face_logic(live_file, aadhaar_path)
