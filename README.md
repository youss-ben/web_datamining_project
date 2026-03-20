# Artemis Knowledge Engineering Pipeline

> Full pipeline: Web Crawling → Information Extraction → KB Construction → Alignment → Reasoning → KGE → RAG  
> Domain: NASA's Artemis Space Program

---

## 📁 Project Structure

```
project-root/
├─ src/
│  ├─ crawl/
│  │  └─ crawler.py              # Domain crawler with robots.txt compliance
│  ├─ ie/
│  │  └─ ner_extraction.py       # NER + relation extraction (spaCy)
│  ├─ kg/
│  │  ├─ kb_construction.py      # Private KB + Wikidata alignment
│  │  └─ kb_expansion.py         # Snowball expansion via SPARQL
│  ├─ reason/
│  │  ├─ create_ontology.py      # family.owl generator
│  │  └─ swrl_reasoning.py       # SWRL rules (family.owl + Artemis KB)
│  ├─ kge/
│  │  └─ tsne_analysis.py        # t-SNE embedding visualization
│  └─ rag/
│     └─ rag_pipeline.py         # NL→SPARQL with self-repair loop
├─ data/
│  ├─ samples/
│  └─ README.md
├─ kg_artifacts/
│  ├─ ontology.ttl               # Initial private KB (Turtle)
│  ├─ expanded.nt                # Expanded KB (N-Triples, 50k+ triples)
│  └─ alignment.ttl              # owl:sameAs alignment to Wikidata
├─ reports/
│  └─ final_report.md
├─ notebooks/
│  └─ TD5_Knowledge_Reasoning.ipynb
├─ README.md
├─ requirements.txt
├─ .gitignore
└─ LICENSE
```

---

## 🛠 Installation

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# For RAG (optional):
# Install Ollama: https://ollama.com
ollama pull gemma:2b
```

---

## 🚀 How to Run

```bash
# Step 1 — Crawl + Extract
python src/crawl/crawler.py
python src/ie/ner_extraction.py

# Step 2 — Build KB + Align + Expand
python src/kg/kb_construction.py
python src/kg/kb_expansion.py

# Step 3 — SWRL Reasoning
python src/reason/create_ontology.py
python src/reason/swrl_reasoning.py

# Step 4 — KGE (open notebook)
jupyter notebook notebooks/TD5_Knowledge_Reasoning.ipynb

# Step 5 — RAG
ollama serve   # in a separate terminal
python src/rag/rag_pipeline.py
```

---

## 📊 Key Results

| Metric | Value | Target |
|--------|-------|--------|
| Triples | 53,573 | 50k–200k ✓ |
| Entities | 17,431 | 5k–30k ✓ |
| Relations | 120 | 50–200 ✓ |

| KGE Model | MRR | Hits@1 | Hits@3 | Hits@10 |
|-----------|-----|--------|--------|---------|
| TransE | 0.0569 | 0.0026 | 0.0875 | 0.1496 |
| **DistMult** | **0.1895** | **0.1753** | **0.1953** | **0.2155** |
| ComplEx | 0.0542 | 0.0412 | 0.0591 | 0.0790 |
| **RotatE** | **0.1890** | **0.1722** | **0.1951** | **0.2188** |
