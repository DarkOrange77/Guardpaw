# GuardPaw Confidence Calculation Design

## Overview

**Confidence** measures how certain we are about the risk assessment, independent from the risk score itself.

It uses a **hybrid approach**:
1. **Risk score is PRIMARY** — if we detected scam patterns, confidence reflects that
2. **Weight agreement is SECONDARY** — shows if signals are aligned or conflicting

---

## Formula

```
if risk_score >= 5:
    confidence = "High"           # Definitely HIGH risk
elif risk_score >= 2:
    if weight_ratio > 0.7:
        confidence = "High"       # Strong agreement on MEDIUM risk
    elif weight_ratio > 0.5:
        confidence = "Moderate"   # Some conflicting signals
    else:
        confidence = "Low"        # Significant conflicts
else:
    if weight_ratio >= 0.5:
        confidence = "Moderate"   # Some signal weight exists
    else:
        confidence = "Low"        # Unclear/conflicting
```

Where:
```
weight_ratio = max(scam_weight, legit_weight) / (scam_weight + legit_weight)
```

---

## Why This Design?

### Problem We Solved

Original simple approach: confidence = count of scam patterns / total patterns.

This broke when obvious scams matched some legitimate patterns in RAG:
- **Text:** "Send $500 or puppy dies via gift card"
- **RAG matched:** artificial_urgency_deadlines (scam), untraceable_payments (scam), physical_verification (legit), pricing_and_transparency (legit)
- **Old result:** 2 scam, 2 legit → 50/50 → "LOW confidence"
- **User confusion:** "But this IS obviously a scam!"

### Solution

The **risk_score already encodes all signal strength**. If it's ≥ 2, we detected real scam patterns. Weight conflicts exist because RAG has some semantic overlap (generic money/pricing talk), not because the assessment is wrong.

So confidence should be:
- **PRIMARY:** "Did we find enough scam weight? risk_score ≥ 2 → HIGH confidence in MEDIUM risk."
- **SECONDARY:** "Do signals agree? weight_ratio shows if they're aligned."

Result:
- **Text example:** risk_score=2 (clear), weight_ratio=0.545 (slight conflict) → MODERATE confidence
  - User sees: "⚠️ MEDIUM RISK — Moderate confidence (some conflicting signals detected)"
  - Dashboard can explain: "Found strong scam indicators (artificial urgency + payment requests) but also matched some legitimate topics (pricing). Likely a scam."

---

## Validation

| Test Case | Risk | Score | Confidence | Meaning |
|-----------|------|-------|------------|---------|
| Obvious scam text | MEDIUM | 2 | Moderate | Clear scam detected, but slight RAG overlap noise |
| Legit rescue URL | LOW | -4 | Moderate | Many legit patterns found, minimal scam signals |
| Empty input | LOW | 0 | Low | No evidence |

---

## RAG Quality & Pattern Filtering

### The Problem

RAG embeddings can match patterns with low semantic relevance:
- Scam text: "Send $500 or puppy dies via gift card"
- Matches: `pricing_and_transparency.md` (mentions "pricing", "fees") even though context is completely different

This creates false signal conflicts and lowers confidence unnecessarily.

### Our Solution: Two-Layer Filtering

1. **Pattern Weight Filtering** (during deduplication):
   - Keep ALL scam patterns regardless of weight
   - Keep legit patterns ONLY if weight ≤ -2 (strong indicators)
   - Exclude weak legit patterns (weight -1) as likely false positives
   - Exclude Case Studies (they're examples, not evidence)

2. **Hybrid Confidence Calculation**:
   - Risk score is PRIMARY
   - Weight agreement is SECONDARY
   - Result: High-confidence MEDIUM risk if strong scam signals present

### Result

| Before | After |
|--------|-------|
| 2 scam + 2 weak legit → MODERATE confidence | 2 scam + 1 strong legit → HIGH confidence |

Weak false positives are filtered before they affect confidence, while strong legitimate patterns (weight ≤ -2) are kept because they represent genuine legitimate signals.

---

## For Dashboard Developers

Confidence + Risk Level together tell the full story:

```
Risk: HIGH, Confidence: HIGH
→ "Definitely a scam. Strong, aligned signals."

Risk: MEDIUM, Confidence: Moderate
→ "Likely a scam, but some conflicting signals. Verify independently."

Risk: LOW, Confidence: Moderate
→ "Appears legitimate, but not completely certain. Check official sources."

Risk: LOW, Confidence: High
→ "Appears legitimate. Multiple indicators of authenticity."
```

Users should trust HIGH confidence more than MODERATE.

