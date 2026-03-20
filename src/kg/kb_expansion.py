import rdflib
from rdflib import Graph, URIRef, Namespace
from SPARQLWrapper import SPARQLWrapper, JSON
import time
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
KG_DIR = ROOT / "kg_artifacts"
DATA_DIR = ROOT / "data"

INPUT_KB_FILE = KG_DIR / "ontology.ttl"
FINAL_KB_FILE = KG_DIR / "expanded.nt"
STATS_FILE = DATA_DIR / "statistics_report.txt"

WD = Namespace("http://www.wikidata.org/entity/")
TARGET_TRIPLES = 65000
MAX_ENTITIES = 20000
MAX_RELATIONS = 120

def get_dense_outgoing_links(wd_id, sparql_client):
    query = f"""SELECT ?p ?o WHERE {{
      wd:{wd_id} ?p ?o .
      FILTER(isIRI(?o))
      FILTER(STRSTARTS(STR(?p), "http://www.wikidata.org/prop/direct/"))
      FILTER(!CONTAINS(STR(?o), "commons.wikimedia.org"))
      FILTER(!CONTAINS(STR(?o), "Special:FilePath"))
      FILTER(!CONTAINS(STR(?o), ".svg"))
      FILTER(!CONTAINS(STR(?o), ".png"))
      FILTER(!CONTAINS(STR(?o), ".jpg"))
    }} LIMIT 50"""
    sparql_client.setQuery(query)
    triples, new_entities = [], []
    try:
        results = sparql_client.query().convert()
        for res in results["results"]["bindings"]:
            p = URIRef(res["p"]["value"]); o = URIRef(res["o"]["value"])
            triples.append((URIRef(WD[wd_id]), p, o))
            if "wikidata.org/entity/Q" in str(o):
                new_entities.append(str(o).split("/")[-1])
    except: pass
    return triples, new_entities

def main():
    print("--- STEP 4: Snowball KB Expansion ---")
    g = Graph(); g.parse(str(INPUT_KB_FILE), format="turtle")
    known_entities = set(g.subjects()) | set(g.objects())
    known_relations = set(g.predicates())
    queue, visited = deque(), set()
    for s, p, o in g.triples((None, Namespace("http://www.w3.org/2002/07/owl#").sameAs, None)):
        if "wikidata.org/entity/" in str(o):
            wd_id = str(o).split("/")[-1]; queue.append(wd_id); visited.add(wd_id)
    print(f"  {len(queue)} anchor entities.")

    sparql = SPARQLWrapper("https://query.wikidata.org/sparql")
    sparql.setReturnFormat(JSON)
    sparql.addCustomHttpHeader('User-Agent', 'StudentLab_Artemis/2.0')
    api_calls = 0

    while queue and len(g) < TARGET_TRIPLES:
        current = queue.popleft()
        triples, new_ents = get_dense_outgoing_links(current, sparql)
        for i, (s, p, o) in enumerate(triples):
            if len(known_relations) >= MAX_RELATIONS and p not in known_relations: continue
            if len(known_entities) >= MAX_ENTITIES and o not in known_entities: continue
            g.add((s, p, o)); known_relations.add(p); known_entities.add(o)
            if i < len(new_ents):
                nid = new_ents[i]
                if nid not in visited: visited.add(nid); queue.append(nid)
        api_calls += 1
        if api_calls % 50 == 0:
            print(f"  API:{api_calls} | E:{len(known_entities)} | R:{len(known_relations)} | T:{len(g)}")
        time.sleep(0.1)

    g.serialize(destination=str(FINAL_KB_FILE), format='nt')
    ft, fe, fr = len(g), len(set(g.subjects())|set(g.objects())), len(set(g.predicates()))
    stats = f"Triplets: {ft}\nEntities: {fe}\nRelations: {fr}\n"
    STATS_FILE.write_text(stats)
    print(f"\nSaved {ft} triples to {FINAL_KB_FILE}")

if __name__ == "__main__":
    main()
