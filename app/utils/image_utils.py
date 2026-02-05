import base64
import os

def image_to_base64(file_path):
    """Converts an image file to a base64 string for DB storage."""
    if not file_path or not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            # Determine mime type from extension
            ext = file_path.lower().split('.')[-1]
            mime_type = f"image/{ext}" if ext != 'jpg' else "image/jpeg"
            return f"data:{mime_type};base64,{encoded_string}"
    except Exception as e:
        print(f"Error encoding image: {e}")
        return None
