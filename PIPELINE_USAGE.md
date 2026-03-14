# GuardPaw Pipeline Usage Guide

## Overview

`app/pipeline.py` is the **unified entry point** for all GuardPaw analysis. It orchestrates:
- Text analysis (RAG semantic search)
- Image analysis (vision detection)
- Link analysis (infrastructure + page text + images)
- Signal combination and scoring
- Risk assessment and reporting

This is what your **dashboard should call**.

---

## Quick Start

### Method 1: Direct Function Call

```python
from app.pipeline import analyze

# Analyze with any combination of inputs
result = analyze(
    user_text="Send money now or puppy dies",
    image_path="/path/to/image.jpg",  # optional
    link_url="https://example.com"     # optional
)

print(f"Risk: {result['risk_level']}")      # HIGH|MEDIUM|LOW
print(f"Score: {result['risk_score']}")     # numeric (0-10+)
print(f"Confidence: {result['confidence']}")  # High|Moderate|Low
```

### Method 2: Using Pipeline Class

```python
from app.pipeline import GuardPawPipeline

pipeline = GuardPawPipeline()

result = pipeline.analyze_submission(
    user_text="...",
    image_path="...",
    link_url="..."
)
```

### Method 3: Singleton Pattern (Reuse Instance)

```python
from app.pipeline import get_pipeline

pipeline = get_pipeline()  # Reuses same instance across calls
result = pipeline.analyze_submission(...)
```

---

## Input Parameters

### `user_text` (str, optional)
Human-provided text describing the request.

```python
user_text = "They're asking for $500 to rescue a dog"
```

### `image_path` (str, optional)
Local file path to image. **Must exist**.

```python
image_path = "/home/user/suspicious_image.jpg"
```

### `link_url` (str, optional)
URL to analyze.

```python
link_url = "https://example.com/donation"
```

---

## Return Value

All methods return a **structured dict**:

```python
{
    "risk_level": "HIGH",                    # HIGH|MEDIUM|LOW
    "risk_score": 7.2,                       # numeric score
    "confidence": "High",                    # High|Moderate|Low
    
    "matched_patterns": [
        {
            "name": "stolen_media_indicators.md",
            "category": "Scam Pattern",
            "weight": 3.0,
            "source": "image"                # text|image|link|link_image
        },
        {
            "name": "pricing_and_transparency.md",
            "category": "Legit Indicator",
            "weight": 1.0,
            "source": "text"
        }
    ],
    
    "signals": {
        "text": {
            "input": "First 100 chars of text...",
            "status": "analyzed"
        },
        "image": {
            "description": "Vision analysis description",
            "signals": 2,                    # number of signals detected
            "status": "analyzed"
        },
        "link": {
            "url": "https://...",
            "infrastructure_signals": 1,
            "page_title": "Donation Page",
            "images_found": 3,
            "status": "analyzed"
        }
    },
    
    "explanation": "Risk Score: 7.2\nDetected 3 scam indicators...",
    "recommendation": "⚠️ HIGH RISK: Strong evidence of scam...",
    
    "input_summary": {
        "has_text": True,
        "has_image": True,
        "has_link": True
    }
}
```

### explanation Field

Human-friendly breakdown that answers:
1. **What was analyzed** — Text? Image? Link?
2. **What's the verdict** — Risk level & confidence
3. **What patterns** — Specific scam/legit indicators
4. **Why** — Evidence-based reasoning
5. **What to do** — Actionable next steps

**Example:**
```
📋 ANALYSIS: We examined text description and fundraiser link

⚠️ VERDICT: MEDIUM RISK — Suspicious activity detected
We are reasonably confident in this assessment.

🚩 SCAM INDICATORS FOUND (2):
   • Artificial Urgency Deadlines (from TEXT)
   • Untraceable Payments Requests (from TEXT)

✓ LEGITIMATE INDICATORS (1):
   • Pricing And Transparency (from TEXT)

📊 WHY:
   • Found 2 scam indicator(s) suggesting potential fraud
   • Also found 1 legitimate indicator(s)
   • Some conflicting signals, but scam indicators are stronger

💡 RECOMMENDATION:
   ⚠️ Proceed with caution
   🔍 Verify the rescue organization independently
   📞 Call or visit the official organization directly
   💰 Use secure payment methods
```

---

## Risk Levels

| Level | Score Range | Meaning |
|-------|-------------|---------|
| **HIGH** | ≥ 5 | Strong scam indicators, high confidence |
| **MEDIUM** | 2–4.9 | Mixed signals or some scam indicators |
| **LOW** | < 2 | Few/no scam indicators or legitimate indicators present |

---

## Confidence Levels

| Level | When |
|-------|------|
| **High** | ≥80% of patterns point same direction (all scam OR all legit) |
| **Moderate** | Mixed signals or moderate number of patterns |
| **Low** | Very few patterns detected or conflicting signals |

