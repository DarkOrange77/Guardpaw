from typing import Dict, List
import os
from PIL import Image
from gradio_client import Client, handle_file
from serpapi import GoogleSearch
import requests
from io import BytesIO


class GuardPawVision:
    """Wrapper to analyze images using Hugging Face Space API (Qwen2-VL-7B) or fallback heuristics.
    Additionally performs SerpAPI reverse image search to detect reused/stolen images.

    analyze_image(image_path) -> {"description": str, "risk_signals": [...]}
    """

    # Map model/heuristic low-level signals to GuardPaw-native patterns & weights
    VISION_SIGNAL_MAP = {
        "reverse_image_match": {"pattern": "stolen_media_indicators.md", "weight": 4},
        "image_manipulation_suspected": {"pattern": "stolen_media_indicators.md", "weight": 3},
        "stock_or_watermark_detected": {"pattern": "stolen_media_indicators.md", "weight": 2},
        "lighting_inconsistency": {"pattern": "staged_rescue_content.md", "weight": 1},
        "unnatural_posing": {"pattern": "staged_rescue_content.md", "weight": 1}
    }

    # Keyword-driven inference from free-form description -> pattern name
    VISION_KEYWORDS = {
        "stolen_media_indicators.md": [
            "watermark",
            "stock photo",
            "image appears elsewhere",
            "reused image",
            "manipulated",
            "edited",
            "ai-generated",
            "inconsistent lighting",
            "shutterstock"
        ],
        "staged_rescue_content.md": [
            "cinematic",
            "dramatic angle",
            "perfect framing",
            "no visible rescuer",
            "no tools present",
            "posed",
            "pose",
            "lighting inconsistency",
        ]
    }

    def __init__(self, hf_space: str = None, api_token: str = None, serpapi_key: str = None):
        # Use provided HF Space or default to Qwen2-VL-7B
        self.hf_space = hf_space or os.getenv("HF_SPACE_ID", "GanymedeNil/Qwen2-VL-7B")
        self.api_token = api_token or os.getenv("HUGGINGFACE_API_KEY", None)
        self.serpapi_key = serpapi_key or os.getenv("SERPAPI_API_KEY", None)
        self.client = None
        
        # Try to initialize Gradio client for HF Space
        try:
            self.client = Client(self.hf_space, hf_token=self.api_token if self.api_token else None)
        except Exception as e:
            # Fallback: try without token parameter
            try:
                self.client = Client(self.hf_space)
            except Exception as e2:
                print(f"Warning: Could not connect to Hugging Face Space {self.hf_space}: {e2}")
                self.client = None

    def reverse_image_search(self, image_path: str) -> Dict[str, any]:
        """Perform SerpAPI reverse image search to detect if image is reused elsewhere.
        
        Returns:
            {
                "found": bool,
                "num_results": int,
                "top_results": list of dicts with 'title', 'url', 'source',
                "description": str explanation
            }
        """
        if not self.serpapi_key:
            return {"found": False, "num_results": 0, "top_results": [], "description": "SerpAPI key not configured"}
        
        try:
            # Read image and encode as base64 for API
            if image_path.startswith('http://') or image_path.startswith('https://'):
                # Image is a URL - download it
                try:
                    response = requests.get(image_path, timeout=10)
                    response.raise_for_status()
                    image_url = image_path
                except Exception as e:
                    print(f"Warning: Could not download image from URL {image_path}: {e}")
                    return {"found": False, "num_results": 0, "top_results": [], "description": "Could not download image"}
            else:
                # Image is a local file
                if not os.path.exists(image_path):
                    return {"found": False, "num_results": 0, "top_results": [], "description": "Image file not found"}
                image_url = image_path

            # Call SerpAPI reverse image search
            params = {
                "engine": "google_reverse_image",
                "image_url": image_url if image_url.startswith('http') else f"file://{os.path.abspath(image_url)}",
                "api_key": self.serpapi_key
            }
            
            search = GoogleSearch(params)
            results = search.get_dict()
            
            # Extract reverse image search results
            search_results = results.get("reverse_image_results", [])
            inline_results = results.get("inline_images", [])
            
            # Combine both result sets
            all_results = search_results + inline_results
            
            # Check if image was found in multiple places (indicates reuse)
            if all_results and len(all_results) > 3:
                top_results = []
                for i, result in enumerate(all_results[:5]):  # Top 5 results
                    top_results.append({
                        "title": result.get("title", "Unknown"),
                        "url": result.get("link", result.get("source_url", "N/A")),
                        "source": result.get("source", "Unknown")
                    })
                
                description = f"Image found in {len(all_results)} online sources - possible reused/stolen media"
                return {
                    "found": True,
                    "num_results": len(all_results),
                    "top_results": top_results,
                    "description": description
                }
            elif all_results:
                return {
                    "found": False,
                    "num_results": len(all_results),
                    "top_results": all_results[:3],
                    "description": "Image found in few online sources - no widespread reuse detected"
                }
            else:
                return {
                    "found": False,
                    "num_results": 0,
                    "top_results": [],
                    "description": "No reverse image search results found"
                }
                
        except Exception as e:
            print(f"Warning: Reverse image search failed: {e}")
            return {"found": False, "num_results": 0, "top_results": [], "description": f"Search error: {str(e)[:100]}"}

    def analyze_image(self, image_path: str) -> Dict[str, List[str]]:
        """Return description text and list of detected visual signals.

        If HF Space API is available it will be used; otherwise
        a lightweight heuristic runs that looks for watermarks and repeated patterns.
        """
        description = ""
        signals: List[str] = []
        
        # Validate image path exists (for file paths, not data URLs)
        if image_path and not image_path.startswith('data:'):
            if not os.path.exists(image_path):
                print(f"Warning: Image file not found: {image_path}")
                return {"description": "Image file not accessible", "risk_signals": []}

        # ==========================================
        # STEP 1: REVERSE IMAGE SEARCH (before visual analysis)
        # ==========================================
        reverse_search_result = {}
        if image_path:
            try:
                reverse_search_result = self.reverse_image_search(image_path)
                if reverse_search_result.get("found"):
                    # Strong indicator of reused/stolen media
                    signals.append("reverse_image_match")
                    description = reverse_search_result.get("description", "")
                    print(f"Reverse image search detected reuse: {description}")
                    # Return early with strong signal - this is high confidence scam indicator
                    return {"description": description, "risk_signals": signals}
            except Exception as e:
                print(f"Warning: Reverse image search encountered error: {e}")
                # Continue with visual analysis if reverse search fails

        # ==========================================
        # STEP 2: VISUAL ANALYSIS (via HF Space or heuristics)
        # ==========================================
        # Try HF Space API first
        if self.client is not None and image_path:
            try:
                # Convert local file to handle_file for API upload
                # Add timeout of 60 seconds for API call
                result = self.client.predict(
                    image=handle_file(image_path),
                    text_input="Analyze this image and describe any animals, people, and details about the rescue operation. Look for signs of authenticity or potential manipulation.",
                    model_id="Qwen/Qwen2-VL-7B-Instruct",
                    api_name="/run_example"
                )
                # Result is typically a string or list with description
                if isinstance(result, str):
                    description = result.strip()
                elif isinstance(result, list) and len(result) > 0:
                    description = str(result[0]).strip()
                else:
                    description = str(result).strip()
            except Exception as e:
                print(f"Warning: HF Space API call failed: {e}")
                print("Falling back to heuristic image analysis...")
                description = ""

        # If no model or model failed, run simple heuristics
        if not description and image_path:
            try:
                description = self._heuristic_analysis(image_path)
            except Exception as e:
                print(f"Warning: Heuristic analysis failed: {e}")
                description = "Image analysis inconclusive"

        # Extract simple risk signals from description
        # Only flag signals if description is NOT a negative heuristic

        s = description.lower()
        is_negative_heuristic = "no obvious" in s or "inconclusive" in s
        
        if not is_negative_heuristic:
            if "watermark" in s or "©" in s or "shutterstock" in s or "stock" in s:
                signals.append("stock_or_watermark_detected")
            if "photoshop" in s or "overlay" in s or "edited" in s or "manipulat" in s:
                signals.append("image_manipulation_suspected")
        if "lighting" in s or "shadow" in s:
            signals.append("lighting_inconsistency")
        if "pose" in s or "posed" in s:
            signals.append("unnatural_posing")

        return {"description": description, "risk_signals": signals}

    def process_vision_output(self, vision_json: Dict) -> (str, List[Dict]):
        """Normalize vision output into (text_blob, signals).

        signals are list of dicts: {"pattern": str, "weight": int}
        """
        text_blob = vision_json.get("description", "") if isinstance(vision_json, dict) else str(vision_json)
        normalized: List[Dict] = []

        # 1) Map explicit risk_signals (if any)
        for s in vision_json.get("risk_signals", []) if isinstance(vision_json, dict) else []:
            mapped = self.VISION_SIGNAL_MAP.get(s)
            if mapped and mapped not in normalized:
                normalized.append(mapped.copy())

        # 2) Infer from description text using deterministic keywords
        inferred = self.infer_vision_signals(text_blob)
        for pattern in inferred:
            # pattern is a tuple (pattern_name, weight)
            patt_name, weight = pattern
            entry = {"pattern": patt_name, "weight": weight}
            if entry not in normalized:
                normalized.append(entry)

        return text_blob, normalized

    def infer_vision_signals(self, description: str) -> List[tuple]:
        """Return list of (pattern, weight) inferred from free-form description.

        Deterministic and explainable keyword matching.
        """
        if not description:
            return []

        desc = description.lower()
        results: List[tuple] = []
        for pattern, keywords in self.VISION_KEYWORDS.items():
            for k in keywords:
                if k in desc:
                    # default weight for keyword-inferred signals
                    weight = 2
                    # if we already have this pattern, keep max weight
                    existing = next((w for (p, w) in results if p == pattern), None)
                    if existing is None:
                        results.append((pattern, weight))
                    else:
                        # ensure max weight
                        if weight > existing:
                            results = [(p, w) if p != pattern else (pattern, weight) for (p, w) in results]
                    break
        return results

    def merge_with_user_text(self, user_text: str, page_text: str = None, vision_description: str = None) -> str:
        """Create combined query to pass to RAG index.search or similarity_search.

        Accepts optional `page_text` (from link analysis) and `vision_description`.
        """
        parts = ["USER DESCRIPTION:", user_text.strip() if user_text else ""]
        if page_text:
            parts.extend(["\nPAGE DESCRIPTION:", page_text.strip()])
        if vision_description:
            parts.extend(["\nIMAGE ANALYSIS:", vision_description.strip()])
        return "\n".join(parts)

    def apply_vision_signals_to_score(self, risk_score: float, vision_signals: List[Dict], matched_patterns: List[str], multiplier: float = 1.0):
        """Add vision-derived weights into existing risk score and matched patterns.

        Vision signals reinforce existing scam patterns.
        Duplicate patterns are collapsed to avoid double-counting: only the max weight per pattern is added.

        Returns (new_score, matched_patterns)
        """
        # Collapse duplicates: keep max weight per pattern
        pattern_weights: Dict[str, float] = {}
        for sig in vision_signals:
            p = sig.get("pattern")
            w = sig.get("weight", 0)
            if p:
                pattern_weights[p] = max(pattern_weights.get(p, 0), float(w))
        
        # Apply collapsed weights to score and matched patterns
        for p, w in pattern_weights.items():
            try:
                risk_score += float(w) * float(multiplier)
            except Exception:
                pass
            if p not in matched_patterns:
                matched_patterns.append(p)
        
        return risk_score, matched_patterns

    def format_image_report(self, description: str, vision_signals: List[Dict]) -> Dict[str, str]:
        """Return a small, explainable image findings section for the final report."""
        findings = []
        for s in vision_signals:
            findings.append(f"Matched pattern: {s.get('pattern')} (weight={s.get('weight')})")

        if not findings:
            findings_text = "Image analysis inconclusive — no strong manipulation signals detected."
            confidence = "low"
        else:
            findings_text = "; ".join(findings)
            confidence = "medium"

        explain = (
            "Image analysis flagged potential issues consistent with known scam patterns"
            if vision_signals else
            "No clear image-based scam signals found"
        )

        return {
            "image_findings": findings_text,
            "confidence_impact": confidence,
            "explainability": explain
        }

    def _heuristic_analysis(self, image_path: str) -> str:
        """Very small heuristic: check for obvious watermark-like regions (corners)
        and image size/format to guess reused/stock images. This is a fallback only.
        """
        try:
            img = Image.open(image_path).convert("RGB")
            w, h = img.size
            # sample corner regions to detect near-white text (simple watermark detector)
            corners = [img.crop((0, 0, int(w * 0.2), int(h * 0.2))),
                       img.crop((w - int(w * 0.2), 0, w, int(h * 0.2))),
                       img.crop((0, h - int(h * 0.2), int(w * 0.2), h)),
                       img.crop((w - int(w * 0.2), h - int(h * 0.2), w, h))]
            white_px = 0
            total_px = 0
            for c in corners:
                data = c.getdata()
                for r, g, b in data:
                    total_px += 1
                    if r > 200 and g > 200 and b > 200:
                        white_px += 1
            white_ratio = white_px / max(1, total_px)
            parts = []
            if white_ratio > 0.15:
                parts.append("Watermark or bright corner text suspected")
            if w < 400 or h < 400:
                parts.append("Small resolution image — possible thumbnail or reused stock")
            if not parts:
                return "No obvious watermark or manipulation detected (heuristic)."
            return ". ".join(parts)
        except Exception:
            return "(image heuristic analysis failed)"
