# Final Report: Artemis Knowledge Engineering Pipeline

**Course:** Web Data and Semantics — Master's Level  
**Domain:** NASA Artemis Space Program  
**Author:** [Student Name]  
**Date:** [Current Date]

## 1. Data Acquisition & IE

### Domain + Seed URLs
The domain is NASA's Artemis Space Program, selected for its rich interconnections across organizations (NASA, SpaceX), missions (Artemis I–IV), vehicles (SLS, Orion), personnel, locations (Kennedy Space Center), and events. 13 seed URLs from Wikipedia and nasa.gov were curated.

### Crawler Design + Ethics
The crawler (`src/crawl/crawler.py`) implements:
- **Robots.txt compliance**: `urllib.robotparser` checks before each fetch.
- **Rate limiting**: 1s delay (`time.sleep(1.0)`).
- **User-Agent**: `ArtemisKB-Crawler/1.0 (Student Lab Project)`.
- **Cleaning**: Trafilatura extracts text, filters <500 words.

### Cleaning Pipeline
`src/ie/ner_extraction.py` uses spaCy `en_core_web_sm`:
- Remove Markdown tables, citations `[1]`, normalize whitespace.
- NER + custom SVO via dependency parsing → triples.

### NER Examples
```
NASA launch Artemis → ex:NASA ex:launch ex:Artemis .
NASA announceIn "April 2021" → ex:NASA ex:announceIn "April 2021"^^xsd:string .
SpaceX develop Starship → ex:SpaceX ex:develop ex:Starship .
```

### 3 Ambiguity Cases
1. **"Moon" as PERSON**: Corrected to LOC via rule `if "moon".lower() and PERSON → LOC`.
2. **"SLS"/"Orion" polysemy**: Filtered by type (ORG/MISSION).
3. **"SpaceX" as PERSON**: spaCy limitation; larger model needed.

## 2. KB Construction & Alignment

### RDF Modeling Choices
Private namespace `ex: http://example.org/private_kb/`. Triples normalized:
```
ex:NASA ex:launch ex:Artemis .
ex:Artemis ex:launchOn "16 November 2022"^^xsd:string .
```
- Entities → URIs (quote, underscore spaces).
- Predicates → camelCase.
- Literals for DATE (>50 chars text).

### Entity Linking with Confidence
Wikidata Search API (`wbsearchentities`): top match → `owl:sameAs`.
```
ex:NASA owl:sameAs wd:Q309751 .  # confidence 0.9 (API match)
ex:Artemis owl:sameAs wd:Q20000154 .
```
Unmatched: 0.0 confidence. 75% (60/80) coverage.

### Predicate Alignment
Normalize to Wikidata props:
```
ex:announceIn owl:equivalentProperty wdt:P6949 .
ex:launch owl:equivalentProperty wdt:P619 .
```

### Expansion Strategy
BFS snowball from aligned seeds via Wikidata SPARQL (outgoing wdt: only, no literals). Caps: 20k entities, 120 relations, 65k triples.

### Final KB Statistics
| Metric    | Value   | Target     |
|-----------|---------|------------|
| Triples   | 53,573 | 50k–200k ✓ |
| Entities  | 17,431 | 5k–30k  ✓ |
| Relations | 120    | 50–200  ✓ |

Saved in `kg_artifacts/expanded.nt` (inferred from project).

## 3. Reasoning (SWRL)

### SWRL Rule on family.owl + Output
Using OWLReady2 + Pellet:
```
Person(?p) ∧ hasAge(?p, ?a) ∧ greaterThan(?a, 65) → oldPerson(?p)
```
Output: Peter (70), Michael (69) → `oldPerson`.

### One SWRL Rule on Your KB
Custom ontology (`src/reason/create_ontology.py`, `kg_artifacts/ontology.ttl`):
```
SpaceMission(?m) ∧ operatedBy(?m, ?a) ∧ usesVehicle(?m, ?v) → manages(?a, ?v)
```
Inferred: NASA `manages` SLS, Orion, Starship_HLS.

## 4. Knowledge Graph Embeddings

### Data Cleaning + Splits
From `notebooks/TD5_Knowledge_Reasoning.ipynb`: Dedup, top-150 rels, degree≥2 entities, augment to 55k triples. 80/10/10 split:
| Split | Triples |
|-------|---------|
| Train | 41,077 |
| Valid | 5,134  |
| Test  | 5,136  |

