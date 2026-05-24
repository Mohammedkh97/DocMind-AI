# System Architecture & Design Decisions

## Question 1 — The document is a bad scan. How do you extract data from it? What is your strategy for fields where the scan is blurry or unreadable?

**1. Multimodal AI over Legacy OCR:** 
Our primary extractor is a Vision-Language Model (Gemini 2.5 Flash). Unlike traditional OCR pipelines (which blindly convert pixels to text and lose spatial context), VLMs process the image natively. This makes them significantly more resilient to visual noise, skew, and low DPI scans because they infer context from the surrounding layout.

**2. Image Preprocessing Pipeline:**
Before the image hits the model, it passes through our `DocumentPreprocessor`. We use OpenCV to apply grayscale conversion, contrast enhancement (CLAHE), and adaptive thresholding to clean up blurry artifacts and sharpen text.

**3. Probabilistic Field Extraction:**
We don't force the model to blindly guess. In our prompts, we explicitly enforce a confidence-scoring schema: 
*   **Instruction:** `"For EVERY field, provide a confidence score from 0.0 to 1.0."`
*   **Blurry Fields:** `"If a field is blurry, provide your best guess but set confidence LOW (< 0.5)."`
*   **Unreadable Fields:** `"If completely unreadable, set value to null and confidence to 0.0."`

We use these confidence scores in our `ConfidenceScorer` to track data quality. If an extracted field has critically low confidence, we can trigger our secondary fallback (PaddleOCR) to attempt a cross-validation patch, or flag it for human review in the frontend dashboard.

---

## Question 2 — What happens when the model returns invalid JSON? Walk through your exact fallback logic, step by step.

Even with strict prompting, LLMs occasionally hallucinate malformed JSON (e.g., trailing commas, missing brackets). We handle this gracefully via a robust fallback pipeline:

**Step 1: Interception:** The raw string output from the VLM is intercepted by our `safe_parse_json` utility.
**Step 2: String Sanitization:** We aggressively strip away markdown fences (e.g., ````json ... ````), leading/trailing whitespace, and structural anomalies. We then attempt standard `json.loads`.
**Step 3: Algorithmic Repair:** If standard parsing fails, we pass the string into the `json-repair` library. This library uses a state-machine parser to aggressively infer and inject missing brackets, remove illegal trailing commas, and fix unquoted keys.
**Step 4: Graceful Degradation:** If the JSON is entirely unsalvageable (a severe hallucination), the parser catches the exception and returns an empty dictionary `{}` alongside a `repair_needed=True` flag. This ensures the pipeline logs a warning but **never crashes**. The orchestrator will simply yield an empty Pydantic model with a warning attached to the metadata.

---

## Question 3 — Which model or models did you use and why? If you used different models for different parts of the pipeline, explain the logic behind that.

**Primary Model: Gemini 2.5 Flash**
We chose this model because it is natively multimodal, highly cost-effective, and exceptionally fast. It completely bypasses the fragile "OCR -> Text -> LLM" pipeline by "reading" the image directly.

**Logic: The Agentic Router Pattern**
Instead of using one massive "catch-all" prompt, we use an Agentic Router pattern to maximize accuracy. 
1. We first hit the model with a tiny, fast prompt to **classify** the page (`commercial_invoice`, `packing_list`, etc.).
2. Based on the classification, we route the image to a highly optimized, specialized prompt containing a strict JSON schema tailored specifically to that document type.

By spending 1 cheap request to classify the document first, the 2nd request is incredibly narrow in scope. This drastically reduces hallucination rates (e.g., it prevents the model from hallucinating invoice fields on a packing list). We also run this sequence concurrently across all pages using `asyncio.gather` to cut processing time in half.

**Secondary Model: PaddleOCR (Optional Fallback)**
We integrated PaddleOCR as a specialized fallback. While VLMs are incredible at layout understanding, they can sometimes hallucinate exact alphanumeric strings (like complex tracking numbers). We use OCR solely to extract raw strings and use Levenshtein distance to cross-validate low-confidence VLM extractions.

