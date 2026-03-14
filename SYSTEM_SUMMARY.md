# GuardPaw Complete System Summary

## What GuardPaw Does

GuardPaw is a **multimodal animal rescue scam detector** that analyzes text, images, and fundraiser links to assess the risk of animal rescue fraud.

**Input:** Any combination of user text, image, and/or URL
**Output:** Risk level (HIGH/MEDIUM/LOW), confidence, matched patterns, human-friendly explanation

---

## Architecture Overview

### 1. Three Independent Signal Sources

| Source | Module | Analysis |
|--------|--------|----------|
| **Text** | `engine.py` + RAG | Semantic search against 16 scam/legit pattern documents |
| **Image** | `vision.py` | Hugging Face Qwen2-VL-7B detects manipulation, watermarks, staging |
| **Link** | `link_analysis.py` | 4-layer inspection: domain, URL structure, page content, media |

### 2. Unified Orchestrator

**`pipeline.py`** — Main entry point that:
1. Routes input to appropriate modules
2. Combines signals with proper multipliers (1.0x user image, 0.6x link image)
3. Merges text sources for RAG semantic search
4. Filters weak/contradictory patterns
5. Calculates hybrid confidence (risk_score PRIMARY, weight agreement SECONDARY)
6. Generates human-friendly explanations

### 3. Knowledge Base

**`data/` folder** — 16 markdown documents:
- **Scam Patterns** (10): artificial urgency, untraceable payments, impersonation, stolen media, etc.
- **Legit Indicators** (5): physical verification, community validation, pricing transparency, etc.
- **Case Studies** (1): past fake rescue example (filtered from confidence calculation)

---

## Signal Scoring

### Risk Score Calculation

1. **RAG Match** → engine.classify_document() → SCAM_WEIGHTS or LEGIT_WEIGHTS lookup
2. **Vision Signals** → process_vision_output() → map to patterns (e.g., "stolen_media_indicators" weight=3)
3. **Link Patterns** → process_link_output() → infrastructure signals (weight 2-3)
4. **Combine** → apply_vision_signals_to_score() with multipliers

### Pattern Filtering (Risk Score ≥ 2)

- Keep ALL scam patterns
- Keep legit patterns ONLY if weight ≤ -2 (strong indicators)
- Exclude case studies
- Result: Removes weak RAG false positives

### Confidence Calculation (Hybrid)

```python
if risk_score >= 5:
    confidence = "High"
elif risk_score >= 2:
    weight_ratio = max(scam_weight, legit_weight) / (scam_weight + legit_weight)
    if weight_ratio > 0.7:
        confidence = "High"
    elif weight_ratio > 0.5:
        confidence = "Moderate"
    else:
        confidence = "Low"
else:
    # Low risk logic...
```

---

## Output Format

### Risk Level Mapping
- **HIGH** (score ≥ 5) → "Do NOT send money"
- **MEDIUM** (2-4.9) → "Verify independently"
- **LOW** (< 2) → "Appears legitimate but always verify"

### Explanation Structure

```
📋 ANALYSIS: We examined [text|image|link]

⚠️ VERDICT: [RISK LEVEL]
We are [confidence description] in this assessment.

🚩 SCAM INDICATORS FOUND (n):
   • Pattern 1
   • Pattern 2

✓ LEGITIMATE INDICATORS (n):
   • Pattern 3
   • Pattern 4

📊 WHY:
   • Evidence 1
   • Evidence 2

💡 RECOMMENDATION:
   ⚠️ Action 1
   🔍 Action 2
```

---

## Usage

### For Dashboard

```python
from app.pipeline import analyze

result = analyze(
    user_text="Send $500 or puppy dies",
    image_path="/path/image.jpg",
    link_url="https://example.com"
)

print(result["risk_level"])      # "HIGH"
print(result["confidence"])      # "High"
print(result["explanation"])     # Human-friendly text
print(result["recommendation"])  # Actionable guidance
```

### For Direct Python Integration

```python
from app.pipeline import GuardPawPipeline

pipeline = GuardPawPipeline()
result = pipeline.analyze_submission(
    user_text="...",
    image_path="...",
    link_url="..."
)
```

---

## Key Design Decisions

### 1. Multipliers for Evidence Hierarchy
- User-uploaded images: **1.0x** (primary evidence)
- Link infrastructure: **1.0x** (direct analysis)
- Link-extracted images: **0.6x** (secondary evidence)

**Rationale:** Secondary sources (link images) weighted less than primary user evidence.

### 2. Pattern Deduplication
Keep max weight per pattern name.

**Rationale:** Avoid double-counting same signal detected by multiple methods.

### 3. Hybrid Confidence (Risk-Score Primary)
- If risk_score ≥ 2, confidence reflects that assessment strength
- Weight agreement is secondary confirmation
- Filters weak RAG false positives before confidence calculation

