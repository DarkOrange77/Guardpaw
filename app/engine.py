from typing import List, Dict, Any
import os


class GuardPawEngine:
    """Classifies retrieved documents into categories and produces a Risk Report.

    Categories: 'Scam Pattern', 'Legit Indicator', 'Case Study'
    """

    CATEGORY_MAP = {
        "scam_patterns": "Scam Pattern",
        "legit_Indicators": "Legit Indicator",
        "case_summaries": "Case Study",
    }

    # Weighted risk scoring: higher = riskier for scams, negative = mitigating factor
    SCAM_WEIGHTS = {
        "artificial_urgency_deadlines.md": 3,      # Classic panic trigger
        "untraceable_payments_requests.md": 3,     # Direct payment = very high risk
        "impersonation_of_authority.md": 3,        # Fake authority = high trust exploit
        "stolen_media_indicators.md": 2,           # Stock/watermarked images
        "staged_rescue_content.md": 2,             # Cinematic/improbable rescue videos
        "psychological_manipulation.md": 2,        # Guilt/graphic suffering
        "digital_footprint_anomalies.md": 2,       # New domains/bot accounts
        "inconsistent_animal_details.md": 2,       # Conflicting ages/breeds
        "private_contact_redirection.md": 2,       # Off-platform communication
        "case_fake_rescue.md": 1,                  # Past case reference (amplifies slightly)
        "no_verifiable_rescue_identity.md": 3,     # No verifiable rescue = high risk
    }

    LEGIT_WEIGHTS = {
        "physical_verification.md": -3,            # Very strong legitimacy (meet/video)
        "community_validation.md": -3,             # Traceable volunteers = strong trust
        "media_verification.md": -2,               # Verified photos reduce scam probability
        "pricing_and_transparency.md": -2,         # Transparent fees
        "education_and_awareness.md": -1,          # Awareness alone
    }

    def __init__(self, data_root: str = None):
        # data_root should point to the project `data/` folder
        if data_root is None:
            # assume project root is two levels up from this file
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            data_root = os.path.join(project_root, "data")
        self.data_root = data_root

        # build a map of filename -> category folder for quick lookup
        self.filename_to_category = {}
        for root, _, files in os.walk(self.data_root):
            rel = os.path.relpath(root, self.data_root)
            folder = rel.split(os.sep)[0] if rel not in (".",) else ""
            for f in files:
                self.filename_to_category[f] = folder

    def classify_document(self, doc: Any) -> str:
        """Return one of the categories for a document.

        doc: a LangChain Document or similar with .metadata['source'] and .page_content
        """
        # Prefer authoritative folder/path metadata (set by the loader)
        try:
            meta = getattr(doc, "metadata", {}) or {}
        except Exception:
            meta = {}

        path_meta = meta.get("path") or ""
        folder_meta = meta.get("folder") or ""
        # Normalize
        folder = (folder_meta or (path_meta.split('/')[0] if path_meta else "")).lower()

        # 1) Determine by folder (authoritative)
        if folder:
            if "scam_patterns" in folder or "scam" in folder:
                return "Scam Pattern"
            if "legit" in folder or "indicator" in folder:
                return "Legit Indicator"
            if "case" in folder or "summary" in folder:
                return "Case Study"

        # 2) Fallback: try filename -> folder mapping produced at init
        src = meta.get("source")
        if src:
            fname = os.path.basename(src)
            mapped_folder = self.filename_to_category.get(fname)
            if mapped_folder:
                mf = mapped_folder.lower()
                if "scam_patterns" in mf or "scam" in mf:
                    return "Scam Pattern"
                if "legit" in mf or "indicator" in mf:
                    return "Legit Indicator"
                if "case" in mf or "summary" in mf:
                    return "Case Study"

        # 2) Fallback to simple keyword heuristics on text
        text = ""
        try:
            text = doc.page_content.lower()
        except Exception:
            text = str(doc).lower()

        scam_keywords = ["urgent", "zelle", "donate", "untraceable", "scam", "deadline", "send money"]
        legit_keywords = ["pricing", "transparency", "community", "verification", "physical verification"]
        case_keywords = ["case", "case study", "summary", "fake rescue", "kiev", "example"]

        score = {"scam": 0, "legit": 0, "case": 0}
        for k in scam_keywords:
            if k in text:
                score["scam"] += 1
        for k in legit_keywords:
            if k in text:
                score["legit"] += 1
        for k in case_keywords:
            if k in text:
                score["case"] += 1

        best = max(score, key=lambda k: score[k])
        if score[best] == 0:
            return "Case Study"  # default
        if best == "scam":
            return "Scam Pattern"
        if best == "legit":
            return "Legit Indicator"
        return "Case Study"

    def snippet(self, doc: Any, length: int = 240) -> str:
        try:
            txt = doc.page_content.strip()
        except Exception:
            txt = str(doc)
        if len(txt) <= length:
            return txt
        # cut at sentence boundary if possible
        cut = txt[:length]
        last_period = cut.rfind('. ')
        if last_period > int(length * 0.5):
            return cut[: last_period + 1]
        return cut + "..."

    def generate_report(self, docs: List[Any]) -> Dict[str, Any]:
        """Classify a list of docs and produce a GuardPaw Risk Report.

        Returns a dict with `summary` and `items` for programmatic use, and a `text` field.
        """
        if not docs:
            return {"text": "No relevant documents found.", "summary": {}, "items": []}

        items = []
        counts = {"Scam Pattern": 0, "Legit Indicator": 0, "Case Study": 0}
        risk_score = 0
        
        for d in docs:
            cat = self.classify_document(d)
            counts[cat] = counts.get(cat, 0) + 1
            src = getattr(d, "metadata", {}).get("source") or "unknown"

            # Accumulate risk score
            if src in self.SCAM_WEIGHTS:
                risk_score += self.SCAM_WEIGHTS[src]
            if src in self.LEGIT_WEIGHTS:
                risk_score += self.LEGIT_WEIGHTS[src]  # negative numbers reduce score

            items.append({"source": src, "category": cat, "snippet": self.snippet(d)})

        # Determine overall risk from score
        scam = counts.get("Scam Pattern", 0)
        legit = counts.get("Legit Indicator", 0)
        total = sum(counts.values())

        if risk_score >= 5:
            risk = "High"
        elif risk_score >= 2:
            risk = "Medium"
        else:
            risk = "Low"

        # Compute confidence: lower confidence if conflicting signals exist
        has_scam = scam > 0
        has_legit = legit > 0
        confidence = "High"
        if has_scam and has_legit:
            confidence = "Moderate"
        elif total < 2:
            confidence = "Low"

        summary = {"counts": counts, "risk": risk, "risk_score": risk_score, "confidence": confidence}

        lines = [
            "*** GuardPaw Risk Report ***",
            f"Overall Risk: {risk}",
            f"Risk Score: {risk_score} (weighted heuristic)",
            f"Confidence: {confidence}",
            ""
        ]
        lines.append("Summary:")
        for k, v in counts.items():
            lines.append(f" - {k}: {v}")

        lines.append("")
        lines.append("Matched Documents:")
        for it in items:
            lines.append(f" - {it['source']} ({it['category']}): {it['snippet']}")

        text = "\n".join(lines)
        return {"text": text, "summary": summary, "items": items}