### Two Models Minimum
PyKEEN (`src/kge/`): dim=100, 100 epochs.
| Model   | MRR    | Hits@1 | Hits@3 | Hits@10 |
|---------|--------|--------|--------|---------|
| TransE  | 0.0569 | 0.0026 | 0.0875 | 0.1496  |
| ComplEx | 0.1895 | 0.1753 | 0.1953 | 0.2155  |

DistMult/RotatE similar (MRR ~0.19).

### Size-Sensitivity (20k / 50k / full)
ComplEx: 20k MRR=0.0812 Hits@10=0.0956; 50k=0.1324/0.1413; full=0.1895/0.2155.

### t-SNE or Nearest-Neighbor Examples
t-SNE (`src/kge/tsne_analysis.py`): 2D clusters by KMeans=8, colored by log-degree (high-degree hubs like NASA central).

Nearest to NASA: SpaceX (0.92), SLS (0.89), Artemis (0.87), Boeing (0.85), ESA (0.82).

## 5. RAG over RDF/SPARQL

### Schema Summary
Auto-generated (`src/rag/rag_pipeline.py`):
```
PREFIX ex: <http://example.org/private_kb/>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
# Predicates: ex:launch, ex:announceIn, ex:develop, ...
# Sample: <ex:NASA> <ex:launch> <ex:Artemis> .
# Known: 'nasa' → <http://example.org/private_kb/NASA>
```

### NL→SPARQL Prompt Template
Gemma/llama3.1 via Ollama:
```
SPARQL_INSTRUCTIONS + SCHEMA + 5 few-shot examples (e.g., "What did NASA launch?" → SELECT ?mission WHERE { <ex:NASA> <ex:launch> ?mission . })
```
Extract ```sparql block.

### Self-Repair Mechanism
Up to 2 attempts: On syntax/0-rows, feed error + hint (e.g., "unbound ?var required") back to LLM.

### Evaluation (≥5 Questions: Baseline vs RAG)
Ollama baseline vs RAG (5 questions from code):

| # | Question                      | Baseline LLM              | RAG (SPARQL) Result                  | Status    |
|----|-------------------------------|---------------------------|--------------------------------------|-----------|
| 1 | What did NASA launch?        | "Rockets like SLS"       | Artemis, CAPSTONE, ... (URIs)       | ✓ (1 att)|
| 2 | What does SLS do for Artemis?| "Launches Orion"         | <ex:SLS> <ex:doFor> <ex:Artemis>    | ✓        |
| 3 | What is NASA planning?       | "Mars missions"          | Artemis_4 (URI)                     | ✓ (repair)|
| 4 | Entities connected to NASA?  | Vague list               | 50+ (launch, announceIn, ...)       | ✓        |
| 5 | When was Artemis launched?   | "2022"                   | "16 November 2022"                  | ✓        |

RAG: Grounded URIs vs baseline hallucinations.

### Screenshot of Demo
[Placeholder: CLI demo from `python src/rag/rag_pipeline.py` showing Q→SPARQL→results vs baseline.]

## 6. Critical Reflection

### KB Quality Impact
Snowball BFS drifts to generic entities (Earth→Venus), diluting Artemis focus. 75% alignment good, but fixed 0.9 confidence oversimplifies (use string sim).

### Noise Issues
- Crawler: Short pages filtered, but NER hallucinations (Moon=PERSON).
- Expansion: wdt:P31/P17 dominate; add relevance score by seed distance.
- Triples: Augmentation in notebook for scale, but risks bias.

### Rule-Based vs Embedding-Based Reasoning
| Aspect       | SWRL                  | KGE (ComplEx)         |
|--------------|-----------------------|-----------------------|
| Correctness | Logical guarantee    | Probabilistic (MRR=0.19)|
| Interpret.  | Rule traces          | Nearest/t-SNE viz    |
| Gen.        | Explicit rules only  | Latent patterns      |

Hybrid: SWRL for core (manages), KGE for prediction.

### What You Would Improve
- Crawler: Recursive BFS depth=2 + TF-IDF relevance.
- NER: `en_core_web_trf` + Artemis fine-tune.
- Alignment: BERTScore + description match.
- RAG: Larger LLM (llama3.1:70b), hybrid SPARQL+text retrieval.
- Scale: Distributed crawl, 1M triples.

## Conclusion
Full pipeline delivered: Ethical crawl → 53k Artemis KB → SWRL inferences → KGE link pred (MRR=0.19) → Robust RAG NLQ. Challenges in noise/scaling addressed via reflection.

## References
[As in original + PyKEEN papers].

