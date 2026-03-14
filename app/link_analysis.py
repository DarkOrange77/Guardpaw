"""
Lightweight Link Analysis for GuardPaw

Implements the 4-layer inspection described in the design:
- Layer 1: Domain & infrastructure (WHOIS)
- Layer 2: URL structure & behavior (redirects, shorteners, payment links)
- Layer 3: Page structure (light DOM checks)
- Layer 4: Media & cross-link signals (image filenames, hashes)

Output surface is similar to `vision` module:
- analyze_link(url) -> {"description": str, "signals": [str,...]}
- process_link_output(link_json) -> (text_blob, [{pattern, weight, source}])

The module is defensive: if optional libs or network fail, it returns best-effort signals.
"""
from typing import Dict, List, Tuple
import os
import re
import hashlib
from urllib.parse import urlparse
from datetime import datetime, timezone

# Optional imports
try:
    import requests
except Exception:
    requests = None

try:
    import whois as whois_lib
except Exception:
    whois_lib = None

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None


# Mapping link-level signals -> MD file + default weight
LINK_SIGNAL_MAP = {
    "domain_recent_30": {"pattern": "digital_footprint_anomalies.md", "weight": 3},
    "domain_recent_90": {"pattern": "digital_footprint_anomalies.md", "weight": 2},
    "no_verifiable_identity": {"pattern": "no_verifiable_rescue_identity.md", "weight": 3},
    "impersonation_claim": {"pattern": "impersonation_of_authority.md", "weight": 2},
    "private_contact_redirection": {"pattern": "private_contact_redirection.md", "weight": 2},
    "untraceable_payment": {"pattern": "untraceable_payments_requests.md", "weight": 3},
    "stolen_media_indicators": {"pattern": "stolen_media_indicators.md", "weight": 2},
    "inconsistent_animal_details": {"pattern": "inconsistent_animal_details.md", "weight": 2},
}

# Lightweight keyword lists for DOM-based checks (Layer 3)
IDENTITY_KEYWORDS = [
    "address", "registered", "tax id", "tax_id", "ein", "charity", "registration",
    "shelter", "rescue", "physical address", "visit", "phone"
]
AUTHORITY_CLAIM_KEYWORDS = [
    "certified rescue", "official partner", "government approved", "registered charity",
]

# Known shortener domains
SHORTENERS = set([
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "buff.ly", "is.gd"
])

# Payment link patterns (very lightweight)
PAYMENT_PATTERNS = [
    re.compile(r"paypal\.me", re.I),
    re.compile(r"venmo\.com", re.I),
    re.compile(r"cashapp\.com", re.I),
    re.compile(r"pay\.pal", re.I),
    re.compile(r"zelle", re.I),
    re.compile(r"stripe", re.I),
    re.compile(r"crypto", re.I),
    re.compile(r"bitcoin", re.I),
    re.compile(r"etherscan|metamask", re.I),
]


def _domain_from_url(url: str) -> str:
    try:
        p = urlparse(url)
        return p.netloc.lower()
    except Exception:
        return ""


def _is_shortener(domain: str) -> bool:
    d = domain.replace("www.", "")
    return any(d.endswith(s) for s in SHORTENERS)


def _get_redirect_chain(url: str) -> Tuple[List[str], str]:
    """Return (redirect_chain, final_url). Best-effort; requires requests."""
    if not requests:
        return [], url
    try:
        resp = requests.head(url, allow_redirects=True, timeout=8)
        chain = [r.headers.get("Location") or r.url for r in resp.history] if getattr(resp, "history", None) else []
        final = resp.url
        return chain, final
    except Exception:
        # fallback: try GET
        try:
            resp = requests.get(url, allow_redirects=True, timeout=10)
            chain = [r.headers.get("Location") or r.url for r in resp.history] if getattr(resp, "history", None) else []
            return chain, resp.url
        except Exception:
            return [], url