---

## Question 4 — Why is your compliance score deterministic? How did you make sure the model is not just generating a number on its own?

**Total Decoupling of AI and Logic.**
Our compliance score is mathematically guaranteed to be deterministic because **the AI model is not involved in scoring at all.**

The VLM is strictly relegated to *data extraction* (Image -> JSON). Once the orchestrator returns the structured, strictly-typed Pydantic model (`ExtractionResponse`), the AI's job is over.

The frontend then passes this JSON to the `/compliance-score` endpoint, which is powered by our `ComplianceEngine`. This engine is written in **100% pure Python logic**. It runs hardcoded rules over the data:
*   *Math checks:* `sum(line_items) == subtotal`
*   *Cross-document checks:* `invoice.total_gross_weight == packing_list.total_gross_weight`
*   *Completeness checks:* `invoice.date is not None`

Because it relies purely on algorithmic logic, passing the exact same extracted JSON into the engine will result in the exact same score, grade, and list of deductions every single time. It executes in less than 10 milliseconds.

---

## Question 5 — If Cleargo needs to process 10,000 documents a day, what breaks first in your current setup? What would you change?

If we instantly scaled to 10,000 documents a day, the system would face two catastrophic failures:

1. **API Rate Limiting (429 Errors):** We are currently executing concurrent requests against a single Gemini API key. Processing ~7 documents a minute continuously would rapidly exhaust the free-tier RPM/TPM limits, causing cascading failures.
    *   **Fix:** Migrate from the consumer API to Google Cloud Vertex AI using Provisioned Throughput to guarantee API bandwidth.
2. **Synchronous HTTP Connection Timeouts:** The `/extract` endpoint holds the HTTP request open while it waits for the VLM to process the document (~25-30 seconds). At 10k documents/day, the default ASGI server workers (Uvicorn) would quickly deplete, resulting in `504 Gateway Timeouts` for incoming users.
    *   **Fix:** Implement an **Asynchronous Task Queue (e.g., Celery + Redis)**. The `/extract` endpoint would instantly return a `job_id`. Background workers would process the document from a queue, and the frontend would poll for status or listen via WebSockets.
3. **Local File System Exhaustion:** We currently dump extraction artifacts and JSONs to a local `./outputs` directory. This is not horizontally scalable.
    *   **Fix:** Migrate to cloud storage (AWS S3 / GCS) for artifacts, and a relational database (PostgreSQL) for structured extraction metadata.

---

## Question 6 — How would you prove to a client that the system is 90% accurate? What does accuracy mean differently for extraction versus compliance scoring?

Proving accuracy requires splitting the definition of "accuracy" between the two completely different halves of the pipeline.

**1. Extraction Accuracy (The AI)**
Extraction accuracy measures: *Did the model correctly pull the data from the image?*
To prove this, we would build a Golden Dataset of hundreds of pre-annotated, diverse documents. We run the pipeline against this dataset and compute:
*   **Exact Match (EM) Rate:** What percentage of fields were extracted flawlessly?
*   **Levenshtein Distance:** For typos, how many characters were off?
*   **F1 Score:** To measure precision (no hallucinations) and recall (no missed fields).
We prove the system is "90% accurate" by showing the client an automated benchmark script that outputs an EM rate of >90% across the dataset.

**2. Compliance Scoring Accuracy (The Logic)**
Compliance accuracy measures: *Did the engine apply the business rules correctly?*
Because the scoring is 100% deterministic code, we prove accuracy via **Unit Testing**. We write tests providing mocked JSON payloads containing specific errors (e.g., mismatched weights, bad math).
If the test suite covers 100% of the business rules and all tests pass, the compliance scoring is technically **100% accurate** by definition. We prove this to the client by showing them our continuous integration (CI) pipeline passing all business-logic unit tests.
