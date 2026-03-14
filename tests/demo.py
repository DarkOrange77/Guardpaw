#!/usr/bin/env python3
"""
GuardPaw Live Demo: Text-Only vs Text+Image Analysis

This demonstrates the full pipeline:
1. Text-only scam detection (RAG + risk scoring)
2. Scam + image analysis (multimodal RAG + vision signals + scoring)
3. Link Analysis integration (optional)

Run: python tests/demo.py
"""

import sys
import os
from dotenv import load_dotenv

# Setup path and env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag.vector_store.search_index import build_or_load_index
from app.engine import GuardPawEngine
from app.vision import GuardPawVision


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def print_demo(title: str, user_text: str, image_path: str = None, link_url: str = None):
    """Run and print a complete demo: text-only or text+image."""
    print_section(title)
    print(f"User Input:\n{user_text}\n")
    
    if image_path:
        print(f"Image: {os.path.basename(image_path)}")
    
    # ==========================================
    # STEP 1: Vision Analysis (if image provided)
    # ==========================================
    vision_description = ""
    vision_signals = []
    
    if image_path and os.path.exists(image_path):
        print("\n[Vision Analysis Running...]")
        try:
            gv = GuardPawVision()
            vout = gv.analyze_image(image_path)
            vision_description, vision_signals = gv.process_vision_output(vout)
            print(f"✓ Image analyzed. Found {len(vision_signals)} vision-based signal(s).")
        except Exception as e:
            print(f"⚠ Vision analysis failed: {e}")

    # ==========================================
    # LINK ANALYSIS (if link_url provided)
    # ==========================================
    link_page_text = None
    link_signals = []
    link_selected_images = []
    if link_url:
        print("\n[Link Analysis Running...]")
        try:
            from app.link_analysis import analyze_link, process_link_output
            link_out = analyze_link(link_url)
            link_page_text = link_out.get("page", {})
            link_selected_images = link_out.get("selected_images", [])
            _, link_signals = process_link_output(link_out)
            print(f"✓ Link analyzed. Found {len(link_signals)} link-derived signal(s).")
        except Exception as e:
            print(f"⚠ Link analysis failed: {e}")
    
    # ==========================================
    # STEP 2: Merge Query (text + page_text + image description)
    # ==========================================
    gv = GuardPawVision()
    page_text_blob = None
    if link_page_text and isinstance(link_page_text, dict):
        parts = []
        if link_page_text.get('title'):
            parts.append(link_page_text.get('title'))
        if link_page_text.get('description'):
            parts.append(link_page_text.get('description'))
        if link_page_text.get('payment_instructions'):
            parts.append("PAYMENT INSTRUCTIONS:\n" + link_page_text.get('payment_instructions'))
        page_text_blob = "\n".join(parts)

    query = gv.merge_with_user_text(user_text, page_text_blob, vision_description if vision_description else None)
    print("\n[Merged Query for RAG]")
    print(f"Length: {len(query)} chars (text + optional page + image analysis combined)")
    
    # ==========================================
    # STEP 3: RAG Search
    # ==========================================
    print("\n[RAG Similarity Search (k=5)]")
    try:
        index = build_or_load_index()
        docs = index.similarity_search(query, k=5)
        print(f"✓ Retrieved {len(docs)} matching documents from knowledge base.")
    except Exception as e:
        print(f"✗ RAG search failed: {e}")
        docs = []
    
    # ==========================================
    # STEP 4: Risk Report & Scoring
    # ==========================================
    print("\n[Risk Scoring & Report Generation]")
    try:
        engine = GuardPawEngine()
        report = engine.generate_report(docs)
        
        # Extract key metrics
        summary = report.get("summary", {})
        risk_level = summary.get("risk", "Unknown")
        risk_score = summary.get("risk_score", 0)
        confidence = summary.get("confidence", "Unknown")
        counts = summary.get("counts", {})
        
        print(f"✓ Report generated.")
    except Exception as e:
        print(f"✗ Report generation failed: {e}")
        risk_level = "Error"
        risk_score = 0
        confidence = "Error"
        counts = {}
    
    # ==========================================
    # STEP 5: Vision Signal Injection (if applicable)
    # ==========================================
    if vision_signals:
        print("\n[Vision Signal Injection into Risk Score]")
        print(f"Vision signals found: {len(vision_signals)}")
        old_score = risk_score
        gv = GuardPawVision()
        matched_patterns = [item.get("source") for item in report.get("items", [])]
        risk_score, matched_patterns = gv.apply_vision_signals_to_score(
            risk_score, vision_signals, matched_patterns
        )
        print(f"Risk score: {old_score} → {risk_score} (added vision weights)")
        
        # Re-evaluate risk level based on new score
        if risk_score >= 5:
            risk_level = "High"
        elif risk_score >= 2:
            risk_level = "Medium"
        else:
            risk_level = "Low"
    
    # ==========================================
    # STEP 6: Final Report & Recommendation
    # ==========================================
    print_section("FINAL REPORT")
    
    print(f"Risk Level:       {risk_level}")
    print(f"Risk Score:       {risk_score} (weighted heuristic)")
    print(f"Confidence:       {confidence}")
    print()
    print("Document Matches:")
    for cat, count in counts.items():
        print(f"  {cat}: {count}")
    
    print()
    print("Matched Patterns:")
    for item in report.get("items", []):
        src = item.get("source", "unknown")
        cat = item.get("category", "unknown")
        print(f"  • {src} ({cat})")
    
    # ==========================================
    # Recommendation
    # ==========================================
    print()
    print("─" * 70)
    if risk_level == "High":
        recommendation = "⛔ LIKELY SCAM — Do NOT donate. Avoid sharing personal information."
    elif risk_level == "Medium":
        recommendation = "⚠️  MODERATE RISK — Investigate further. Verify rescue identity independently."
    else:
        recommendation = "✓ LOW RISK — Appears legitimate, but still verify independently."
    
    print(f"\nRECOMMENDATION:\n{recommendation}\n")
    print("─" * 70)


