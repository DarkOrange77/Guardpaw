# GuardPaw Dashboard Integration Guide

## Overview

Your GuardPaw system is now fully integrated with a beautiful, detailed dashboard that provides users with comprehensive explanations for every scam assessment.

The dashboard features:
- **Real-time analysis** via Flask API backend
- **Detailed explanations** with 5-section breakdown
- **Visual indicators** for scam/legitimacy patterns
- **Risk assessment** with confidence scoring
- **Beautiful UI** with glass-morphism design

---

## Architecture

```
Frontend (Dashboard.html)
    ↓ POST /analyze
    ↓ (text, link, image)
    ↓
Flask API (app/api.py)
    ↓
GuardPaw Pipeline (app/pipeline.py)
    ↓
    ├─ Text RAG (engine.py)
    ├─ Link Analysis (link_analysis.py)
    └─ Image Vision (vision.py)
    ↓
Result JSON
    ↓
Dashboard Display
    ├─ Risk Level (HIGH/MEDIUM/LOW)
    ├─ Risk Score
    ├─ Confidence %
    ├─ Scam Indicators
    ├─ Legitimacy Indicators
    └─ Detailed Explanation
```

---

## How It Works

### 1. User Submits Content

The dashboard accepts:
- **Text**: Pasted rescue descriptions
- **Link**: URLs to analyze
- **Image**: Screenshots/pasted images

### 2. Backend Processing

When user clicks "Analyze":
```javascript
analyzeContent() sends to http://localhost:5000/analyze
    ↓
Flask receives JSON:
{
    "user_text": "...",
    "link_url": "...",
    "image_path": "..."
}
```

### 3. Pipeline Analysis

The Flask API calls `GuardPawPipeline.analyze_submission()`:
```python
result = pipeline.analyze_submission(
    user_text="URGENT: Send $500 via gift card...",
    link_url="https://...",
    image_path="/path/to/image.jpg"
)
```

Returns:
```json
{
    "risk_level": "MEDIUM",
    "risk_score": 2.0,
    "confidence": "Moderate",
    "matched_patterns": [
        {
            "pattern": "artificial_urgency_deadlines",
            "type": "scam",
            "source": "text",
            "weight": 2
        }
    ],
    "explanation": "📋 ANALYSIS: ...\n⚠️ VERDICT: ...\n🚩 PATTERNS: ...",
    "recommendation": "⚠️ Proceed with caution"
}
```

### 4. Dashboard Display

Results are displayed in three sections:

#### A. Risk Card (Center)
```
RISK ASSESSMENT
    HIGH RISK
    Confidence: 87%
    [=========>          ] 78/100
```

#### B. Indicator Panels
**Left Panel - Scam Indicators:**
- 🚩 Artificial Urgency Deadlines (from TEXT)
- 🚩 Untraceable Payments Requests (from TEXT)

**Right Panel - Legitimacy Indicators:**
- ✓ Physical Verification (from TEXT)
- ✓ Pricing And Transparency (from TEXT)

#### C. Explanation Sections

**Why This Was Flagged:**
- Found 2 scam indicator(s) suggesting potential fraud
- Also found 2 legitimate indicator(s)
- Some conflicting signals, but scam indicators are stronger

---

## Setup & Launch

### Option 1: Automated Launcher (Recommended)

```bash
cd c:\Users\bezz3\OneDrive\Ser VS CODE\GuardPaw
python run_guardpaw.py
```

This will:
- ✅ Check Python environment
- ✅ Install Flask dependencies if needed
- ✅ Start Flask API on http://localhost:5000
- ✅ Auto-open Dashboard in your browser
- ✅ Show helpful instructions

### Option 2: Manual Setup

**Terminal 1 - Start Flask API:**
```bash
cd c:\Users\bezz3\OneDrive\Ser VS CODE\GuardPaw
python app/api.py
```

