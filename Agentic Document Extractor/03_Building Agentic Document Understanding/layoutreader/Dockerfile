FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for OpenCV and building packages
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1-mesa-glx \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements if any
COPY requirements.txt .

# Install PyTorch (CPU version is sufficient for fallback extraction if GPU unavailable, 
# but installing standard which includes CUDA support if run on GPU host)
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Install other dependencies including FastAPI
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir fastapi uvicorn pydantic

# Pre-download the layoutreader model so it's baked into the image
RUN python -c "from transformers import AutoModelForTokenClassification; AutoModelForTokenClassification.from_pretrained('hantian/layoutreader')" || true

# Copy all the application files
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