def _whois_age_days(domain: str) -> Tuple[int, dict]:
    """Return approximate age in days and raw whois dict. If whois not available, return (-1,{})"""
    if not whois_lib:
        return -1, {}
    try:
        w = whois_lib.whois(domain)
        # whoislib may return creation_date as list or datetime
        cd = w.get("creation_date") if isinstance(w, dict) else getattr(w, "creation_date", None)
        # normalize
        if isinstance(cd, list) and cd:
            cd = cd[0]
        if not cd:
            return -1, dict(w)
        if isinstance(cd, str):
            try:
                cd = datetime.fromisoformat(cd)
            except Exception:
                # best-effort parse
                cd = None
        if not isinstance(cd, datetime):
            # try to parse using strptime common formats
            try:
                cd = datetime.strptime(str(cd), "%Y-%m-%d")
            except Exception:
                cd = None
        if not cd:
            return -1, dict(w)
        now = datetime.now(timezone.utc)
        if cd.tzinfo is None:
            cd = cd.replace(tzinfo=timezone.utc)
        age = (now - cd).days
        return age, dict(w)
    except Exception:
        return -1, {}


def _fetch_page(url: str) -> Tuple[str, List[str]]:
    """Return (html_text, list_of_image_srcs) - best-effort."""
    if not requests:
        return "", []
    try:
        resp = requests.get(url, timeout=10)
        html = resp.text
        imgs = []
        if BeautifulSoup:
            try:
                soup = BeautifulSoup(html, "html.parser")
                imgs = [img.get("src") for img in soup.find_all("img") if img.get("src")]
            except Exception:
                imgs = []
        return html, imgs
    except Exception:
        return "", []


