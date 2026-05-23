"""
Pipeline output saving utility.

Saves original page images, enhanced page images, composite JSON,
and raw VLM extraction text (as Markdown files) to the outputs directory.
"""

import json
import time
import re
from pathlib import Path
from PIL import Image
from core.logging import get_logger

logger = get_logger("output_saver")

def save_pipeline_outputs(
    filename: str,
    pages: list[dict],
    raw_vlm_texts: dict[int, str],
    extraction_response: dict
) -> Path | None:
    """
    Saves the pipeline extraction assets to the outputs directory.

    Dumps:
    - Original page images: page_{num}_original.png
    - Enhanced page images: page_{num}_enhanced.png
    - JSON extraction result: extraction_output.json
    - Raw VLM text: raw_extracted_page_{num}.md
    """
    try:
        # Determine base outputs directory
        outputs_base = Path("outputs")
        if Path.cwd().name == "backend":
            outputs_base = Path("../outputs")
        outputs_base.mkdir(parents=True, exist_ok=True)

        # Create a unique directory name for this run
        timestamp = int(time.time())
        clean_filename = re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)
        run_id = f"extract_{timestamp}_{clean_filename}"

        run_dir = outputs_base / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # Save page images
        for page in pages:
            page_num = page.get("page_number", 1)

            # Save original image
            original_img = page.get("original_image")
            if isinstance(original_img, Image.Image):
                original_img.save(run_dir / f"page_{page_num}_original.png")

            # Save enhanced image
            enhanced_img = page.get("enhanced_image")
            if isinstance(enhanced_img, Image.Image):
                enhanced_img.save(run_dir / f"page_{page_num}_enhanced.png")

        # Save raw VLM text as Markdown files
        for page_num, text in raw_vlm_texts.items():
            md_path = run_dir / f"raw_extracted_page_{page_num}.md"
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(text)

        # Write JSON output
        json_path = run_dir / "extraction_output.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(extraction_response, f, indent=2, ensure_ascii=False)

        logger.info(
            "pipeline_outputs_saved",
            run_id=run_id,
            output_dir=str(run_dir)
        )
        return run_dir

    except Exception as e:
        logger.error(
            "failed_to_save_pipeline_outputs",
            filename=filename,
            error=str(e)
        )
        return None