def main():
    """Run full demo: text-only, then text+image."""
    
    print("\n")
    print(" " * 20 + "[GUARDPAW LIVE DEMO]")
    print(" " * 15 + "Animal Rescue Scam Detection System")
    
    # ==========================================
    # DEMO 1: Text-Only Scam
    # ==========================================
    scam_text = """
Hi, I'm running an emergency rescue operation. We just found a puppy 
severely injured on the street. The vet says he needs immediate surgery 
(costs $3,000) or he will be euthanized within 3 hours.

I'm desperately asking for help. Please send money via Zelle or wire transfer 
(Western Union) to help save this precious life. Every minute counts!

I can't verify the rescue organization details right now because we're 
in the field, but I promise to send receipts later. 

Please share this with your friends and donate whatever you can. 
God bless.
""".strip()

    image_path = os.path.join(
        os.path.dirname(__file__), 
        "dog-sleep-sad-sore-wounds-260nw-568229899.webp"
    )
    link_url = os.getenv("LINK_URL")
    
    print_demo("DEMO 1: Text-Only Scam Detection", scam_text)
    
    # ==========================================
    # DEMO 2: Same Scam + Image Analysis
    # ==========================================
    if os.path.exists(image_path):
        print_demo("DEMO 2: Same Scam + Image Analysis", scam_text, image_path)
    else:
        print(f"\n[Image not found at {image_path} — skipping multimodal demo]")

    # ==========================================
    # DEMO 3: Same Scam + Link Analysis (link-only)
    # ==========================================
    if link_url:
        print_demo("DEMO 3: Same Scam + Link Analysis (no image)", scam_text, None, link_url)
    else:
        print("\n[LINK_URL not set — skipping link-only demo]")

    # ==========================================
    # DEMO 4: Same Scam + Link Analysis + Link Images
    # ==========================================
    if link_url:
        print_demo("DEMO 4: Same Scam + Link Analysis + Link Images", scam_text, None, link_url)
    else:
        print("\n[LINK_URL not set — skipping link+image demo]")
    
    print("\n" + "="*70)
    print("  Demo Complete")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