---

## Examples

### Example 1: Text Only (No Image, No Link)

```python
result = analyze(
    user_text="Send $500 via gift card or the puppy dies in 1 hour"
)

# Output
{
    "risk_level": "HIGH",
    "risk_score": 6.5,
    "confidence": "High",
    "matched_patterns": [
        {"name": "artificial_urgency_deadlines.md", "source": "text", "weight": 3},
        {"name": "untraceable_payments_requests.md", "source": "text", "weight": 3},
    ],
    "recommendation": "⚠️ HIGH RISK: Clear scam indicators..."
}
```

### Example 2: Link Only

```python
result = analyze(
    link_url="https://bestfriends.org/how-you-can-help"
)

# Output
{
    "risk_level": "LOW",
    "risk_score": -2.2,
    "confidence": "Moderate",
    "matched_patterns": [7 total],  # Mix of legit indicators
    "signals": {
        "link": {
            "page_title": "How you can help homeless pets",
            "images_found": 2,
            "infrastructure_signals": 1
        }
    }
}
```

### Example 3: Text + Image + Link

```python
result = analyze(
    user_text="Send money now",
    image_path="/tmp/suspicious.jpg",
    link_url="https://suspicious.com"
)

# Combines all three signal sources:
# - RAG semantic search on merged query
# - Vision analysis on user image (1.0x weight)
# - Link infrastructure analysis
# - Vision analysis on link-extracted images (0.6x weight)
```

---

## Source Tracking

Each pattern includes a **`source`** field showing where it came from:

- **`text`** — Matched via RAG semantic search on user text or page text
- **`image`** — Detected via vision analysis on user-uploaded image
- **`link`** — Detected via link infrastructure analysis (domain, URL, metadata)
- **`link_image`** — Detected via vision analysis on images extracted from link

This helps the dashboard explain **WHY** each pattern was detected.

---

## Error Handling

Pipeline handles gracefully:

1. **Missing file** → Returns error message in result
2. **RAG search fails** → Continues with direct pattern matching
3. **Image analysis fails** → Continues with text+link
4. **Link download fails** → Continues with text+image
5. **No input provided** → Returns LOW risk with error message

```python
result = analyze()  # Empty call

print(result["error"])        # "No input provided"
print(result["risk_level"])   # "LOW"
```

---

## For Dashboard Integration

### Recommended Flow

```python
from app.pipeline import analyze
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/analyze', methods=['POST'])
def analyze_submission():
    # Get form data
    user_text = request.form.get('text', '')
    image_file = request.files.get('image')
    link_url = request.form.get('link', '')
    
    # Save image temporarily if provided
    image_path = None
    if image_file:
        image_path = f"/tmp/{image_file.filename}"
        image_file.save(image_path)
    
    # Run analysis
    try:
        result = analyze(
            user_text=user_text,
            image_path=image_path,
            link_url=link_url
        )
    finally:
        # Clean up temp file
        if image_path and os.path.exists(image_path):
            os.remove(image_path)
    
    # Return structured response
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=False)
```

---

## Tuning Parameters

All weights and thresholds are in the modular components:

- **Vision weights**: `app/vision.py` → `VISION_KEYWORDS`
- **Link infrastructure**: `app/link_analysis.py` → WHOIS age thresholds, pattern rules
- **RAG patterns**: `data/scam_patterns/` and `data/legit_indicators/`
- **Scoring**: `app/engine.py` → `SCAM_WEIGHTS`, `LEGIT_WEIGHTS`

No hardcoding in pipeline.py — it just orchestrates.

---

## Performance Notes

- **First run**: ~5 seconds (RAG embedding model loads)
- **Subsequent runs**: ~2 seconds (index cached)
- **Link analysis**: +1-2 seconds per URL
- **Image analysis**: +2-3 seconds per image (via HuggingFace API)

For high-throughput dashboards, consider:
1. **Caching** RAG index (currently lazy-loaded once)
2. **Batch processing** multiple submissions
3. **Async** link downloads

---

## Testing

```bash
# Quick test
python app/pipeline.py

# Test with different inputs
python -c "
from app.pipeline import analyze
result = analyze(user_text='Send money now')
print(f'Risk: {result[\"risk_level\"]} ({result[\"risk_score\"]})')
"
```

---

## Troubleshooting

### "No input provided" error
→ Provide at least one of: `user_text`, `image_path`, `link_url`

### "Image file not found"
→ Check file path exists and is readable

### RAG index loads slowly
→ Normal on first run. Subsequent calls reuse cached index.

### Vision API timeout
→ Check internet connection and HuggingFace API availability

### Unexpected LOW risk despite suspicious text
→ Pipeline may be finding legitimate indicators in knowledge base. Check `matched_patterns` for breakdown.