if __name__ == "__main__":
    # Demo: run a similarity search and print the GuardPaw report.
    try:
        import sys
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from rag.vector_store.search_index import build_or_load_index
        # For demo safety: remove any existing local index so we rebuild with the
        # currently-configured embedding backend (avoids deserialization prompts).
        idx_dir = os.path.join(project_root, "rag", "vector_store")
        for name in ("index.faiss", "index.pkl"):
            p = os.path.join(idx_dir, name)
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

        # Optional image path can be provided via env var IMAGE_PATH
        image_path = os.getenv("IMAGE_PATH")
        # Optional link URL can be provided via env var LINK_URL
        link_url = os.getenv("LINK_URL")

        q = "They say the puppy will be euthanized in 3 hours unless I send money via Zelle."

        # If link provided, analyze link, extract page text, and select images
        link_page_text = None
        link_patterns = []
        link_selected_images = []
        try:
            if link_url:
                from app.link_analysis import analyze_link, process_link_output
                link_out = analyze_link(link_url)
                link_page_text = link_out.get("page", {})
                link_selected_images = link_out.get("selected_images", [])
                # Map to GuardPaw patterns
                link_patterns_text, link_patterns = process_link_output(link_out)
        except Exception:
            link_page_text = None
            link_patterns = []

        # If image provided, analyze and merge description into query (user-uploaded image = primary)
        image_desc = None
        image_signals = []
        try:
            if image_path:
                from app.vision import GuardPawVision
                gv = GuardPawVision()
                vout = gv.analyze_image(image_path)
                # Normalize and infer GuardPaw-native signals
                image_desc, image_signals = gv.process_vision_output(vout)
        except Exception:
            image_desc = None

        # Build merged query: prefer page text (link) and include vision descriptions
        try:
            from app.vision import GuardPawVision
            gv = gv if 'gv' in locals() else GuardPawVision()
            # page description text
            page_text_blob = None
            if link_page_text and isinstance(link_page_text, dict):
                # combine title + description + payment instructions
                parts = []
                if link_page_text.get('title'):
                    parts.append(link_page_text.get('title'))
                if link_page_text.get('description'):
                    parts.append(link_page_text.get('description'))
                if link_page_text.get('payment_instructions'):
                    parts.append("PAYMENT INSTRUCTIONS:\n" + link_page_text.get('payment_instructions'))
                page_text_blob = "\n".join(parts)

            # combine user text, page_text_blob, and primary image description
            q = gv.merge_with_user_text(q, page_text_blob, image_desc)
        except Exception:
            pass

        index = build_or_load_index()
        docs = index.similarity_search(q, k=5)

        engine = GuardPawEngine()
        report = engine.generate_report(docs)

        # Apply link-derived pattern hits to score
        try:
            matched_patterns = [item.get("source") for item in report.get("items", [])]
            risk_score = report.get("summary", {}).get("risk_score", 0)

            # link-level mapped signals (from process_link_output)
            if link_patterns:
                # reuse vision helper to apply pattern weights
                gv = gv if 'gv' in locals() else __import__('app.vision', fromlist=['GuardPawVision']).GuardPawVision()
                risk_score, matched_patterns = gv.apply_vision_signals_to_score(risk_score, link_patterns, matched_patterns, multiplier=1.0)

            # Apply primary user-uploaded image signals (full weight)
            if image_signals:
                risk_score, matched_patterns = gv.apply_vision_signals_to_score(risk_score, image_signals, matched_patterns, multiplier=1.0)

            # If link contained selected images, run vision on those (reduced weight)
            link_image_descs = []
            link_image_signals = []
            for img_url in link_selected_images:
                try:
                    # Use the vision client (the analyze_image handles URLs via handle_file)
                    vout = gv.analyze_image(img_url)
                    desc, sigs = gv.process_vision_output(vout)
                    if desc:
                        link_image_descs.append(desc)
                    if sigs:
                        link_image_signals.extend(sigs)
                except Exception:
                    continue

            if link_image_signals:
                # apply with slightly reduced multiplier for link-sourced images
                risk_score, matched_patterns = gv.apply_vision_signals_to_score(risk_score, link_image_signals, matched_patterns, multiplier=0.6)

            # Update report summary values for printing
            # Determine overall risk from updated score
            if risk_score >= 5:
                risk = "High"
            elif risk_score >= 2:
                risk = "Medium"
            else:
                risk = "Low"

            # recompute confidence simply
            counts = report.get("summary", {}).get("counts", {})
            scam = counts.get("Scam Pattern", 0)
            legit = counts.get("Legit Indicator", 0)
            total = sum(counts.values())
            confidence = "High"
            if scam > 0 and legit > 0:
                confidence = "Moderate"
            elif total < 2:
                confidence = "Low"

            # Print final explainable report
            lines = [
                "*** GuardPaw Risk Report (Final) ***",
                f"Overall Risk: {risk}",
                f"Risk Score: {risk_score} (weighted heuristic)",
                f"Confidence: {confidence}",
                ""
            ]
            lines.append("Summary:")
            for k, v in counts.items():
                lines.append(f" - {k}: {v}")
            lines.append("")
            lines.append("Matched Documents:")
            for it in report.get("items", []):
                lines.append(f" - {it['source']} ({it['category']}): {it['snippet']}")
            lines.append("")
            if link_patterns:
                lines.append("Link-derived pattern hits:")
                for lp in link_patterns:
                    lines.append(f" - {lp.get('pattern')} (weight={lp.get('weight')})")
            if link_image_signals:
                lines.append("")
                lines.append("Link image findings:")
                for s in link_image_signals:
                    lines.append(f" - {s.get('pattern')} (weight={s.get('weight')})")
            if image_signals:
                lines.append("")
                lines.append("User-uploaded image findings:")
                for s in image_signals:
                    lines.append(f" - {s.get('pattern')} (weight={s.get('weight')})")

            print("\n".join(lines))
        except Exception:
            # fallback: print original report
            print(report.get("text", ""))
    except Exception as e:
        print("Demo failed:", e)
