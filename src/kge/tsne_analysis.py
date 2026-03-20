# tsne_analysis.py — t-SNE Clustering Visualization of KGE Embeddings
# Copy the run_tsne_analysis() function into the notebook after training.

import numpy as np
import matplotlib.pyplot as plt
from sklearn.manifold import TSNE
from sklearn.cluster import KMeans
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

def run_tsne_analysis(trained_models, training_tf, testing_tf):
    """Call this in the notebook: run_tsne_analysis(trained_models, training_tf, testing_tf)"""
    model = trained_models["DistMult"]
    embeddings = model.entity_representations[0](indices=None).detach().cpu().numpy()
    n = embeddings.shape[0]
    print(f"Entities: {n}, Dim: {embeddings.shape[1]}")

    degree = Counter()
    for h, r, t in training_tf.mapped_triples.numpy():
        degree[int(h)] += 1; degree[int(t)] += 1
    degrees = np.array([degree.get(i, 0) for i in range(n)])

    # Sample if needed
    max_pts = 5000
    if n > max_pts:
        idx = np.argsort(-degrees)
        sample = np.concatenate([idx[:2000], np.random.choice(idx[2000:], min(3000, len(idx)-2000), replace=False)])
    else:
        sample = np.arange(n)

    emb_s = embeddings[sample]
    deg_s = degrees[sample]

    print("Running t-SNE...")
    coords = TSNE(n_components=2, perplexity=30, random_state=42, n_iter=1000, init='pca').fit_transform(emb_s)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8))

    sc = ax1.scatter(coords[:,0], coords[:,1], c=np.log1p(deg_s), cmap='viridis', s=3, alpha=0.6)
    plt.colorbar(sc, ax=ax1, label='log(degree+1)')
    ax1.set_title('DistMult Embeddings (by degree)')

    labels = KMeans(n_clusters=8, random_state=42, n_init=10).fit_predict(emb_s)
    for c in range(8):
        m = labels == c
        ax2.scatter(coords[m,0], coords[m,1], s=3, alpha=0.6, label=f'Cluster {c} ({m.sum()})')
    ax2.set_title('K-Means Clustering (k=8)')
    ax2.legend(fontsize=7, markerscale=5)

    plt.tight_layout()
    out = ROOT / "data" / "tsne_embeddings.png"
    plt.savefig(str(out), dpi=150, bbox_inches='tight')
    print(f"Saved: {out}")
    plt.show()