def _sha1_bytes(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()


def _inspect_images(img_srcs: List[str], base_url: str) -> List[Dict]:
    """Check image filenames for stock indicators and compute content hashes (best-effort)."""
    signals = []
    if not requests:
        return signals
    for src in img_srcs:
        try:
            # make absolute
            if src.startswith("//"):
                src = "http:" + src
            elif src.startswith("/"):
                parsed = urlparse(base_url)
                src = f"{parsed.scheme}://{parsed.netloc}{src}"
            # simple filename checks
            fn = os.path.basename(urlparse(src).path).lower()
            if any(x in fn for x in ["shutterstock", "stock", "depositphotos", "istock"]):
                signals.append({"type": "image_filename_stock", "value": fn})
            # fetch bytes and hash
            try:
                r = requests.get(src, timeout=6)
                if r.status_code == 200 and r.content:
                    h = _sha1_bytes(r.content)
                    signals.append({"type": "image_hash", "value": h, "src": src})
            except Exception:
                pass
        except Exception:
            continue
    return signals


def analyze_link(url: str) -> Dict:
    """Main entrypoint: analyze a link and return descriptive text + low-level signals list.

    signals are string keys that will be mapped by `process_link_output()`.
    """
    description_parts = []
    signals: List[str] = []

    domain = _domain_from_url(url)
    description_parts.append(f"URL: {url}")

    # Layer 1: domain & infrastructure
    if domain:
        if _is_shortener(domain):
            signals.append("shortener_detected")
            description_parts.append("Detected URL shortener or redirector.")
        age, who = _whois_age_days(domain)
        if age >= 0:
            description_parts.append(f"Domain age (days): {age}")
            if age < 30:
                signals.append("domain_recent_30")
            elif age < 90:
                signals.append("domain_recent_90")
            # registrar heuristics
            registrar = who.get("registrar") if isinstance(who, dict) else None
            if registrar and isinstance(registrar, str) and ("namecheap" in registrar.lower() or "godaddy" in registrar.lower()):
                # not necessarily bad but record
                description_parts.append(f"Registrar: {registrar}")

    # Layer 2: URL structure & behavior
    chain, final = _get_redirect_chain(url)
    if chain:
        description_parts.append(f"Redirect chain length: {len(chain)}; final: {final}")
        signals.append("redirect_chain_detected")
    # detect deep links to messaging apps
    if "wa.me" in url or "whatsapp" in url or "telegram.me" in url or "t.me" in url:
        signals.append("private_contact_redirection")
        description_parts.append("Link redirects to private messaging or contact channel.")

    # detect payment links
    for pat in PAYMENT_PATTERNS:
        if pat.search(url):
            signals.append("untraceable_payment")
            description_parts.append(f"Found payment-related link/pattern: {pat.pattern}")
            break

    # Layer 3: Page structure (light DOM)
    html, imgs = _fetch_page(url)
    if html:
        # check for identity anchors
        lowered = html.lower()
        has_identity = any(k in lowered for k in IDENTITY_KEYWORDS)
        if not has_identity:
            signals.append("no_verifiable_identity")
            description_parts.append("No obvious physical address or registration info found on page.")
        # authority claims without proof
        for claim in AUTHORITY_CLAIM_KEYWORDS:
            if claim in lowered and "http" not in lowered:
                signals.append("impersonation_claim")
                description_parts.append(f"Authority claim without clear proof: {claim}")
                break
        # check for embedded payment forms (simple heuristics)
        if "google.com/forms" in html or "form action" in html and ("paypal" in html or "stripe" in html):
            signals.append("untraceable_payment")
            description_parts.append("Page contains form or embedded payment pathways.")

    # Layer 4: Media & cross-link signals
    if imgs:
        img_signals = _inspect_images(imgs, url)
        # filename stock hits
        for isig in img_signals:
            if isig.get("type") == "image_filename_stock":
                signals.append("stolen_media_indicators")
                description_parts.append(f"Image filename suggests stock media: {isig.get('value')}")
            if isig.get("type") == "image_hash":
                # include hash in description for cross-checking in RAG later
                description_parts.append(f"Image hash: {isig.get('value')} src={isig.get('src')}")

    # light sanity: if content claims recent found date but page contains old timestamps
    # (very cheap check: look for years in page)
    years = re.findall(r"(20\d{2})", html)
    if years:
        # if year earlier than current, note potential inconsistency
        now_year = datetime.now().year
        for y in set(years):
            try:
                yi = int(y)
                if yi < now_year - 1:
                    signals.append("inconsistent_animal_details")
                    description_parts.append(f"Found older timestamp/year {yi} on page content.")
                    break
            except Exception:
                continue

    description = "; ".join(description_parts)

    # Extract structured page text and select evidentiary images (best-effort)
    page_text = extract_page_text(html, url) if html else {}
    selected_images = select_evidentiary_images(html, imgs, url) if html else []

    return {
        "description": description,
        "signals": signals,
        "images": imgs,
        "page": page_text,
        "selected_images": selected_images,
    }


def extract_page_text(html: str, base_url: str) -> Dict:
    """Extract page title, main description, updates, and payment instructions.

    Returns a dict: {"title", "description", "updates", "payment_instructions"}
    """
    if not html or not BeautifulSoup:
        return {}
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.string or "") if soup.title else ""

    # Choose the longest paragraph as main description (simple heuristic)
    paragraphs = [p.get_text(separator=" ", strip=True) for p in soup.find_all("p")]
    main_desc = max(paragraphs, key=len) if paragraphs else ""

    # Find simple updates (elements with 'update' in class or recent date-like strings)
    updates = []
    for el in soup.find_all(attrs={"class": True}):
        cls = " ".join(el.get("class"))
        if "update" in cls.lower() or "post" in cls.lower():
            txt = el.get_text(separator=" ", strip=True)
            if txt:
                updates.append(txt)
    # also pick recent text nodes with dates
    date_matches = re.findall(r"(\b\d{1,2}[ /.-](Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{1,2})[ /.-]\d{2,4}\b)|\b(20\d{2})\b", html, re.I)
    if date_matches:
        updates.extend([m[0] for m in date_matches if m])

    # Payment instructions: find nodes that contain payment patterns or keywords
    payment_texts = []
    pay_keywords = ["donate", "donation", "zelle", "paypal", "venmo", "cashapp", "wire", "bank", "crypto", "bitcoin", "pay"]
    for el in soup.find_all(text=True):
        txt = str(el).strip()
        if not txt or len(txt) < 5:
            continue
        if any(pk in txt.lower() for pk in pay_keywords):
            payment_texts.append(txt)

    return {
        "title": title,
        "description": main_desc,
        "updates": updates,
        "payment_instructions": " \n ".join(payment_texts[:3])
    }


