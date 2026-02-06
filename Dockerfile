FROM python:3.10-slim

# Install system dependencies required for DeepFace, OpenCV, PyTesseract, PDF2Image, and PyZbar
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    libzbar0 \
    libgl1 \
    libgl1-mesa-dri \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port (Hugging Face Spaces defaults to 7860)
EXPOSE 7860

# Run the application
# Using shell form to allow variable expansion if you decide to set different ports
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
