import pandas as pd
from rdflib import Graph, Literal, RDF, URIRef, Namespace
from rdflib.namespace import XSD, OWL, RDFS
import urllib.parse
import requests
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data"
KG_DIR = ROOT / "kg_artifacts"

INPUT_CSV   = DATA_DIR / "extracted_knowledge.csv"
KB_FILE     = KG_DIR / "ontology.ttl"
MAPPING_FILE = DATA_DIR / "mapping_table.csv"
ALIGNMENT_TTL = KG_DIR / "alignment.ttl"
PRED_ALIGN_FILE = DATA_DIR / "predicate_alignment.csv"

EX = Namespace("http://example.org/private_kb/")
WD = Namespace("http://www.wikidata.org/entity/")
WDT = Namespace("http://www.wikidata.org/prop/direct/")
SPARQL_URL = "https://query.wikidata.org/sparql"

def clean_uri(text):
    if pd.isna(text): return EX.Unknown
    safe = urllib.parse.quote(str(text).replace(" ", "_").replace('"', "").strip())
    return URIRef(EX[safe])

def clean_predicate(text):
    if pd.isna(text): return EX.relation
    words = str(text).split()
    if not words: return EX.relation
    camel = words[0].lower() + "".join(x.capitalize() for x in words[1:])
    return EX[camel]

def get_wikidata_id(label):
    url = "https://www.wikidata.org/w/api.php"
    params = {"action":"wbsearchentities","language":"en","format":"json","search":label,"limit":1}
    try:
        r = requests.get(url, params=params, headers={"User-Agent":"StudentLab/1.0"}, timeout=5)
        data = r.json()
        if data.get("search"): return data["search"][0]["id"]
    except: pass
    return None

def sparql_find_predicate(keyword):
    """
    SPARQL query on Wikidata: find properties whose label contains the keyword.
    Returns list of (property_id, property_label).
    """
    # Convert camelCase to space-separated words for search
    import re
    words = re.sub(r'([A-Z])', r' \1', keyword).strip().lower()
    # Use the first meaningful word (skip very short ones)
    search_terms = [w for w in words.split() if len(w) > 2]
    if not search_terms:
        search_terms = [words]

    query = f"""SELECT ?property ?propertyLabel WHERE {{
  ?property a wikibase:Property .
  ?property rdfs:label ?propertyLabel .
  FILTER(CONTAINS(LCASE(?propertyLabel), "{search_terms[0]}"))
  FILTER(LANG(?propertyLabel) = "en")
}} LIMIT 10"""

    headers = {"Accept": "application/sparql-results+json", "User-Agent": "StudentLab/1.0"}
    try:
        r = requests.get(SPARQL_URL, params={"query": query}, headers=headers, timeout=15)
        results = r.json().get("results", {}).get("bindings", [])
        candidates = []
        for res in results:
            pid = res["property"]["value"].split("/")[-1]
            plabel = res["propertyLabel"]["value"]
            candidates.append((pid, plabel))
        return candidates
    except:
        return []

