import sys
import asyncio
from pathlib import Path
import os

# Ensure backend modules can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.extraction.agentic_doc_extractor import AgenticDocumentExtractor

async def main():
    if len(sys.argv) < 2:
        print("Usage: python test_ade.py <path_to_image_or_pdf>")
        sys.exit(1)
        
    file_path = sys.argv[1]
    
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        sys.exit(1)
        
    print(f"Reading file: {file_path}...")
    with open(file_path, "rb") as f:
        image_bytes = f.read()
        
    print("\nInitializing AgenticDocumentExtractor...")
    extractor = AgenticDocumentExtractor()
    
    if not extractor.client:
        print("ERROR: Landing AI client failed to initialize. Make sure LANDING_AI_API_KEY is in your .env file.")
        sys.exit(1)
    
    print("\nStarting ADE extraction...")
    print("This will upload the file, create a parse job, and poll until completion.")
    
    try:
        # We use extract_invoice, but ADE essentially just extracts raw markdown 
        # regardless of whether we call extract_invoice or extract_packing_list.
        structured_data, repair_needed, raw_text = await extractor.extract_invoice(image_bytes=image_bytes)
        
        print("\n" + "="*50)
        print("✅ EXTRACTION COMPLETE")
        print("="*50)
        
        print("\n--- Raw Markdown Extracted ---")
        print(raw_text)
        
        print("\n--- Structured Data (Expected empty for ADE fallback) ---")
        print(structured_data)
        
    except Exception as e:
        print(f"\n❌ Extraction failed: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
