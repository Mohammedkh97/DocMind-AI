# Architecture Document

## Question 1 — The document is a bad scan. How do you extract data from it?

My strategy layers multiple techniques to handle degraded scans, because no single method works reliably on blurry documents:

**Image Preprocessing (OpenCV pipeline):**
Before any extraction, I apply a targeted enhancement pipeline:
1. **Bilateral denoising** — removes scan noise while preserving text edges (unlike Gaussian blur which destroys detail)
2. **CLAHE (Contrast Limited Adaptive Histogram Equalization)** — handles uneven lighting across the scan. CLAHE adapts contrast per-tile, so a dark corner and a bright center are both enhanced correctly
3. **Mild sharpening** — a conservative sharpening kernel recovers slightly blurred character edges without amplifying noise

**VLM-First Extraction (Gemini 2.5 Flash):**
The critical architectural decision is using a Vision-Language Model as the primary extractor, not OCR. VLMs reason about visual context — they understand that a blurry number next to a currency symbol is probably a price, that text inside a table row belongs to that row, and that a partially obscured HS code is still an HS code. Traditional OCR sees individual characters in isolation and fails more often on degraded regions.

**Confidence-Driven Flagging:**
For fields in blurry areas, the VLM reports lower self-assessed confidence. I combine this with OCR cross-validation (if PaddleOCR can also read the value, confidence increases) and format validation (if the value matches expected patterns like an 8-digit HS code, confidence increases). Fields below 60% confidence are flagged but **never silently skipped** — the consumer sees the best-guess value alongside a clear confidence signal.

**Re-extraction for critical fields:**
If a critical field (invoice number, grand total) comes back with very low confidence, the system applies more aggressive preprocessing (binarization, upscaling) and re-extracts just that region. This is a targeted retry, not a full re-process.

**What I explicitly chose NOT to do:**
I don't use aggressive binarization as a default preprocessing step. While it helps some OCR engines, it destroys color-coded information (like header backgrounds) that VLMs use as layout cues. The preprocessing is tuned for "just enough enhancement" rather than maximum OCR readability.

---

## Question 2 — What happens when the model returns invalid JSON?

I implemented a 4-layer JSON repair pipeline in `services/common/json_repair.py`. Here is the exact fallback chain:

**Layer 1: Direct Parse**
`json.loads(response)` — works approximately 85% of the time because I request `response_mime_type="application/json"` from Gemini, which constrains the output format.

**Layer 2: Regex Cleanup**
If direct parsing fails, I apply targeted regex repairs for the most common LLM JSON issues:
- Strip markdown code fences (` ```json ... ``` `) — models frequently wrap JSON in these
- Remove trailing commas before `}` or `]` — a common LLM habit that breaks strict JSON
- Remove single-line comments (`// ...`)
- Replace `NaN` and `Infinity` with `null` — not valid JSON but sometimes emitted
Then re-attempt parsing.

**Layer 3: Partial Extraction**
If cleanup fails, the response is likely truncated or wrapped in explanatory text. I use bracket-matching to find the largest valid JSON object within the string. This recovers partial results even from badly formatted output.