Output:
```
============================================================
GuardPaw API Starting...
============================================================
Dashboard: http://localhost:5000/
API: http://localhost:5000/analyze
Health: http://localhost:5000/health
============================================================
```

**Terminal 2 - Open Dashboard:**
```bash
# Windows
start "file:///C:/Users/bezz3/OneDrive/Ser VS CODE/GuardPaw/Frontend/Dashboard.html"

# macOS
open "file:///Users/bezz3/OneDrive/Ser VS CODE/GuardPaw/Frontend/Dashboard.html"

# Linux
xdg-open "file:///home/user/GuardPaw/Frontend/Dashboard.html"
```

---

## API Endpoints

### POST /analyze
Analyze submission for scams

**Request:**
```json
{
    "user_text": "Send $500 via gift card or puppy dies!",
    "link_url": "https://example.com",
    "image_path": "/path/to/image.jpg"
}
```

**Response:**
```json
{
    "risk_level": "MEDIUM",
    "risk_score": 2.0,
    "confidence": "Moderate",
    "matched_patterns": [...],
    "explanation": "📋 ANALYSIS: ...",
    "recommendation": "⚠️ Proceed with caution",
    "signals": {...},
    "input_summary": "Analyzed text description"
}
```

### GET /health
Health check

**Response:**
```json
{
    "status": "ok",
    "service": "GuardPaw API"
}
```

### GET /info
API information

**Response:**
```json
{
    "name": "GuardPaw Scam Detection API",
    "version": "1.0.0",
    "description": "Multimodal animal rescue scam detector",
    "endpoints": {
        "/analyze": "POST - Analyze submission",
        "/health": "GET - Health check",
        "/info": "GET - API info"
    }
}
```

---

## Dashboard Features

### 1. Input Tabs
- **Paste Tab**: Copy-paste text descriptions
- **Link Tab**: Enter URL to analyze
- **Upload Tab**: Upload images or documents

### 2. Real-time Processing
- Loading state feedback
- Progress indicators
- Error handling with fallback to demo data

### 3. Result Display
- Risk level with color coding (RED/ORANGE/BLUE)
- Confidence percentage
- Risk gauge visualization
- Detailed pattern matching
- Evidence-based explanations

### 4. Visual Design
- Glass-morphism UI with frosted glass effect
- Night sky gradient background
- Animated fireflies and snowflakes
- Smooth transitions and hover effects
- Responsive layout for all screen sizes

---

## Result Explanation Format

The `explanation` field contains 5 sections:

```
📋 ANALYSIS
We examined [what was analyzed: text/image/link]

⚠️ VERDICT
[RISK_LEVEL] — [plain language description]
[Confidence statement]

🚩 SCAM INDICATORS FOUND ([count])
   • Pattern name 1 (from SOURCE)
   • Pattern name 2 (from SOURCE)

✓ LEGITIMATE INDICATORS ([count])
   • Pattern name 1 (from SOURCE)
   • Pattern name 2 (from SOURCE)

📊 WHY
   • [Evidence point 1]
   • [Evidence point 2]
   • [Evidence point 3]

💡 RECOMMENDATION
   ⚠️ [Action 1]
   🔍 [Action 2]
   📞 [Action 3]
   💰 [Action 4]
```

---

## Example Usage

### Test Case 1: Obvious Scam Text

**Input:**
```
URGENT: Send $500 via Amazon gift card NOW or 
the rescue operation will fail and the puppies 
will have to be put down! We need the money ASAP!
```

**Output:**
```
Risk Level: MEDIUM
Confidence: 70%
Risk Score: 2.0

Scam Indicators Found (2):
  🚩 Artificial Urgency Deadlines (from TEXT)
  🚩 Untraceable Payments Requests (from TEXT)

Legitimacy Indicators Found (0):
  (none detected)

Why This Was Flagged:
  • Found 2 scam indicator(s) suggesting potential fraud
  • Language patterns indicate manipulation tactics
  • Payment method strongly suggests untraceable transfer

Recommendation:
  ⚠️ Proceed with caution - likely fraudulent
  🔍 Verify the rescue organization independently
  📞 Call the official organization directly
  💰 Use secure payment methods
```

