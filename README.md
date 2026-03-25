# Artemis Knowledge Engineering Pipeline

> Full pipeline: Web Crawling → Information Extraction → KB Construction → Alignment → Reasoning → KGE → RAG  
> Domain: NASA's Artemis Space Program

---

## Project Structure

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

## Environment / Reproducibility

### 1. Requirements (`requirements.txt`)
All Python dependencies are listed in `requirements.txt`. Install them using:
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 2. Instructions for running Ollama
The RAG pipeline requires a local Large Language Model via Ollama.
1. Install [Ollama](https://ollama.com/) for your operating system.
2. Pull the required model:
```bash
ollama pull llama3.1:8b
```
3. Ensure the Ollama service is running in the background before starting the RAG demo.

---

## Hardware Requirements

- **RAM**: Minimum 8GB (16GB+ recommended for KGE processing and local LLM execution).
- **Disk Space**: At least 8GB of free space to accommodate crawled data, embeddings, and the local `llama3.1` model.
- **CPU/GPU**: A multi-core CPU is sufficient, but a GPU is highly recommended for faster knowledge graph embeddings and responsive RAG execution.

---

## Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd Project_web_datamining

# Install dependencies (as stated above)
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

---

## How to Run Each Module

The pipeline is split into sequential modules. Run them from the project root:

```bash
# 1. Crawl + Extract
python src/crawl/crawler.py
python src/ie/ner_extraction.py

# 2. Build KB + Align to Wikidata + Expand
python src/kg/kb_construction.py
python src/kg/kb_expansion.py

# 3. SWRL Reasoning
python src/reason/create_ontology.py
python src/reason/swrl_reasoning.py

# 4. KGE (Knowledge Graph Embeddings)
# Open the Jupyter notebook and run all cells
jupyter notebook notebooks/TD5_Knowledge_Reasoning.ipynb
```

---

## How to Run the RAG Demo

After building the Knowledge Graph and ensuring Ollama is installed:

1. Start the Ollama server (in a separate terminal):
```bash
ollama serve
```
2. Launch the RAG pipeline:
```bash
python src/rag/rag_pipeline.py
```

### RAG Demo Screenshot

*(Please insert your actual RAG demo screenshot below to complete this requirement)*
![RAG Demo Screenshot Placeholder](<insert_screenshot_path_here.png>)
---

## Key Results

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
