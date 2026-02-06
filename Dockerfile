FROM python:3.10-slim

# Install system dependencies
# libgl1 and libglib2.0-0 are required for OpenCV (even headless sometimes needs base libs)
# tesseract-ocr and libzbar0 are for OCR and QR Code scanning
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    libzbar0 \
    libgl1 \
    libgl1-mesa-dri \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set up a new user named "user" with user ID 1000 to match Hugging Face default permissions
RUN useradd -m -u 1000 user

# Switch to the "user" user
USER user

# Set environment variables
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# Set working directory
WORKDIR $HOME/app

# Copy imports first for caching
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY --chown=user . .

# Create directory for local storage and ensure it's writable
RUN mkdir -p saved_images

# Expose the port
EXPOSE 7860

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
