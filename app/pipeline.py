#!/usr/bin/env python3
"""
GuardPaw Unified Pipeline

Main orchestrator for analyzing user submissions (text, image, link).
Handles all 7 input combinations deterministically.

This is the PRIMARY entry point for dashboard integration.

Usage:
    from app.pipeline import GuardPawPipeline
    
    pipeline = GuardPawPipeline()
    result = pipeline.analyze_submission(
        user_text="suspicious text",
        image_path="/path/to/image.jpg",
        link_url="https://example.com"
    )
    
    print(result['risk_level'])  # HIGH|MEDIUM|LOW
    print(result['risk_score'])  # numeric score
    print(result['confidence'])  # High|Moderate|Low
"""

import os
import sys
from typing import Dict, List, Optional, Any

# Setup path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.link_analysis import analyze_link, process_link_output
from app.vision import GuardPawVision
from app.engine import GuardPawEngine
from rag.vector_store.search_index import build_or_load_index


class GuardPawPipeline:
    """
    Unified analysis pipeline for GuardPaw.
    
    Accepts any combination of inputs:
    - user_text: human-provided description
    - image_path: local file path to image
    - link_url: URL to analyze
    
    Returns structured risk assessment with patterns, signals, and explanation.
    """
    
    def __init__(self):
        """Initialize pipeline components."""
        self.vision = GuardPawVision()
        self.engine = GuardPawEngine()
        self.index = None
        
        # Expose weight dictionaries for confidence calculation
        self.scam_weights_map = self.engine.SCAM_WEIGHTS
        self.legit_weights_map = self.engine.LEGIT_WEIGHTS
        
    def _load_index(self):
        """Lazy-load RAG index."""
        if self.index is None:
            self.index = build_or_load_index()
        return self.index
    
    def _is_domain_legitimate(self, link_out: Dict) -> bool:
        """
        Determine if a link's domain infrastructure appears legitimate.
        
        Returns True if domain has good signals (older domain, legit signals, identity info).
        Returns False if domain has suspicious signals (recent, shortener, etc).
        """
        if not link_out:
            return False
        
        signals = link_out.get("signals", [])
        
        # Negative signals (red flags)
        red_flags = [
            "domain_recent_30",
            "domain_recent_90", 
            "shortener_detected",
            "redirect_chain_detected",
            "private_contact_redirection",
            "untraceable_payment",
            "impersonation_claim"
        ]
        
        has_red_flags = any(flag in signals for flag in red_flags)
        
        # Positive signals (good signs)
        description = link_out.get("description", "").lower()
        has_identity = any(keyword in description for keyword in 
                          ["address", "registered", "tax", "charity", "registration", "shelter", "rescue"])
        
        # If domain has identity keywords and NO red flags, it's likely legitimate
        if has_identity and not has_red_flags:
            return True
        
        # If no red flags at all, lean legitimate
        if not has_red_flags:
            return True
        
        return False
    
    def _load_index(self):
        """Lazy-load RAG index."""
        if self.index is None:
            self.index = build_or_load_index()
        return self.index
    
    def analyze_submission(
        self,
        user_text: str = "",
        image_path: Optional[str] = None,
        link_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze a submission combining any mix of text, image, and link.
        
        Args:
            user_text: Human-provided description (optional)
            image_path: Path to local image file (optional)
            link_url: URL to analyze (optional)
        
        Returns:
            {
                "risk_level": "HIGH|MEDIUM|LOW",
                "risk_score": float,
                "confidence": "High|Moderate|Low",
                "matched_patterns": [
                    {
                        "name": "pattern_file.md",
                        "category": "Scam Pattern|Legit Indicator",
                        "weight": float,
                        "source": "text|image|link"
                    }
                ],
                "signals": {
                    "text": {...},
                    "image": {...},
                    "link": {...}
                },
                "explanation": "Full text explanation of assessment",
                "recommendation": "Action-oriented recommendation"
            }
        """
        
        # ==========================================
        # INPUT VALIDATION
        # ==========================================
        if not user_text and not image_path and not link_url:
            return self._empty_result("No input provided")
        
        # Validate file paths
        if image_path and not os.path.exists(image_path):
            return self._empty_result(f"Image file not found: {image_path}")
        
        # ==========================================
        # INITIALIZE TRACKING
        # ==========================================
        merged_query = ""
        all_patterns = []
        risk_score = 0.0
        
        signals = {
            "text": None,
            "image": None,
            "link": None
        }
        
        # ==========================================
        # STEP 1: TEXT ANALYSIS
        # ==========================================
        text_patterns = []
        rag_query = ""  # Track query for RAG (only user-provided text and link content)
        
        if user_text and user_text.strip():
            merged_query = user_text
            rag_query = user_text  # RAG should match against user's actual text
            signals["text"] = {
                "input": user_text[:100],
                "status": "analyzed"
            }
        
        # ==========================================
        # STEP 2: IMAGE ANALYSIS (User-Uploaded)
        # ==========================================
        image_signals = []
        if image_path:
            try:
                vout = self.vision.analyze_image(image_path)
                image_desc, image_signals = self.vision.process_vision_output(vout)
                
                # Merge vision description into merged_query for signal combination
                # BUT do NOT add to rag_query (vision-synthesized text shouldn't trigger RAG patterns)
                merged_query = self.vision.merge_with_user_text(
                    merged_query, 
                    page_text=None, 
                    vision_description=image_desc
                )
                
                signals["image"] = {
                    "description": image_desc[:100] if image_desc else None,
                    "signals": len(image_signals),
                    "status": "analyzed"
                }
            except Exception as e:
                signals["image"] = {
                    "error": str(e),
                    "status": "failed"
                }
        
        # ==========================================
        # STEP 3: LINK ANALYSIS
        # ==========================================
        link_patterns = []
        link_image_signals = []
        page_text_blob = None
        selected_images = []
        link_out = {}  # Track link output for domain legitimacy check
        
        if link_url:
            try:
                link_out = analyze_link(link_url)
                
                # Extract infrastructure signals
                link_text, link_patterns = process_link_output(link_out)
                
                # Extract page content
                page_data = link_out.get("page", {})
                selected_images = link_out.get("selected_images", [])
                
                if page_data and isinstance(page_data, dict):
                    parts = []
                    if page_data.get('title'):
                        parts.append(page_data.get('title'))
                    if page_data.get('description'):
                        parts.append(page_data.get('description'))
                    if page_data.get('payment_instructions'):
                        parts.append("PAYMENT:\n" + page_data.get('payment_instructions'))
                    page_text_blob = "\n".join(parts)
                
                # Merge page text into BOTH merged_query AND rag_query (link page content is real, not auto-generated)
                merged_query = self.vision.merge_with_user_text(
                    merged_query,
                    page_text=page_text_blob,
                    vision_description=None
                )
                rag_query = self.vision.merge_with_user_text(
                    rag_query,
                    page_text=page_text_blob,
                    vision_description=None
                )
                
                signals["link"] = {
                    "url": link_url,
                    "infrastructure_signals": len(link_out.get("signals", [])),
                    "page_title": page_data.get('title', '')[:80] if page_data else None,
                    "images_found": len(selected_images),
                    "status": "analyzed"
                }
                
                # Vision analysis on link-selected images (0.6x multiplier)
                # But do NOT add their descriptions to rag_query (auto-generated descriptions shouldn't trigger RAG)
                for img_url in selected_images:
                    try:
                        vout = self.vision.analyze_image(img_url)
                        _, sigs = self.vision.process_vision_output(vout)
                        if sigs:
                            link_image_signals.extend(sigs)
                    except Exception:
                        continue
                
            except Exception as e:
                signals["link"] = {
                    "error": str(e),
                    "status": "failed"
                }
        
        # ==========================================
        # STEP 4: RAG SEMANTIC SEARCH
        # ==========================================
        # IMPORTANT: Use rag_query (which only contains user-provided text and link page content)
        # NOT merged_query (which includes auto-generated vision descriptions)
        # This prevents false positives from synthesized image descriptions
        rag_items = []
        if rag_query and rag_query.strip():
            try:
                index = self._load_index()
                # Just use top-5 matches without threshold filtering
                # (normalized embeddings have lower similarity scores; thresholding removes all matches)
                docs = index.similarity_search(rag_query, k=5)
                
                if docs:
                    report = self.engine.generate_report(docs)
                    rag_items = report.get("items", [])
                    risk_score = report.get("summary", {}).get("risk_score", 0)
            except Exception as e:
                # Graceful fallback if RAG fails
                pass
        
        # ==========================================
        # STEP 5: COMBINE ALL SIGNALS
        # ==========================================
        matched_patterns = []
        matched_pattern_names = []
        
        # Determine if link domain is legitimate for downweighting RAG false positives
        domain_is_legitimate = link_url and self._is_domain_legitimate(link_out if link_url else {})
        
        # If domain is legitimate, reduce risk_score to prevent false positives from innocent text
        if domain_is_legitimate and link_url and risk_score > 0:
            # Reduce risk score by 70% when scam patterns found in legitimate domain's text
            # (innocent phrases like "adopt now", "urgent", "donation" trigger false positives)
            risk_score = risk_score * 0.3
        
        # Build initial pattern list from RAG results with proper weights
        for item in rag_items:
            pattern_name = item.get("source", "")
            # Look up weight from engine's weight maps
            weight = self.scam_weights_map.get(pattern_name, 0) or self.legit_weights_map.get(pattern_name, 0)
            
            # DOWNWEIGHT scam patterns if they come from link text and domain is legitimate
            # This prevents false positives from innocent phrases like "adopt now", "urgent help"
            if domain_is_legitimate and link_url and "scam" in item.get("category", "").lower():
                # Reduce scam pattern weight by 80% when found in legitimate domain's text
                weight = max(0, int(weight * 0.2))
            
            matched_patterns.append({
                "name": pattern_name,
                "category": item.get("category"),
                "weight": weight,
                "source": "text"
            })
            matched_pattern_names.append(pattern_name)
        
        # Apply link infrastructure patterns (1.0x)
        if link_patterns:
            risk_score, matched_pattern_names = self.vision.apply_vision_signals_to_score(
                risk_score, link_patterns, 
                matched_pattern_names,
                multiplier=1.0
            )
            # Add link patterns to list
            for lp in link_patterns:
                pattern_name = lp.get("pattern", "")
                weight = lp.get("weight", 0)
                matched_patterns.append({
                    "name": pattern_name,
                    "category": "Scam Pattern" if "scam" in pattern_name.lower() else "Unknown",
                    "weight": weight,
                    "source": "link"
                })
        
        # ADD POSITIVE SIGNALS for legitimate domains
        # If domain infrastructure shows legitimacy, add strong legit indicators
        if domain_is_legitimate and link_url:
            # Add strong legitimacy signals for established domains
            legit_signal = {
                "pattern": "community_validation.md",
                "weight": -3,  # Strong negative (legitimacy indicator)
                "source": "link"
            }
            # Check if not already in patterns
            if not any(p["name"] == "community_validation.md" for p in matched_patterns):
                matched_patterns.append({
                    "name": "community_validation.md",
                    "category": "Legit Indicator",
                    "weight": -3,
                    "source": "link"
                })
                # Apply to risk score
                risk_score -= 3
            
            # REMOVE contradictory patterns when domain is legitimate
            # If we determined domain has good infrastructure, remove "no_verifiable_identity" flags
            # which are just keyword-matching artifacts
            matched_patterns = [p for p in matched_patterns 
                               if "no_verifiable_rescue_identity" not in p["name"]]
        
        # Apply user-uploaded image signals (1.0x)
        if image_signals:
            risk_score, matched_pattern_names = self.vision.apply_vision_signals_to_score(
                risk_score, image_signals,
                matched_pattern_names,
                multiplier=1.0
            )
            for img_sig in image_signals:
                pattern_name = img_sig.get("pattern", "")
                weight = img_sig.get("weight", 0)
                matched_patterns.append({
                    "name": pattern_name,
                    "category": "Scam Pattern" if "scam" in pattern_name.lower() else "Unknown",
                    "weight": weight,
                    "source": "image"
                })
        
        # Apply link-sourced image signals (0.6x)
        if link_image_signals:
            risk_score, matched_pattern_names = self.vision.apply_vision_signals_to_score(
                risk_score, link_image_signals,
                matched_pattern_names,
                multiplier=0.6
            )
            for link_img_sig in link_image_signals:
                pattern_name = link_img_sig.get("pattern", "")
                weight = link_img_sig.get("weight", 0) * 0.6  # Apply multiplier
                matched_patterns.append({
                    "name": pattern_name,
                    "category": "Scam Pattern" if "scam" in pattern_name.lower() else "Unknown",
                    "weight": weight,
                    "source": "link_image"
                })
        
        # Deduplicate patterns (keep highest weight per pattern)
        deduplicated = {}
        for p in matched_patterns:
            key = p["name"]
            if key not in deduplicated or p["weight"] > deduplicated[key]["weight"]:
                deduplicated[key] = p
        
        final_patterns = list(deduplicated.values())
        
        # ==========================================
        # FILTER: Remove weak/contradictory patterns
        # ==========================================
        # If risk_score is clearly HIGH/MEDIUM (strong scam signals),
        # filter out legit patterns that have very low weight (likely false positives)
        # Also exclude Case Studies from confidence calculation (they're examples, not signals)
        if risk_score >= 2:
            filtered = []
            for p in final_patterns:
                category = p.get("category", "").lower()
                weight = p.get("weight", 0)
                
                # Exclude case studies — they're examples, not evidence
                if "case" in category:
                    continue
                
                # Keep all scam patterns
                if "scam" in category:
                    filtered.append(p)
                # For legit patterns: only keep if weight is strong (-2 or lower)
                # or if it came from user image/link (high confidence sources)
                elif "legit" in category:
                    if weight <= -2 or p.get("source") in ("image", "link"):
                        filtered.append(p)
                else:
                    # Unknown category — keep it
                    filtered.append(p)
            
            final_patterns = filtered
        
        # ==========================================
        # STEP 6: CALCULATE RISK LEVEL & CONFIDENCE
        # ==========================================
        risk_level = self._calculate_risk_level(risk_score)
        confidence = self._calculate_confidence(final_patterns, risk_score)
        
        # ==========================================
        # STEP 7: GENERATE EXPLANATION & RECOMMENDATION
        # ==========================================
        # STEP 7: GENERATE EXPLANATION & RECOMMENDATION
        # ==========================================
        explanation = self._generate_explanation(
            risk_score, risk_level, confidence, final_patterns, signals, 
            {
                "has_text": bool(user_text and user_text.strip()),
                "has_image": bool(image_path),
                "has_link": bool(link_url),
                "text_sample": user_text[:200] if user_text else None,
                "link_info": link_out if link_url else None,
                "scam_patterns": [p for p in final_patterns if "scam" in p.get("category", "").lower()],
                "legit_patterns": [p for p in final_patterns if "legit" in p.get("category", "").lower()],
            }
        )
        
        recommendation = self._generate_recommendation(risk_level, final_patterns)
        
        # ==========================================
        # RETURN STRUCTURED RESULT
        # ==========================================
        return {
            "risk_level": risk_level,
            "risk_score": round(risk_score, 1),
            "confidence": confidence,
            "matched_patterns": final_patterns,
            "signals": signals,
            "explanation": explanation,
            "recommendation": recommendation,
            "input_summary": {
                "has_text": bool(user_text and user_text.strip()),
                "has_image": bool(image_path),
                "has_link": bool(link_url)
            }
        }
    
    def _calculate_risk_level(self, risk_score: float) -> str:
        """Map numeric score to risk level."""
        if risk_score >= 5:
            return "HIGH"
        elif risk_score >= 2:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _calculate_confidence(self, patterns: List[Dict], risk_score: float) -> str:
        """
        Calculate confidence using hybrid approach: risk_score (primary) + weight agreement (secondary).
        
        Confidence measures how certain we are about the risk assessment:
        - HIGH (≥0.75): Strong signals, clear assessment
        - MEDIUM (0.5-0.75): Some conflicting signals but assessment is still valid
        - LOW (<0.5): Conflicting signals or insufficient evidence
        
        Approach:
        1. Risk score is PRIMARY — if score >= 2, we detected real scam patterns
        2. Weight ratio is SECONDARY — shows signal agreement
        
        Formula:
        - If risk_score >= 5: HIGH (definitely high risk)
        - If risk_score >= 2: Check weight agreement
          * ratio > 0.7 → HIGH (strong agreement on medium risk)
          * ratio 0.5-0.7 → MEDIUM (some conflicting signals)
          * ratio <= 0.5 → LOW (conflicting signals)
        - If risk_score < 2: Check weight agreement
          * ratio >= 0.5 → MEDIUM (some signal weight exists)
          * ratio < 0.5 → LOW (unclear/conflicting)
        """
        if not patterns:
            return "Low"
        
        # Calculate total scam and legit weights
        scam_weight = sum(
            abs(p.get("weight", 0)) 
            for p in patterns 
            if "scam" in p.get("category", "").lower()
        )
        legit_weight = sum(
            abs(p.get("weight", 0)) 
            for p in patterns 
            if "legit" in p.get("category", "").lower()
        )
        
        total_weight = scam_weight + legit_weight
        
        # Avoid division by zero
        if total_weight == 0:
            return "Low"
        
        # Calculate weight agreement ratio
        max_weight = max(scam_weight, legit_weight)
        weight_ratio = max_weight / total_weight
        
        # Apply hybrid logic: risk_score primary, weight_ratio secondary
        if risk_score >= 5:
            # Definitely HIGH risk → HIGH confidence
            return "High"
        elif risk_score >= 2:
            # MEDIUM risk (clearly detected scam patterns)
            # Check weight agreement for secondary confirmation
            if weight_ratio > 0.7:
                return "High"  # Strong agreement on medium risk
            elif weight_ratio > 0.5:
                return "Moderate"  # Some conflicting signals
            else:
                return "Low"  # Significant conflicting signals
        else:
            # LOW risk → check if we have ANY signal agreement
            if weight_ratio >= 0.5:
                return "Moderate"  # Some signal weight exists, unclear
            else:
                return "Low"  # Conflicting or insufficient evidence
    
    def _generate_explanation(
        self, 
        risk_score: float, 
        risk_level: str,
        confidence: str,
        patterns: List[Dict],
        signals: Dict,
        input_summary: Dict
    ) -> str:
        """Generate detailed, evidence-based explanation that cites specific findings.
        
        Structure mimics professional detective reports with:
        - What was analyzed
        - Verdict with confidence
        - Specific findings with quotes/evidence
        - Pattern analysis
        - Why this assessment
        - Actionable recommendations
        """
        lines = []
        
        has_text = input_summary.get("has_text")
        has_image = input_summary.get("has_image")
        has_link = input_summary.get("has_link")
        text_sample = input_summary.get("text_sample")
        link_info = input_summary.get("link_info")
        scam_patterns = input_summary.get("scam_patterns", [])
        legit_patterns = input_summary.get("legit_patterns", [])
        
        # ==========================================
        # SECTION 1: WHAT WAS ANALYZED
        # ==========================================
        lines.append("**ANALYSIS SUMMARY**")
        analysis_parts = []
        if has_text:
            analysis_parts.append("text submission")
        if has_image:
            analysis_parts.append("image analysis")
        if has_link:
            analysis_parts.append("website analysis")
        
        if analysis_parts:
            lines.append(f"We performed {', '.join(analysis_parts)} to assess this submission.")
        lines.append("")
        
        # ==========================================
        # SECTION 2: VERDICT
        # ==========================================
        confidence_strength = {
            "High": "strongly",
            "Moderate": "",
            "Low": "with limited confidence"
        }
        strength = confidence_strength.get(confidence, "")
        
        if risk_level == "HIGH":
            verdict_text = "**🚨 HIGH RISK** - Multiple strong indicators of fraudulent activity"
            if strength:
                verdict_text += f" ({strength})"
        elif risk_level == "MEDIUM":
            verdict_text = "**⚠️ MEDIUM RISK** - Suspicious elements detected"
            if strength:
                verdict_text += f" ({strength})"
        else:
            verdict_text = "**✓ LOW RISK** - Appears legitimate"
            if strength:
                verdict_text += f" ({strength})"
        
        lines.append(verdict_text)
        lines.append("")
        
        # ==========================================
        # SECTION 3: KEY CONCERNS (Top scam patterns)
        # ==========================================
        if scam_patterns:
            lines.append("**Red Flags Detected:**")
            lines.append("")
            
            for idx, p in enumerate(scam_patterns[:5], 1):  # Top 5
                pattern_name = p.get("name", "").replace(".md", "").replace("_", " ")
                source = p.get("source", "unknown")
                weight = p.get("weight", 0)
                
                # Pattern-specific context and explanations
                pattern_details = {
                    "artificial urgency deadlines": {
                        "description": "Uses artificial urgency or emotional pressure",
                        "context": "Common scam tactic: claiming the animal will die without immediate donation",
                        "risk": "Pressure override users' normal decision-making"
                    },
                    "private contact redirection": {
                        "description": "Directs communication to private messaging (WhatsApp, Telegram, etc.)",
                        "context": "Legitimate rescues use public contact methods for transparency and accountability",
                        "risk": "Avoids leaving verifiable communication trail; enables isolation of victims"
                    },
                    "untraceable payments requests": {
                        "description": "Requests payment through hard-to-trace methods",
                        "context": "Instead of established charity payment systems or verifiable bank transfers",
                        "risk": "Makes it impossible to recover money or trace the fraud"
                    },
                    "psychological manipulation": {
                        "description": "Uses emotional manipulation to cloud judgment",
                        "context": "Excessive emotional appeals combined with demand for quick action",
                        "risk": "Overcomes rational decision-making; typically targets compassionate people"
                    },
                    "digital footprint anomalies": {
                        "description": "Suspicious digital presence patterns",
                        "context": "Very new domain, no organizational history, or inconsistent online presence",
                        "risk": "Indicates newly-created fraudulent operation"
                    },
                    "no verifiable rescue identity": {
                        "description": "Cannot verify the organization's legitimate identity",
                        "context": "No verifiable address, phone number, tax registration, or shelter affiliation",
                        "risk": "May be completely fabricated identity"
                    },
                    "impersonation of authority": {
                        "description": "Falsely claims authority or official status",
                        "context": "Claims to be government approved, official partner, or registered charity without proof",
                        "risk": "Uses authority impersonation to gain trust"
                    },
                    "stolen media indicators": {
                        "description": "Uses potentially stolen or stock photos",
                        "context": "Images match stock photo sites (Shutterstock, Getty, etc.) or show signs of theft",
                        "risk": "Fabricates emotional appeal with fake imagery"
                    },
                    "inconsistent animal details": {
                        "description": "Animal details are inconsistent or don't match",
                        "context": "Stories about the animal don't align with each other or with the images shown",
                        "risk": "Indicates fabricated narrative"
                    },
                    "staged rescue content": {
                        "description": "Rescue narrative appears artificially staged or produced",
                        "context": "Story elements don't align with reality; too-perfect emotional narrative",
                        "risk": "Indicates fake rescue scenario created purely for profit"
                    }
                }
                
                details = pattern_details.get(pattern_name.lower(), {
                    "description": f"Detected {pattern_name} pattern",
                    "context": "This pattern is commonly found in animal rescue scams",
                    "risk": "Indicates fraudulent activity"
                })
                
                lines.append(f"{idx}. **{pattern_name.title()}** (detected in {source})")
                lines.append(f"   • {details['description']}")
                lines.append(f"   • Context: {details['context']}")
                lines.append(f"   • Risk: {details['risk']}")
                lines.append("")
        
        # ==========================================
        # SECTION 4: WEBSITE INFRASTRUCTURE ANALYSIS
        # ==========================================
        if has_link and link_info:
            lines.append("**Website Infrastructure Analysis:**")
            
            description = link_info.get("description", "")
            link_signals = link_info.get("signals", [])
            page_data = link_info.get("page", {})
            
            findings = []
            
            # Domain age
            if "Domain age" in description:
                age_match = description.split("Domain age (days): ")
                if len(age_match) > 1:
                    days_str = age_match[1].split(";")[0]
                    if days_str.isdigit():
                        days = int(days_str)
                        if days < 30:
                            findings.append(f"• **Domain Age**: Only {days} days old (MAJOR RED FLAG - typical scam pattern)")
                        elif days < 90:
                            findings.append(f"• **Domain Age**: {days} days old (moderate concern)")
                        else:
                            years = days // 365
                            findings.append(f"• **Domain Age**: Established {years} year(s) ago (suggests legitimacy)")
            
            # Redirects
            if "redirect_chain_detected" in link_signals:
                findings.append("• **Redirect Chain**: Multiple redirects detected (suspicious for scam links)")
            
            # Shorteners
            if "shortener_detected" in link_signals:
                findings.append("• **URL Shortener**: Uses shortener service, masking actual destination")
            
            # Payment methods
            if "untraceable_payment" in link_signals:
                findings.append("• **Payment Method**: Uses untraceable payment service (e.g., PayPal Friends & Family, cryptocurrency)")
            
            # Private contact
            if "private_contact_redirection" in link_signals:
                findings.append("• **Contact Method**: Redirects to private messaging instead of public contact")
            
            # Verification
            if "no_verifiable_identity" in link_signals:
                findings.append("• **Verification**: No verifiable address, phone, or organizational identity found on site")
            
            # Impersonation
            if "impersonation_claim" in link_signals:
                findings.append("• **Authority Claims**: Makes authority claims without supporting evidence")
            
            # Page title
            if page_data and page_data.get("title"):
                title = page_data.get("title", "")[:80]
                findings.append(f"• **Page Title**: '{title}'")
            
            # Images
            if link_info.get("selected_images"):
                count = len(link_info.get("selected_images", []))
                findings.append(f"• **Images on Site**: {count} image(s) found")
            
            if findings:
                for finding in findings:
                    lines.append(finding)
                lines.append("")
        
        # ==========================================
        # SECTION 5: TEXT ANALYSIS (if text provided)
        # ==========================================
        if has_text and text_sample:
            lines.append("**Text Analysis:**")
            # Truncate for display
            sample = text_sample.strip()
            if len(sample) > 150:
                sample = sample[:150] + "..."
            lines.append(f"Analyzed text: \"{sample}\"")
            
            # Check for common scam phrases
            scam_phrases = [
                ("URGENT", "artificial urgency"),
                ("emergency", "artificial urgency"),
                ("now or", "temporal pressure"),
                ("don't have time", "artificial urgency"),
                ("help immediately", "artificial urgency"),
                ("PayPal", "payment method"),
                ("Western Union", "payment method"),
                ("bank transfer", "payment method"),
                ("private message", "contact avoidance"),
                ("WhatsApp", "private contact"),
            ]
            
            found_phrases = []
            text_lower = sample.lower()
            for phrase, category in scam_phrases:
                if phrase.lower() in text_lower:
                    found_phrases.append(f"'{phrase}' ({category})")
            
            if found_phrases:
                lines.append(f"Found suspicious phrases: {', '.join(found_phrases)}")
            lines.append("")
        
        # ==========================================
        # SECTION 6: LEGITIMATE INDICATORS (if any)
        # ==========================================
        if legit_patterns:
            lines.append("**Positive Indicators:**")
            for p in legit_patterns:
                pattern_name = p.get("name", "").replace(".md", "").replace("_", " ")
                sources_map = {
                    "text": "in submission",
                    "link": "on website",
                    "image": "in image",
                }
                source = sources_map.get(p.get("source", ""), "detected")
                lines.append(f"• {pattern_name.title()} ({source})")
            lines.append("")
        
        # ==========================================
        # SECTION 7: ASSESSMENT REASONING
        # ==========================================
        scam_count = len(scam_patterns)
        legit_count = len(legit_patterns)
        
        lines.append("**Why This Assessment:**")
        if risk_level == "HIGH":
            lines.append(f"We detected {scam_count} strong scam indicator(s) that together form a clear pattern of fraudulent activity. These patterns are consistently seen in confirmed animal rescue scams.")
        elif risk_level == "MEDIUM":
            lines.append(f"We found {scam_count} concerning pattern(s) and {legit_count} legitimate indicator(s). The concerning patterns outweigh the positives, warranting additional verification before any monetary commitment.")
        else:  # LOW
            if legit_count > 0:
                lines.append(f"The positive indicators ({legit_count}) outweigh any concerns. The organization shows signs of legitimacy.")
            else:
                lines.append("We did not find strong evidence of fraudulent activity. Risk profile is low.")
        lines.append("")
        
        # ==========================================
        # SECTION 8: RECOMMENDATIONS
        # ==========================================
        lines.append("**Recommended Actions:**")
        if risk_level == "HIGH":
            lines.append("• **DO NOT send money or personal information**")
            lines.append("• Report the link/email to the platform hosting it")
            lines.append("• Report to FTC (ftc.gov) and local animal control")
            lines.append("• Check local rescues with verifiable addresses and phone numbers instead")
        elif risk_level == "MEDIUM":
            lines.append("• **Before donating**: Verify independently")
            lines.append("• Call the organization directly using a number from their official website (not the provided link)")
            lines.append("• Check their physical address on Google Maps")
            lines.append("• Search for reviews on Charity Navigator, GuideStar, or BBB")
            lines.append("• Ask for proof: vet clinic letters, shelter registration, tax ID")
        else:  # LOW
            lines.append("• Appears legitimate, but always verify for peace of mind")
            lines.append("• Check their physical location and phone number independently")
            lines.append("• Ask for transparency about how funds are used")
            lines.append("• Reputable rescues will provide verifiable information")
        
        return "\n".join(lines)
    
    
    def _generate_recommendation(self, risk_level: str, patterns: List[Dict]) -> str:
        """Generate context-specific, actionable recommendations based on risk level."""
        if risk_level == "HIGH":
            return ("🚨 **DO NOT send money or personal information.** This submission shows clear signs of a scam. "
                   "Report to FTC (ftc.gov), your state attorney general, and the platform. "
                   "If you're looking to help animals, contact established rescues like ASPCA or local shelters with verifiable addresses.")
        elif risk_level == "MEDIUM":
            return ("⚠️ **VERIFY BEFORE DONATING.** Call the organization directly using a number from their official nonprofit database "
                   "(like Guidestar or Charity Navigator), not from the submission. Ask for proof of nonprofit status, physical address, and vet references. "
                   "Legitimate rescues are transparent about where donations go.")
        else:
            return ("✓ **Appears legitimate, but always verify.** Check their nonprofit status on Guidestar or IRS.gov, "
                   "visit their physical location if possible, and review their social media history for consistency. "
                   "Reputable rescues maintain transparent records and verifiable contact methods.")
    
    
    def _empty_result(self, message: str) -> Dict[str, Any]:
        """Return error/empty result."""
        return {
            "risk_level": "LOW",
            "risk_score": 0,
            "confidence": "Low",
            "matched_patterns": [],
            "signals": {"text": None, "image": None, "link": None},
            "explanation": message,
            "recommendation": "Please provide text, image, or link for analysis.",
            "input_summary": {
                "has_text": False,
                "has_image": False,
                "has_link": False
            },
            "error": message
        }


# ============================================================================
# CONVENIENCE FUNCTION FOR DASHBOARD
# ============================================================================

_pipeline = None

def get_pipeline() -> GuardPawPipeline:
    """Get singleton pipeline instance."""
    global _pipeline
    if _pipeline is None:
        _pipeline = GuardPawPipeline()
    return _pipeline


def analyze(
    user_text: str = "",
    image_path: Optional[str] = None,
    link_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Quick analysis function for dashboard.
    
    Example:
        result = analyze(
            user_text="Send money now or puppy dies",
            link_url="https://suspicious.com"
        )
        print(f"Risk: {result['risk_level']} (score: {result['risk_score']})")
    """
    pipeline = get_pipeline()
    return pipeline.analyze_submission(user_text, image_path, link_url)


if __name__ == "__main__":
    # Demo
    pipeline = GuardPawPipeline()
    
    # Test 1: Text only
    print("\n[TEST 1: Text Only]")
    result = pipeline.analyze_submission(
        user_text="They say the puppy will be euthanized in 3 hours unless I send money via Zelle."
    )
    print(f"Risk Level: {result['risk_level']}")
    print(f"Risk Score: {result['risk_score']}")
    print(f"Confidence: {result['confidence']}")
    print(f"Patterns: {len(result['matched_patterns'])}")
    
    # Test 2: Link only
    print("\n[TEST 2: Link Only]")
    result = pipeline.analyze_submission(
        link_url="https://bestfriends.org/how-you-can-help"
    )
    print(f"Risk Level: {result['risk_level']}")
    print(f"Risk Score: {result['risk_score']}")
    print(f"Confidence: {result['confidence']}")
    print(f"Patterns: {len(result['matched_patterns'])}")
    
    # Test 3: No input
    print("\n[TEST 3: Empty Input]")
    result = pipeline.analyze_submission()
    print(f"Error: {result.get('error')}")
