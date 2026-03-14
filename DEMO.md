# 🐾 GuardPaw Live Demo

See GuardPaw in action: text-only analysis → multimodal (text + image) → risk scoring.

## Quick Start

```bash
python tests/demo.py
```

This runs two scenarios on the same rescue scam:

### Demo 1: Text-Only Analysis
- User description: Emergency puppy rescue, $3k surgery needed, euthanasia in 3 hours, asks for Zelle payment
- **RAG retrieves:** 5 matching patterns (3 scam, 2 legit)
- **Risk Score:** 3 (Medium)
- **Confidence:** Moderate
- **Recommendation:** ⚠️ Investigate further. Verify rescue identity independently.

### Demo 2: Same Text + Image
- Same user text as Demo 1
- **Vision analysis** of distressed puppy image
- **Qwen2-VL-7B identifies:** Potential manipulation, lighting inconsistencies
- **Merged multimodal query** sent to RAG (text + image forensic description)
- **Risk Score:** 6 → **9.0** (vision signals injected)
- **Confidence:** Moderate
- **Matched patterns:** 4 scam signals + stolen media indicators
- **Recommendation:** ⛔ **LIKELY SCAM — Do NOT donate**

## Why This Matters

The image analysis **flipped the risk from Medium → High**:

1. **Text alone** found urgency + unverified rescue → Medium (conflicting signals)
2. **Text + image** found stolen/manipulated media → High (reinforces scam pattern)

This is **hybrid AI done right**: deterministic keyword inference + semantic RAG + vision signals.

## What GuardPaw Does

```
User Input (text + image)
    ↓
[Vision Analysis] — Qwen2-VL-7B describes image for manipulation/authenticity
    ↓
[Keyword Inference] — Rule-based signal extraction (stolen_media_indicators, etc)
    ↓
[Multimodal RAG] — Merged query (text + image) searches knowledge base
    ↓
[Risk Scoring] — Weighted heuristic + vision signal injection
    ↓
[Explainable Report] — Matched patterns, confidence, recommendation
```

## Running Standalone

You can also test with your own image:

```bash
export IMAGE_PATH=path/to/your/image.jpg
python -m app.engine
```

Or programmatically:

```python
from app.vision import GuardPawVision
from app.engine import GuardPawEngine
from rag.vector_store.search_index import build_or_load_index

# Analyze image
gv = GuardPawVision()
vision_output = gv.analyze_image("rescue_photo.jpg")
text_blob, vision_signals = gv.process_vision_output(vision_output)

# Merge with user text
user_text = "Help! Puppy injured, $3k surgery, send Zelle..."
query = gv.merge_with_user_text(user_text, text_blob)

# Search RAG
index = build_or_load_index()
docs = index.similarity_search(query, k=5)

# Generate report + inject vision scores
engine = GuardPawEngine()
report = engine.generate_report(docs)
risk_score, matched = gv.apply_vision_signals_to_score(
    report["summary"]["risk_score"],
    vision_signals,
    [item["source"] for item in report["items"]]
)
```

## Confidence Levels

- **High:** 4+ scam patterns OR image + text both flag issues
- **Moderate:** Mixed signals (some scam, some legit patterns found)
- **Low:** Fewer than 2 matches OR mostly legit indicators

## Next Steps

- [ ] Integrate into a web UI (Flask/Streamlit)
- [ ] Add URL/domain validation (Whois checks)
- [ ] Expand vision keywords (more rescue-specific patterns)
- [ ] User feedback loop (improve scoring weights)
