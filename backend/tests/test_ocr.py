import asyncio
import os
import sys
from PIL import Image

# Ensure backend directory is in the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from services.extraction.ocr_extractor import OCRExtractor

async def main():
    print("Initializing OCRExtractor...")
    extractor = OCRExtractor()
    
    # The image path is relative to the backend directory (or /app inside Docker)
    image_path = "assets/assignment/page_1.png"
    
    if not os.path.exists(image_path):
        print(f"Error: Could not find image at {image_path}")
        return
        
    print(f"Loading image from {image_path}...")
    img = Image.open(image_path).convert('RGB')
    
    print("Running extraction...")
    try:
        result = await extractor.extract_text(img)
        print("\n--- Extraction Result ---")
        import json
        print(json.dumps(result, indent=2, default=str))
    except Exception as e:
        print(f"Extraction failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