**Layer 4: Empty Structure**
If all layers fail (which I've never seen in testing with this document, but production systems must handle it), the API returns a valid JSON response with all fields set to `null` and confidence `0.0`. An internal `_parse_error: true` flag is set for monitoring.

**The guarantee:** The API *always* returns valid JSON. The `ExtractionResponse` Pydantic model enforces this at the serialization boundary — even if everything upstream fails, FastAPI serializes the default Pydantic model (with null values) into valid JSON.

---

## Question 3 — Which models did you use and why?

**Primary: Gemini 2.5 Flash (VLM extraction)**

I chose Gemini 2.5 Flash as the primary extraction engine for several specific reasons:

1. **Vision-native understanding**: Unlike OCR→LLM pipelines, Gemini processes the actual page image. It sees table borders, column alignment, header backgrounds, and spatial relationships that get lost when OCR flattens a document to text. For structured documents like invoices, this is a significant accuracy advantage.

2. **Native JSON mode**: Gemini's `response_mime_type="application/json"` constrains the output to valid JSON at the inference level, not just via prompt engineering. This dramatically reduces JSON repair needs.

3. **Cost efficiency**: At ~$0.10 per million input tokens for Flash, processing a 2-page document costs a fraction of a cent. GPT-4o is 3-5x more expensive for comparable quality on document extraction.

4. **Accuracy on degraded scans**: In my testing with the provided document (which has intentionally blurry areas), Gemini correctly extracted the partially obscured HS code and all table values, including the zero-value line item.

**Fallback: Gemini 2.0 Flash**

If the primary model fails (API error, timeout), I fall back to an older model version. This provides resilience without adding a second API provider's complexity.

**Validation: PaddleOCR (v4)**

PaddleOCR serves as an independent validation signal, not a primary extractor. I chose it over Tesseract because:
- PP-OCRv4 handles degraded scans significantly better (tested on this specific document)
- It provides bounding boxes natively, which I use for spatial cross-validation
- It runs locally with no API cost
- It has good CJK character support (relevant for Chinese shipper names)

**Why NOT other models:**
- **GPT-4o**: Comparable extraction quality but 3-5x the cost. For a production system processing thousands of documents, this adds up.
- **LayoutLMv3/Donut**: Require fine-tuning on domain-specific data. Zero-shot performance on unseen invoice layouts is poor. Not viable within a 72-hour timeline.
- **Tesseract**: Significantly worse on blurry scans compared to PaddleOCR. I benchmarked both on this document.

---

## Question 4 — Why is your compliance score deterministic?

The score is deterministic because the model is architecturally separated from the scoring process:

**Extraction (model-powered):** The VLM reads the document and outputs structured data. This is the only step where AI is involved.

**Scoring (code-powered):** Compliance scoring is pure Python code executing a fixed ruleset. Here's the chain:

```
ExtractionResponse → Rule 1: evaluate() → [issues] or []
                   → Rule 2: evaluate() → [issues] or []
                   → ...
                   → Rule N: evaluate() → [issues] or []
                   
All issues → sum(deductions) → score = 100 - total_deductions
```

Each rule is a pure function: `f(extracted_data) → list[ComplianceIssue]`. No model is called. No randomness. No temperature. No sampling.

**Concrete example:** The `MATH-002` rule checks if the subtotal equals the sum of line item amounts. This is pure arithmetic: `sum([4440, 3780, 2520, 0, 2040, 660]) = 13440 ≠ 13680`. The rule fires, deducts 15 points. This happens identically every time.

**Why this matters for customs compliance:** A logistics company needs to explain to a customs officer why a document scored 72. "The AI said so" is not acceptable. With this system, you can point to the RUBRIC.md file and say: "Rule MATH-002 found a $240 subtotal discrepancy — that's 15 points. Rule DATA-001 found a zero-value line item — that's 5 points." Every point is traceable.

The rules are defined in `RUBRIC.md` and implemented in `services/compliance/rules.py`. Adding or modifying a rule means editing the Python function and the rubric document — the scoring engine automatically picks up changes.

---

## Question 5 — If Cleargo needs to process 10,000 documents a day, what breaks first?

**First bottleneck: VLM API throughput and latency.**

Current architecture: Each document requires 2-3 API calls (classification + extraction per page), each taking ~2-4 seconds. Serial processing of 10,000 documents = ~20,000 API calls × 3 seconds = ~17 hours. That doesn't fit in a business day.

**Fix:** Async task queue with parallel processing.
- Add Celery + Redis as a task queue
- `POST /extract` becomes asynchronous — returns a `job_id` immediately, client polls for results
- Worker pool processes multiple documents in parallel (8-16 concurrent workers)
- With 10 parallel workers and 3s/call, throughput = ~10,000 docs in ~1.7 hours

**Second bottleneck: Memory pressure from PDF→image conversion.**

Each page rendered at 200 DPI produces a ~5-10MB image in memory. 10,000 documents × 2 pages = 20,000 images. Even with streaming, worker memory can spike.

**Fix:** 
- Process pages sequentially within each document (stream, don't batch)
- Delete intermediate images immediately after extraction
- Set container memory limits and horizontal scale
- Consider reducing DPI to 150 for bulk processing (configurable trade-off)

**Third bottleneck: Result storage.**

10K documents/day × 365 days = 3.65M documents/year. Each extraction result is ~5-10KB of JSON. That's manageable in PostgreSQL, but the original PDFs (200KB-5MB each) need object storage.

**Fix:**
- PostgreSQL for extraction results and compliance scores (indexed, queryable)
- S3/MinIO for original PDFs and rendered images
- Data retention policy (archive after 90 days, delete images after 30 days)

**Fourth bottleneck: Gemini API rate limits.**

Google's rate limits for Gemini Flash are generous but not unlimited. At 10K docs × 3 calls = 30K calls/day, you might hit per-minute limits.

**Fix:**
- Implement request queuing with rate limiter (token bucket)
- Spread processing across the day rather than bursting
- Consider Gemini batch API for non-urgent processing
- Multi-provider fallback (GPT-4o as secondary provider)

**What I would NOT do:** Self-host an open-source VLM. The operational overhead of GPU infrastructure, model serving, and reliability engineering is not worth it until you're well past 100K docs/day and have a dedicated ML platform team.

---

## Question 6 — How would you prove to a client that the system is 90% accurate?

Accuracy means different things for extraction versus compliance, and confusing them is a common mistake.

**Extraction accuracy — field-level correctness:**

1. **Build an evaluation dataset:** Annotate 50-100 documents with ground-truth values (every field manually verified). This is labor-intensive but essential.

2. **Measure per-field accuracy:** For each field, compare extracted value to ground truth:
   - **Text fields** (names, ports): Use fuzzy matching (Levenshtein similarity > 0.9 counts as correct). OCR might extract "ShanghaiTex" vs "Shanghai Tex" — both are correct.
   - **Numeric fields** (amounts, quantities): Exact match (within rounding tolerance of $0.01).
   - **Date fields**: Parse to canonical format and compare.

3. **Report:** Accuracy = (correct extractions / total fields) per document. Report both field-level and document-level accuracy, plus per-field-type breakdowns.

4. **90% target interpretation:** 90% means that on average, 9 out of 10 fields are extracted correctly. But I'd go further and report the **95th percentile** — how bad is the worst 5%? A system that's 95% accurate on average but catastrophically wrong on some documents is not production-ready.

**Compliance accuracy — issue detection correctness:**

Compliance accuracy has two dimensions:

1. **Precision:** Of the issues the system flags, how many are actually real issues? (Avoid false positives — flagging correct values as problems.)

2. **Recall:** Of the actual issues in the document, how many does the system catch? (Avoid false negatives — missing real problems.)

For customs compliance, **recall is more important than precision.** A missed critical issue (e.g., subtotal mismatch not detected) can lead to customs delays or fines. A false alarm (flagging something that's actually fine) just means a human reviews it unnecessarily.

**Measurement approach:** For compliance, annotate the evaluation dataset with known issues (human expert identifies all compliance problems). Then measure:
- Precision = true positives / (true positives + false positives)
- Recall = true positives / (true positives + false negatives)
- F1 score = 2 × (precision × recall) / (precision + recall)

**Ongoing monitoring:** Deploy with a human-in-the-loop for the first 30 days. Track when humans override the system's extraction or compliance findings. Use these overrides to continuously improve extraction prompts and compliance rules.
