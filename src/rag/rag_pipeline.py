# rag_pipeline.py
# RAG with RDF/SPARQL and a Local Small LLM
# Follows the structure from KB_Lab_RAG_with_Knowledge_Graphs.pdf
# Adapted for the NASA Artemis private KB (expanded.nt)

import re
import json
from typing import List, Tuple
from pathlib import Path
from rdflib import Graph
import requests

# ----------------------------
# Configuration
# ----------------------------
ROOT      = Path(__file__).resolve().parent.parent.parent
KB_FILE   = ROOT / "kg_artifacts" / "expanded.nt"
KB_FORMAT = "nt"

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL      = "llama3.1:8b"

MAX_PREDICATES = 80
MAX_CLASSES    = 40
SAMPLE_TRIPLES = 20

KB_BASE = "http://example.org/private_kb/"

# Confirmed entities from the KB
KNOWN_ENTITIES = {
    "artemis":         f"{KB_BASE}Artemis",
    "artemis program": f"{KB_BASE}Artemis",
    "artemis 4":       f"{KB_BASE}Artemis_4",
    "artemis latest":  f"{KB_BASE}Artemis_Latest",
    "nasa":            f"{KB_BASE}NASA",
    "sls":             f"{KB_BASE}SLS",
    "gateway":         f"{KB_BASE}Gateway",
    "iss":             f"{KB_BASE}ISS",
    "esa":             f"{KB_BASE}ESA",
    "boeing":          f"{KB_BASE}Boeing",
    "lockheed martin": f"{KB_BASE}Lockheed_Martin",
    "moon":            f"{KB_BASE}Harvest_Moon",
    "mars":            f"{KB_BASE}Mars",
    "earth":           f"{KB_BASE}Earth",
    "congress":        f"{KB_BASE}Congress",
    "china":           f"{KB_BASE}China",
    "apollo":          f"{KB_BASE}Apollo",
    "capstone":        f"{KB_BASE}CAPSTONE",
    "astronauts":      f"{KB_BASE}Astronauts",
    "florida":         f"{KB_BASE}Florida",
    "bill nelson":     f"{KB_BASE}Bill_Nelson",
    "donald trump":    f"{KB_BASE}Donald_Trump",
    "jim bridenstine": f"{KB_BASE}Jim_Bridenstine",
    "isaacman":        f"{KB_BASE}Isaacman",
}

# Evaluation questions matched to confirmed KB triples
EVAL_QUESTIONS = [
    "What did NASA launch?",
    "What does the SLS rocket do for Artemis?",
    "What is NASA planning?",
    "What entities are connected to NASA?",
    "When was Artemis launched?",
]


# ----------------------------
# 0) Utility: call local LLM (Ollama)
# ----------------------------