def main():
    KG_DIR.mkdir(parents=True, exist_ok=True)

    # ====== STEP 1: Build Initial KB ======
    print("--- STEP 1: Build Initial KB ---")
    df = pd.read_csv(INPUT_CSV)
    print(f"Loaded {len(df)} rows.")

    g = Graph()
    g.bind("ex", EX); g.bind("owl", OWL); g.bind("wd", WD); g.bind("wdt", WDT)
    entities_to_link = set()
    predicates_used = set()

    for _, row in df.iterrows():
        subject = clean_uri(row["Head"])
        entities_to_link.add((subject, row["Head"]))
        predicate = clean_predicate(row["Relation"])
        predicates_used.add((predicate, row["Relation"]))
        if row.get("Tail_Type") == "DATE" or (isinstance(row["Tail"], str) and len(str(row["Tail"])) > 50):
            obj = Literal(row["Tail"], datatype=XSD.string)
        else:
            obj = clean_uri(row["Tail"])
            entities_to_link.add((obj, row["Tail"]))
        g.add((subject, predicate, obj))

    print(f"Initial KB: {len(g)} triples, {len(entities_to_link)} unique entities, {len(predicates_used)} predicates")

    # ====== STEP 2: Entity Linking ======
    print("\n--- STEP 2: Entity Linking ---")
    mapping_data = []
    alignment_graph = Graph()
    alignment_graph.bind("ex", EX); alignment_graph.bind("owl", OWL)
    alignment_graph.bind("wd", WD); alignment_graph.bind("wdt", WDT)
    found = 0
    for i, (uri, label) in enumerate(entities_to_link):
        if pd.isna(label): continue
        wd_id = get_wikidata_id(label)
        if wd_id:
            wd_uri = URIRef(WD[wd_id])
            mapping_data.append({"Private Entity": label, "External URI": str(wd_uri), "Confidence": "0.9"})
            alignment_graph.add((uri, OWL.sameAs, wd_uri))
            g.add((uri, OWL.sameAs, wd_uri))
            found += 1
        else:
            mapping_data.append({"Private Entity": label, "External URI": "N/A", "Confidence": "0.0"})
        if (i+1) % 10 == 0: print(f"  {i+1}/{len(entities_to_link)} entities...")
        time.sleep(0.5)
    print(f"Alignment: {found} entities linked.")

    # ====== STEP 3: Predicate Alignment via SPARQL ======
    print(f"\n--- STEP 3: Predicate Alignment via SPARQL ({len(predicates_used)} predicates) ---")
    pred_alignment_data = []

    for pred_uri, pred_label in predicates_used:
        if pd.isna(pred_label):
            continue
        pred_name = str(pred_label).strip()
        print(f"\n  Private predicate: ex:{pred_name}")

        # Query Wikidata for matching properties
        candidates = sparql_find_predicate(pred_name)

        if candidates:
            # Pick the best candidate (first one, most relevant)
            best_pid, best_label = candidates[0]
            wd_prop = URIRef(WDT[best_pid])

            print(f"  Candidates from Wikidata:")
            for pid, plabel in candidates[:5]:
                marker = " ← SELECTED" if pid == best_pid else ""
                print(f"    wdt:{pid} → \"{plabel}\"{marker}")

            # Add alignment: owl:equivalentProperty
            alignment_graph.add((pred_uri, OWL.equivalentProperty, wd_prop))
            g.add((pred_uri, OWL.equivalentProperty, wd_prop))

            pred_alignment_data.append({
                "Private Predicate": pred_name,
                "Private URI": str(pred_uri),
                "Wikidata Property": f"wdt:{best_pid}",
                "Wikidata Label": best_label,
                "Relation": "owl:equivalentProperty",
                "Candidates": "; ".join(f"wdt:{p}={l}" for p, l in candidates[:5])
            })
        else:
            print(f"  No Wikidata match found.")
            pred_alignment_data.append({
                "Private Predicate": pred_name,
                "Private URI": str(pred_uri),
                "Wikidata Property": "N/A",
                "Wikidata Label": "N/A",
                "Relation": "none",
                "Candidates": ""
            })

        time.sleep(1.0)  # Rate limit for Wikidata SPARQL

    # Save predicate alignment table
    pd.DataFrame(pred_alignment_data).to_csv(PRED_ALIGN_FILE, index=False)
    print(f"\n  Predicate alignment saved to: {PRED_ALIGN_FILE}")
    aligned_preds = sum(1 for r in pred_alignment_data if r["Wikidata Property"] != "N/A")
    print(f"  {aligned_preds}/{len(predicates_used)} predicates aligned.")

    # ====== FINAL STATS ======
    total_t = len(g)
    total_e = len(set(g.subjects()) | set(g.objects()))
    print(f"\n--- FINAL ---")
    print(f"  Triples:  {total_t}")
    print(f"  Entities: {total_e}")

    pd.DataFrame(mapping_data).to_csv(MAPPING_FILE, index=False)
    alignment_graph.serialize(destination=str(ALIGNMENT_TTL), format="turtle")
    g.serialize(destination=str(KB_FILE), format="turtle")
    print(f"\n-> {KB_FILE}\n-> {ALIGNMENT_TTL}\n-> {MAPPING_FILE}\n-> {PRED_ALIGN_FILE}")

if __name__ == "__main__":
    main()
