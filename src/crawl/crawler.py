# crawler.py — Domain-specific web crawler with robots.txt compliance
# Implements BFS link-following (depth=1) to discover more pages.
import trafilatura
from trafilatura import extract, fetch_url
import json
import time
import re
from pathlib import Path
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser

# ---------- CONFIGURATION ----------
SEED_URLS = [
    # --- Planetary Society ---
    "https://www.planetary.org/space-missions/artemis",
    "https://www.planetary.org/articles/why-send-people-back-to-the-moon",
    "https://www.planetary.org/articles/nasa-artemis-i-successfully-launches",
    "https://www.planetary.org/articles/how-soon-will-starship-fly",
    # --- Space.com ---
    "https://www.space.com/artemis-program",
    # --- ESA ---
    "https://www.esa.int/Science_Exploration/Human_and_Robotic_Exploration/Orion/Artemis_I",
    "https://www.esa.int/Science_Exploration/Human_and_Robotic_Exploration/Orion/Artemis_II",
    "https://www.esa.int/Science_Exploration/Human_and_Robotic_Exploration/Orion/European_Service_Module",
    "https://www.esa.int/Science_Exploration/Human_and_Robotic_Exploration/Exploration/Gateway",
    "https://www.esa.int/Science_Exploration/Human_and_Robotic_Exploration/Orion/Artemis_III",
    "https://www.esa.int/Science_Exploration/Human_and_Robotic_Exploration/Orion/Artemis_IV",
    "https://www.esa.int/Science_Exploration/Human_and_Robotic_Exploration/Orion/Artemis_V",
    # --- NASA ---
    "https://www.nasa.gov/humans-in-space/artemis/",
    "https://www.nasa.gov/moontomarsarchitecture-components/",
    "https://www.nasa.gov/moontomarsarchitecture/",
    "https://www.nasa.gov/mission/gateway/",
    "https://www.nasa.gov/humans-in-space/orion-spacecraft/",
    "https://science.nasa.gov/solar-system/nasas-artemis-ii-lunar-science-operations-to-inform-future-missions/",
    "https://www.nasa.gov/centers-and-facilities/kennedy/nasas-exploration-ground-systems-welcomes-new-program-manager/",
    "https://www.nasa.gov/general/nasas-space-launch-system-overview/",
]

# Keywords to filter discovered links (must contain at least one)
DOMAIN_KEYWORDS = [
    "artemis", "orion", "sls", "space-launch-system", "lunar", "moon",
    "gateway", "starship", "exploration", "astronaut", "crew",
]

USER_AGENT = "ArtemisKB-Crawler/1.0 (Student Lab Project)"
ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_PATH = ROOT / "data" / "crawler_output.jsonl"
CRAWL_DELAY = 1.0
MIN_WORDS = 200
MAX_PAGES = 50         # Stop after this many saved pages
FOLLOW_LINKS = True    # Enable BFS link-following (depth=1)

# ---------- ROBOTS.TXT COMPLIANCE ----------
_robots_cache: dict[str, RobotFileParser] = {}

def check_robots_txt(url: str) -> bool:
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    if base not in _robots_cache:
        rp = RobotFileParser()
        rp.set_url(f"{base}/robots.txt")
        try:
            rp.read()
            print(f"  [ROBOTS] Loaded {base}/robots.txt")
        except Exception:
            print(f"  [ROBOTS] Could not load — assuming allowed")
            rp.allow_all = True
        _robots_cache[base] = rp
    return _robots_cache[base].can_fetch(USER_AGENT, url)

# ---------- LINK DISCOVERY ----------
def extract_links(html: str, base_url: str) -> list[str]:
    """Extract links from raw HTML that match our domain keywords."""
    links = set()
    for match in re.findall(r'href=["\']([^"\']+)["\']', html):
        full_url = urljoin(base_url, match)
        # Only keep http(s) links
        if not full_url.startswith("http"):
            continue
        # Only keep links relevant to our domain
        url_lower = full_url.lower()
        if any(kw in url_lower for kw in DOMAIN_KEYWORDS):
            links.add(full_url.split("#")[0].split("?")[0])  # Remove fragments/params
    return list(links)

# ---------- CORE ----------
def fetch_page(url: str) -> tuple[str | None, str | None]:
    """Returns (extracted_text, raw_html) or (None, None)."""
    try:
        html = fetch_url(url)
        if html is None:
            return None, None
        text = extract(html)
        return text, html
    except Exception as e:
        print(f"[ERROR] {url} → {e}")
        return None, None

def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.unlink(missing_ok=True)

    # BFS queue: (url, depth)
    queue = [(url, 0) for url in SEED_URLS]
    visited = set()
    saved = 0

    print(f"Starting crawl with {len(SEED_URLS)} seed URLs...")
    print(f"User-Agent: {USER_AGENT}")
    print(f"Link following: {'ON (depth=1)' if FOLLOW_LINKS else 'OFF'}")
    print(f"Max pages: {MAX_PAGES}\n")

    with OUTPUT_PATH.open("a", encoding="utf-8") as f:
        while queue and saved < MAX_PAGES:
            url, depth = queue.pop(0)

            # Skip if already visited
            if url in visited:
                continue
            visited.add(url)

            # Check robots.txt
            if not check_robots_txt(url):
                print(f"[BLOCKED] {url}")
                continue

            # Fetch
            text, html = fetch_page(url)
            if text is None:
                print(f"[FAIL] {url}")
                time.sleep(CRAWL_DELAY)
                continue

            word_count = len(text.split())

            # Discover new links from this page (depth=0 only → depth=1 children)
            if FOLLOW_LINKS and html and depth == 0:
                new_links = extract_links(html, url)
                added = 0
                for link in new_links:
                    if link not in visited:
                        queue.append((link, 1))
                        added += 1
                if added:
                    print(f"  [LINKS] Discovered {added} new domain-relevant links")

            # Filter by length
            if word_count < MIN_WORDS:
                print(f"[SKIP] {word_count}w < {MIN_WORDS}w: {url}")
                continue

            # Save
            record = {"url": url, "text": text, "length": word_count}
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            saved += 1
            print(f"[OK #{saved}] {word_count}w from: {url}")

            time.sleep(CRAWL_DELAY)

    print(f"\nDone! Saved {saved} pages to {OUTPUT_PATH.resolve()}")

if __name__ == "__main__":
    main()