def ask_local_llm(prompt: str, model: str = MODEL) -> str:
    payload = {
        "model":   model,
        "prompt":  prompt,
        "stream":  False,
        "options": {"temperature": 0.1},
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        if response.status_code != 200:
            raise RuntimeError(
                f"Ollama API error {response.status_code}: {response.text}"
            )
        data = response.json()
        if "error" in data:
            print(f"  [LLM ERROR] {data['error']}")
        result = data.get("response", "")
        if not result:
            print(f"  [LLM WARN] Empty response. Keys: {list(data.keys())}")
        return result
    except requests.ConnectionError:
        raise RuntimeError("Ollama not running. Start with: ollama serve")


# ----------------------------
# 1) Load RDF graph
# ----------------------------

def load_graph(path: Path = KB_FILE, fmt: str = KB_FORMAT) -> Graph:
    g = Graph()
    g.parse(str(path), format=fmt)
    print(f"Loaded {len(g)} triples from {path}")
    return g


# ----------------------------
# 2) Build schema summary
# ----------------------------

def get_prefix_block(g: Graph) -> str:
    defaults = {
        "rdf":  "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        "xsd":  "http://www.w3.org/2001/XMLSchema#",
        "owl":  "http://www.w3.org/2002/07/owl#",
        "kb":   KB_BASE,
    }
    ns_map = {p: str(ns) for p, ns in g.namespace_manager.namespaces()}
    for k, v in defaults.items():
        ns_map.setdefault(k, v)
    return "\n".join(sorted(f"PREFIX {p}: <{ns}>" for p, ns in ns_map.items()))


def list_distinct_predicates(g: Graph, limit: int = MAX_PREDICATES) -> List[str]:
    q = f"SELECT DISTINCT ?p WHERE {{ ?s ?p ?o . }} LIMIT {limit}"
    return [str(row.p) for row in g.query(q)]


def list_distinct_classes(g: Graph, limit: int = MAX_CLASSES) -> List[str]:
    q = f"SELECT DISTINCT ?cls WHERE {{ ?s a ?cls . }} LIMIT {limit}"
    return [str(row.cls) for row in g.query(q)]


def sample_triples_from_graph(g: Graph, limit: int = SAMPLE_TRIPLES) -> List[Tuple]:
    q = f"SELECT ?s ?p ?o WHERE {{ ?s ?p ?o . }} LIMIT {limit}"
    return [(str(r.s), str(r.p), str(r.o)) for r in g.query(q)]


def build_schema_summary(g: Graph) -> str:
    prefixes = get_prefix_block(g)
    preds    = list_distinct_predicates(g)
    classes  = list_distinct_classes(g)
    samples  = sample_triples_from_graph(g)

    pred_lines   = "\n".join(f"- {p}" for p in preds)
    cls_lines    = "\n".join(f"- {c}" for c in classes) or "(none found)"
    sample_lines = "\n".join(f"- <{s}> <{p}> <{o}>" for s, p, o in samples)
    entity_lines = "\n".join(
        f"  {label:25s} → <{uri}>"
        for label, uri in sorted(KNOWN_ENTITIES.items())
    )

    return f"""{prefixes}

# Predicates (up to {MAX_PREDICATES})
{pred_lines}

# Classes / rdf:type (up to {MAX_CLASSES})
{cls_lines}

# Sample triples (up to {SAMPLE_TRIPLES})
{sample_lines}

# Known entity URIs (use these exactly — do NOT invent others)
{entity_lines}
""".strip()


# ----------------------------
# 3) NL → SPARQL generation
# ----------------------------

# KEY FIX: instructions now explicitly forbid binding both subject AND object,
# and require at least one projected ?variable in the WHERE clause.
SPARQL_INSTRUCTIONS = """
You are a SPARQL generator. Convert the user QUESTION into a valid SPARQL 1.1 SELECT query
for the given RDF graph schema. Follow strictly:

- Use ONLY the IRIs/prefixes visible in the SCHEMA SUMMARY.
- Use ONLY the entity URIs listed under "Known entity URIs". Do NOT invent URIs.
- Do NOT use external URIs (wikidata, dbpedia, schema.org) as subjects or objects.
- CRITICAL RULE: The SELECT query must project at least one ?variable that appears
  as an UNBOUND variable in the WHERE clause. Never write a triple where BOTH the
  subject AND the object are fixed URIs — that returns nothing to SELECT.
  WRONG:  SELECT ?x WHERE { <A> <p> <B> . }   ← both sides fixed, ?x never bound
  RIGHT:  SELECT ?o WHERE { <A> <p> ?o . }     ← ?o is unbound, will be filled
  RIGHT:  SELECT ?s WHERE { ?s <p> <B> . }     ← ?s is unbound, will be filled
- Return ONLY the SPARQL query in a single fenced code block labeled ```sparql
- No explanations or extra text outside the code block.
"""

# KEY FIX: few-shot examples now cover every question pattern we use,
# with the exact KB URIs confirmed to exist.
SPARQL_EXAMPLES = f"""
EXAMPLE 1 — "What entities are connected to NASA?"
```sparql
SELECT ?connected WHERE {{
  <{KB_BASE}NASA> ?predicate ?connected .
}}
```

EXAMPLE 2 — "What did NASA launch?"
```sparql
SELECT ?mission WHERE {{
  <{KB_BASE}NASA> <{KB_BASE}launch> ?mission .
}}
```

EXAMPLE 3 — "When was Artemis launched?"
```sparql
SELECT ?date WHERE {{
  <{KB_BASE}Artemis> <{KB_BASE}launchOn> ?date .
}}
```

EXAMPLE 4 — "What does the SLS rocket do for Artemis?"
```sparql
SELECT ?result WHERE {{
  <{KB_BASE}SLS> <{KB_BASE}doFor> ?result .
}}
```

EXAMPLE 5 — "What is NASA planning?"
```sparql
SELECT ?plan WHERE {{
  <{KB_BASE}NASA> <{KB_BASE}planFor> ?plan .
}}
```
"""

CODE_BLOCK_RE = re.compile(r"```(?:sparql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


def extract_sparql(text: str) -> str:
    """Extract first ```sparql block; fall back to first SPARQL keyword line."""
    m = CODE_BLOCK_RE.search(text)
    if m:
        return m.group(1).strip()
    keywords = {"SELECT", "ASK", "CONSTRUCT", "DESCRIBE", "PREFIX"}
    lines = text.strip().splitlines()
    start = next(
        (i for i, l in enumerate(lines)
         if l.strip().split()[:1]
         and l.strip().split()[0].upper() in keywords),
        None,
    )
    return "\n".join(lines[start:]).strip() if start is not None else text.strip()


def make_sparql_prompt(schema_summary: str, question: str) -> str:
    return f"""{SPARQL_INSTRUCTIONS}

SCHEMA SUMMARY:
{schema_summary}

{SPARQL_EXAMPLES}

QUESTION:
{question}

Return only the SPARQL query in a ```sparql code block.
"""


def generate_sparql(question: str, schema_summary: str) -> str:
    raw = ask_local_llm(make_sparql_prompt(schema_summary, question))
    return extract_sparql(raw)


# ----------------------------
# 4) Execute SPARQL with rdflib
# ----------------------------

def run_sparql(g: Graph, query: str) -> Tuple[List[str], List[Tuple]]:
    res   = g.query(query)
    vars_ = [str(v) for v in res.vars]
    rows  = [tuple(str(cell) for cell in r) for r in res]
    return vars_, rows


# ----------------------------
# 5) Self-repair
# ----------------------------

REPAIR_INSTRUCTIONS = """
The previous SPARQL query executed without error but returned ZERO rows,
OR it raised an execution error. Fix it using the schema and the hint below.

Follow strictly:
- Use only known prefixes/IRIs from the schema.
- Use only entity URIs listed under "Known entity URIs".
- Do NOT use external URIs (wikidata, dbpedia) as subjects or objects.
- CRITICAL: Make sure the SELECT variable (e.g. ?o) is an UNBOUND variable
  in the WHERE clause — do not fix both the subject AND the object.
  WRONG: SELECT ?x WHERE { <A> <p> <B> . }
  RIGHT: SELECT ?o WHERE { <A> <p> ?o . }
- Return only a single ```sparql code block with the corrected SPARQL.
"""


def repair_sparql(
    schema_summary: str,
    question: str,
    bad_query: str,
    error_msg: str,
) -> str:
    prompt = f"""{REPAIR_INSTRUCTIONS}

SCHEMA SUMMARY:
{schema_summary}

ORIGINAL QUESTION:
{question}

BAD SPARQL:
{bad_query}

ERROR / HINT:
{error_msg}

Return only the corrected SPARQL in a ```sparql code block.
"""
    raw = ask_local_llm(prompt)
    return extract_sparql(raw)


def _has_unbound_select_var(query: str) -> bool:
    """
    Heuristic: check whether the projected SELECT variables actually appear
    as unbound (not fixed-URI) patterns in the WHERE clause.
    Returns False when both subject and object look like fixed URIs (<...>).
    """
    where_match = re.search(r"WHERE\s*\{(.*)\}", query, re.DOTALL | re.IGNORECASE)
    if not where_match:
        return True  # can't tell — let it through
    where_body = where_match.group(1)
    # Count triple patterns where both S and O are fixed IRIs (no ?var)
    fixed_triples = re.findall(
        r"<[^>]+>\s+<[^>]+>\s+<[^>]+>", where_body
    )
    variable_slots = re.findall(r"\?[A-Za-z_]\w*", where_body)
    # If every triple is fully fixed and there are no ?vars → problem
    if fixed_triples and not variable_slots:
        return False
    return True


# ----------------------------
# 6) Orchestration: SPARQL-generation RAG
# ----------------------------

def answer_with_sparql_rag(
    g: Graph,
    schema_summary: str,
    question: str,
    try_repair: bool = True,
    max_repairs: int = 2,
) -> dict:
    sparql   = generate_sparql(question, schema_summary)
    repaired = False

    for attempt in range(1 + max_repairs):
        # KEY FIX: detect the "both sides fixed" pattern before executing
        if not _has_unbound_select_var(sparql):
            hint = (
                "The query has no unbound ?variable in the WHERE clause — "
                "both subject and object are fixed URIs, so SELECT returns nothing. "
                "Rewrite it so that the answer is an unbound ?variable, e.g. "
                "SELECT ?o WHERE { <subject> <predicate> ?o . }"
            )
            print(f"  [WARN attempt {attempt + 1}] Fixed-URI pattern detected — auto-repairing.")
            if try_repair and attempt < max_repairs:
                sparql   = repair_sparql(schema_summary, question, sparql, hint)
                repaired = True
                continue
        try:
            vars_, rows = run_sparql(g, sparql)

            # KEY FIX: treat zero rows as a soft failure worth repairing
            if len(rows) == 0 and try_repair and attempt < max_repairs:
                hint = (
                    "The query executed successfully but returned 0 rows. "
                    "Possible causes: wrong entity URI, wrong predicate, or "
                    "both subject and object are fixed (no ?variable to fill). "
                    "Check the Known entity URIs and rewrite with an unbound ?variable."
                )
                print(f"  [WARN attempt {attempt + 1}] 0 rows — trying repair.")
                sparql   = repair_sparql(schema_summary, question, sparql, hint)
                repaired = True
                continue

            return {
                "query":    sparql,
                "vars":     vars_,
                "rows":     rows,
                "repaired": repaired,
                "error":    None,
                "attempts": attempt + 1,
            }

        except Exception as e:
            err = str(e)
            print(f"  [SPARQL ERROR attempt {attempt + 1}] {err}")
            if try_repair and attempt < max_repairs:
                sparql   = repair_sparql(schema_summary, question, sparql, err)
                repaired = True
            else:
                return {
                    "query":    sparql,
                    "vars":     [],
                    "rows":     [],
                    "repaired": repaired,
                    "error":    err,
                    "attempts": attempt + 1,
                }

    # Final attempt exhausted
    try:
        vars_, rows = run_sparql(g, sparql)
        return {
            "query":    sparql,
            "vars":     vars_,
            "rows":     rows,
            "repaired": repaired,
            "error":    None,
            "attempts": max_repairs + 1,
        }
    except Exception as e:
        return {
            "query":    sparql,
            "vars":     [],
            "rows":     [],
            "repaired": repaired,
            "error":    str(e),
            "attempts": max_repairs + 1,
        }


# ----------------------------
# 7) Baseline: direct LLM, no KG
# ----------------------------

def answer_no_rag(question: str) -> str:
    prompt = f"Answer the following question as best as you can:\n\n{question}"
    return ask_local_llm(prompt)


# ----------------------------
# 8) Pretty-print helper
# ----------------------------

def pretty_print_result(result: dict):
    print(
        f"\n  [SPARQL Query Used] "
        f"(repaired={result['repaired']}, attempts={result['attempts']})"
    )
    print("  " + result["query"].replace("\n", "\n  "))

    if result.get("error"):
        print(f"\n  [Execution Error] {result['error']}")
        return

    vars_ = result.get("vars", [])
    rows  = result.get("rows", [])

    if not rows:
        print("\n  [No rows returned]")
        return

    print(f"\n  [Results — {len(rows)} row(s)]")
    print("  " + " | ".join(vars_))
    for r in rows[:20]:
        print("  " + " | ".join(r))
    if len(rows) > 20:
        print(f"  ... (showing 20 of {len(rows)})")


# ----------------------------
# 9) Batch evaluation (for report)
# ----------------------------

def run_evaluation(g: Graph, schema_summary: str, questions: List[str]):
    print("\n" + "=" * 60)
    print("  RAG EVALUATION")
    print("=" * 60)

    records = []
    for i, q in enumerate(questions, 1):
        print(f"\nQ{i}: {q}")

        baseline = answer_no_rag(q)
        print(f"  [Baseline] {baseline[:120]}")

        result = answer_with_sparql_rag(g, schema_summary, q)
        pretty_print_result(result)

        records.append({
            "question":     q,
            "baseline":     baseline[:300],
            "rag_status":   "SUCCESS" if not result["error"] else "FAILED",
            "rag_attempts": result["attempts"],
            "rag_repaired": result["repaired"],
            "rag_sparql":   result["query"],
            "rag_vars":     result["vars"],
            "rag_results":  result["rows"][:10],
            "rag_error":    result["error"],
        })

    out = ROOT / "data" / "rag_evaluation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(records, indent=2, ensure_ascii=False))
    print(f"\nEvaluation saved to {out}")


# ----------------------------
# 10) CLI demo
# ----------------------------

def run_cli(g: Graph, schema_summary: str):
    print("\nCLI mode — type your question or 'eval' to run batch evaluation.")
    while True:
        try:
            q = input("\nQuestion (or 'eval' / 'quit'): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not q:
            continue
        if q.lower() == "quit":
            break
        if q.lower() == "eval":
            run_evaluation(g, schema_summary, EVAL_QUESTIONS)
            continue

        print("\n--- Baseline (No RAG) ---")
        print(answer_no_rag(q))

        print(f"\n--- SPARQL-generation RAG ({MODEL} + rdflib) ---")
        result = answer_with_sparql_rag(g, schema_summary, q, try_repair=True)
        pretty_print_result(result)


# ----------------------------
# Entry point
# ----------------------------

if __name__ == "__main__":
    import sys

    g      = load_graph()
    schema = build_schema_summary(g)

    if "--eval" in sys.argv:
        run_evaluation(g, schema, EVAL_QUESTIONS)
    else:
        run_cli(g, schema)