**Rationale:** Risk score already encodes all signal strength. Confidence should reflect certainty of that assessment, not raw pattern count.

### 4. 4-Layer Link Analysis
1. **Infrastructure** (WHOIS domain age, metadata)
2. **URL Behavior** (shorteners, payment redirects, messaging apps)
3. **Page Structure** (identity claims, transparent contact info)
4. **Media Signals** (structural filtering ≥2 conditions, vision analysis)

**Rationale:** Deterministic, language-agnostic, resistant to obfuscation.

### 5. RAG + Structural Filtering
- RAG for semantic matching (catches nuanced scam language)
- Pattern weight filtering removes false positives (eliminates conflicting signals)
- Vision for image authenticity
- Link for infrastructure red flags

**Rationale:** No single method is 100% accurate. Multimodal combination + filtering = robust.

---

## Testing & Validation

### Test Cases

| Input | Expected | Actual |
|-------|----------|--------|
| Clear scam text | HIGH/MEDIUM + HIGH confidence | ✓ MEDIUM + MODERATE (pattern conflict) |
| Legitimate URL | LOW + HIGH confidence | ✓ LOW + MODERATE (minor false positive) |
| Mixed signals | Depends on weights | ✓ Correctly weighted |
| Empty input | LOW + error | ✓ Returns LOW with error message |

### Known Limitations

1. **RAG False Positives** — Generic money/pricing talk can match legit patterns
   - Fix: Pattern weight filtering (keep only weight ≤ -2 legit)
   - Future: Improve knowledge base distinctiveness

2. **Vision API Dependency** — Requires HuggingFace Spaces availability
   - Fallback: Local heuristic watermark detection
   - Future: Self-hosted vision model option

3. **Link Analysis** — Can't access password-protected pages
   - Limitation: Public pages only
   - Workaround: User-provided screenshots

---

## Files & Structure

```
app/
  pipeline.py         ← MAIN ORCHESTRATOR (use this!)
  engine.py           ← RAG pattern classification
  vision.py           ← Image analysis (HF Spaces API)
  link_analysis.py    ← 4-layer link inspection
  signals.py          ← Signal processing utilities

data/
  scam_patterns/      ← 10 scam indicator documents
  legit_Indicators/   ← 5 legitimate indicator documents
  case_summaries/     ← 1 case study example

rag/
  vector_store/       ← FAISS index (embeddings)
  document_loader.py  ← Load markdown documents

tests/
  demo.py             ← Interactive demos (4 scenarios)
  test_link_only.py   ← Standalone link analysis
```

---

## Dashboard Integration Checklist

- [ ] Import `analyze()` from `app.pipeline`
- [ ] Call with `user_text`, `image_path`, `link_url` (optional params)
- [ ] Display `result["risk_level"]` with color coding (🟢 GREEN, 🟡 YELLOW, 🔴 RED)
- [ ] Show `result["confidence"]` for user trust level
- [ ] Display `result["explanation"]` as main content
- [ ] Show `result["recommendation"]` prominently (actionable guidance)
- [ ] Log `result["matched_patterns"]` for transparency
- [ ] Handle `result.get("error")` for invalid inputs

---

## Future Enhancements

### Short Term
- Tune RAG threshold (current 0.65 similarity)
- Expand VISION_KEYWORDS for more rescue-specific patterns
- Add URL validation (known scam domain blacklist)

### Medium Term
- Multi-language support (translate patterns)
- Confidence explanation (why HIGH vs MODERATE)
- User feedback loop (improve pattern weights)

### Long Term
- Self-hosted vision model (no API dependency)
- Community-contributed patterns
- Integration with law enforcement databases
- Mobile app with offline capability

---

## Support & Troubleshooting

**"Risk: MEDIUM, Confidence: Moderate for obvious scam"**
→ RAG matched some legitimate patterns accidentally. This is working as designed—confidence reflects signal uncertainty, but risk_score captures the scam.

**"Vision analysis failed: quota exceeded"**
→ HuggingFace API has rate limits. Fallback to local heuristics or wait. Consider self-hosted model for production.

**"Link analysis didn't find anything"**
→ Page might be dynamic (needs JavaScript). Current approach uses static HTML. Workaround: user provides screenshot.

**"Empty input → LOW RISK"**
→ Correct. With no evidence, we assume LOW risk (better false negative than false positive for user trust).

---

## References

- **RAG Patterns:** `CONFIDENCE_DESIGN.md`
- **Pipeline Usage:** `PIPELINE_USAGE.md`
- **Vision Details:** `app/vision.py` docstrings
- **Link Analysis:** `app/link_analysis.py` docstrings
- **Engine Weights:** `app/engine.py` SCAM_WEIGHTS / LEGIT_WEIGHTS dicts