def select_evidentiary_images(html: str, img_srcs: List[str], base_url: str) -> List[str]:
    """Select up to 2 images from page that satisfy structural conditions.

    Structural conditions (count >=2 required):
      - money proximity (nearby $/donate/goal)
      - large (width/height attributes >=600)
      - unique (not repeated)
      - urgent nearby text (exclamation, 'urgent', 'now', 'hours')
      - not banner/header/footer
    """
    if not BeautifulSoup or not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    imgs = []
    all_srcs = [s for s in img_srcs]

    money_markers = ["$", "€", "£", "donate", "goal", "raised", "zelle", "paypal", "venmo", "cashapp"]
    urgent_markers = ["urgent", "now", "hours", "today", "immediately", "please help"]

    for img in soup.find_all("img"):
        try:
            src = img.get("src")
            if not src:
                continue
            # normalize src to absolute
            if src.startswith("//"):
                src = "http:" + src
            elif src.startswith("/"):
                parsed = urlparse(base_url)
                src = f"{parsed.scheme}://{parsed.netloc}{src}"

            conds = 0

            # money proximity: check parent and siblings text
            parent = img.parent
            context_text = ""
            try:
                context_text = parent.get_text(separator=" ", strip=True) if parent else ""
            except Exception:
                context_text = ""
            if any(m in context_text.lower() for m in money_markers):
                conds += 1

            # large size via attributes
            w = img.get("width")
            h = img.get("height")
            try:
                iw = int(w) if w and str(w).isdigit() else 0
                ih = int(h) if h and str(h).isdigit() else 0
            except Exception:
                iw = ih = 0
            if iw >= 600 or ih >= 600:
                conds += 1

            # uniqueness
            occurrences = all_srcs.count(img.get("src"))
            if occurrences <= 1:
                conds += 1

            # urgent nearby text
            if any(u in context_text.lower() for u in urgent_markers) or "!" in context_text:
                conds += 1

            # not banner/header/footer heuristics
            classes = " ".join(img.get("class") or [])
            tagname = parent.name if parent else ""
            if any(x in classes.lower() for x in ["header", "banner", "logo"]) or tagname in ("header", "nav", "footer"):
                # reduce count (penalize)
                conds -= 1

            if conds >= 2:
                imgs.append(src)
        except Exception:
            continue

    # dedupe and limit to 2
    seen = []
    selected = []
    for s in imgs:
        if s in seen:
            continue
        seen.append(s)
        selected.append(s)
        if len(selected) >= 2:
            break

    return selected


def process_link_output(link_json: Dict) -> Tuple[str, List[Dict]]:
    """Map low-level link signals into GuardPaw-native patterns with weights.

    Returns (text_blob, normalized_signals) where normalized_signals is list of dicts
    {"pattern": str, "weight": int, "source": url}
    """
    text_blob = link_json.get("description", "")
    src_url = "" if not isinstance(link_json, dict) else link_json.get("description", "").split("; ")[0]
    normalized: List[Dict] = []

    # Map declared signals
    for s in link_json.get("signals", []) if isinstance(link_json, dict) else []:
        mapped = LINK_SIGNAL_MAP.get(s)
        if mapped:
            entry = {"pattern": mapped["pattern"], "weight": mapped["weight"], "source": src_url}
            if entry not in normalized:
                normalized.append(entry)

    # If no explicit mapped signals found, run lightweight keyword inference on description
    if not normalized and text_blob:
        desc = text_blob.lower()
        # domain age
        if "domain age (days):" in desc:
            m = re.search(r"domain age \(days\): (\d+)", desc)
            if m:
                age = int(m.group(1))
                if age < 30:
                    normalized.append({"pattern": "digital_footprint_anomalies.md", "weight": 3, "source": src_url})
                elif age < 90:
                    normalized.append({"pattern": "digital_footprint_anomalies.md", "weight": 2, "source": src_url})
        # image filename or hash
        if "image filename suggests stock" in desc or "image hash" in desc:
            normalized.append({"pattern": "stolen_media_indicators.md", "weight": 2, "source": src_url})
        # missing identity
        if "no obvious physical address" in desc:
            normalized.append({"pattern": "no_verifiable_rescue_identity.md", "weight": 3, "source": src_url})

    # Deduplicate by pattern, keep max weight
    collapsed: Dict[str, Dict] = {}
    for e in normalized:
        p = e.get("pattern")
        w = e.get("weight", 0)
        if p not in collapsed or w > collapsed[p].get("weight", 0):
            collapsed[p] = {"pattern": p, "weight": w, "source": e.get("source")}

    return text_blob, list(collapsed.values())


if __name__ == "__main__":
    # Small CLI demo
    import sys
    if len(sys.argv) < 2:
        print("Usage: python app/link_analysis.py <url>")
        sys.exit(1)
    url = sys.argv[1]
    out = analyze_link(url)
    text, sigs = process_link_output(out)
    print("DESCRIPTION:\n", text)
    print("\nPATTERN HITS:\n", sigs)
