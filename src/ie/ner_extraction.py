import spacy
import json
import csv
import re
from pathlib import Path

# --- 1. Load Model ---
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    from spacy.cli import download
    download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

ROOT = Path(__file__).resolve().parent.parent.parent
INPUT_FILE = ROOT / "data" / "crawler_output.jsonl"
OUTPUT_FILE = ROOT / "data" / "extracted_knowledge.csv"

# --- 2. Helpers ---
def clean_text(text: str) -> str:
    if not text: return ""
    text = re.sub(r'\|', ' ', text)
    text = re.sub(r'-{3,}', ' ', text)
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def refine_entity(ent):
    text, label = ent.text, ent.label_
    if text.lower() == "moon" and label == "PERSON":
        return "LOC"
    if label == "DATE" and text.isdigit():
        return None
    return label

def extract_svo_triples(doc):
    triples = []
    for sent in doc.sents:
        ent_map = {}
        for ent in sent.ents:
            refined_label = refine_entity(ent)
            if refined_label and refined_label in ["ORG", "PERSON", "GPE", "DATE", "LOC"]:
                ent_map[ent.root.i] = (ent, refined_label)
        for token in sent:
            if token.dep_ == "nsubj" and token.i in ent_map:
                subj_ent, subj_label = ent_map[token.i]
                verb = token.head
                for child in verb.children:
                    target_token = None
                    verb_text = verb.lemma_
                    if child.dep_ in ["dobj", "attr"] and child.i in ent_map:
                        target_token = child
                    elif child.dep_ == "prep":
                        for gc in child.children:
                            if gc.dep_ == "pobj" and gc.i in ent_map:
                                target_token = gc
                                verb_text = f"{verb.lemma_} {child.text}"
                                break
                    if target_token:
                        obj_ent, obj_label = ent_map[target_token.i]
                        triples.append({
                            "Head": subj_ent.text, "Head_Type": subj_label,
                            "Relation": verb_text,
                            "Tail": obj_ent.text, "Tail_Type": obj_label,
                            "Context": sent.text
                        })
    return triples

# --- 3. Main ---
def main():
    if not INPUT_FILE.exists():
        print(f"File {INPUT_FILE} not found. Run the crawler first.")
        return
    OUTPUT_FILE.unlink(missing_ok=True)
    print("Starting Semantic Extraction...")
    with INPUT_FILE.open("r", encoding="utf-8") as f_in, \
         OUTPUT_FILE.open("w", encoding="utf-8", newline="") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=["Source","Head","Head_Type","Relation","Tail","Tail_Type","Context"])
        writer.writeheader()
        count = 0
        for line in f_in:
            data = json.loads(line)
            doc = nlp(clean_text(data["text"]))
            for triple in extract_svo_triples(doc):
                triple["Source"] = data["url"]
                writer.writerow(triple)
                count += 1
    print(f"Done! Extracted {count} relations to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