### Test Case 2: Legitimate Organization

**Input:**
```
https://bestfriends.org/how-you-can-help
```

**Output:**
```
Risk Level: LOW
Confidence: 91%
Risk Score: -4.0

Scam Indicators Found (1):
  🚩 No Verifiable Rescue Identity (minor signal)

Legitimacy Indicators Found (4):
  ✓ Physical Verification
  ✓ Community Validation
  ✓ Pricing And Transparency
  ✓ Education And Awareness

Why This Was Flagged:
  • Found 4 legitimate indicator(s)
  • Organization has strong credibility signals
  • Multiple verification sources confirm legitimacy

Recommendation:
  ✅ Appears legitimate
  🔍 Verify independently if needed
  💰 Use their official payment portal
```

---

## Customization

### Change Risk Colors
Edit [Dashboard.html](Dashboard.html#L20-L25):
```css
--risk-high: #e8724d;    /* Red for HIGH RISK */
--risk-medium: #e8a54d;  /* Orange for MEDIUM RISK */
--risk-low: #4d9ee8;     /* Blue for LOW RISK */
```

### Change API Endpoint
Edit [Dashboard.html](Dashboard.html#L935):
```javascript
const response = await fetch('http://YOUR-API-URL:5000/analyze', {
```

### Modify Explanation Display
Edit [Dashboard.html](Dashboard.html#L1020) `updateExplanationDisplay()` function to parse different explanation formats.

---

## Troubleshooting

### Dashboard loads but "Analyze" button doesn't work
- **Issue**: Flask API not running
- **Fix**: Start API with `python app/api.py`
- **Check**: http://localhost:5000/health should return `{"status": "ok"}`

### "Error analyzing content" message
- **Issue**: Backend error during analysis
- **Fix**: Check Flask terminal for error messages
- **Debug**: Look for exception details in Flask output

### No indicators showing in results
- **Issue**: Pipeline not returning patterns
- **Fix**: Ensure RAG index is loaded (check for "Loading existing index..." message)
- **Verify**: Run `python app/pipeline.py` to test pipeline directly

### Slow analysis (>30 seconds)
- **Issue**: Vision API timeout
- **Fix**: Provide text instead of images, or increase timeout
- **Note**: First run loads embedding model (slow), subsequent runs are faster

---

## Performance Notes

- **Text-only analysis**: ~2 seconds
- **Link analysis**: ~3-5 seconds (includes page download + text extraction)
- **Image analysis**: ~5-10 seconds (HuggingFace API call)
- **Combined analysis**: ~8-15 seconds

First API call loads embedding model (~100MB), subsequent calls use cached model.

---

## Next Steps

1. **Test the system** using the example test cases above
2. **Deploy API** to production server (Heroku, AWS, etc.)
3. **Host dashboard** on web server (Netlify, GitHub Pages, etc.)
4. **Add authentication** if needed (user accounts, rate limiting)
5. **Monitor performance** with logging/metrics
6. **Gather user feedback** to improve patterns

---

## Support Files

| File | Purpose |
|------|---------|
| [Dashboard.html](Frontend/Dashboard.html) | Frontend UI + JavaScript logic |
| [app/api.py](app/api.py) | Flask API backend |
| [app/pipeline.py](app/pipeline.py) | Analysis orchestrator |
| [run_guardpaw.py](run_guardpaw.py) | Automated launcher |
| [requirements.txt](requirements.txt) | Python dependencies |

---

## Questions?

Refer to these documentation files:
- [SYSTEM_SUMMARY.md](SYSTEM_SUMMARY.md) - Complete architecture
- [PIPELINE_USAGE.md](PIPELINE_USAGE.md) - Pipeline integration examples
- [CONFIDENCE_DESIGN.md](CONFIDENCE_DESIGN.md) - Scoring methodology
