"""Compare approved embeddings on the same operator-labelled real-news corpus."""

import argparse
import json
from pathlib import Path

import numpy as np

from inves_cog.clock import SystemClock
from inves_cog.ingest.adapters import Embedding
from inves_cog.ingest.embedding_models import ASYNC_MODELS, MODEL_BATCH_SIZES, MODEL_DIMENSIONS
from inves_cog.ingest.settings import read_environment
from inves_cog.llm.usage import usage_context


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--env", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--models", nargs="+", required=True)
    args = parser.parse_args()
    dataset = json.loads(args.dataset.read_text())
    documents, queries = dataset["documents"], dataset["queries"]
    identifiers = [row["id"] for row in documents]
    texts = [row["text"] for row in documents + queries]
    values, clock = read_environment(args.env), SystemClock()
    report = {
        "documents": len(documents),
        "queries": len(queries),
        "models": [],
        "limitation": "Small operator-labelled corpus; default document-mode vectors for queries and documents; "
        "not a general benchmark.",
    }
    for model in args.models:
        if model not in MODEL_DIMENSIONS or model in ASYNC_MODELS or model == "text-embedding-v3":
            raise ValueError("Choose an approved synchronous model with free quota")
        adapter = Embedding({**values, "INVES_COG_EMBEDDING_ENABLED": "1"}, clock=clock)
        started, vectors = clock.now_utc(), []
        size = MODEL_BATCH_SIZES[model]
        for offset in range(0, len(texts), size):
            with usage_context(purpose="embedding_comparison"):
                vectors.extend(
                    adapter.batch(texts[offset : offset + size], model=model, dimensions=MODEL_DIMENSIONS[model])
                )
        matrix = np.asarray(vectors, dtype=np.float32)
        matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)
        scores = matrix[len(documents) :] @ matrix[: len(documents)].T
        ranks = []
        for query, row in zip(queries, scores, strict=True):
            ordered = np.argsort(-row).tolist()
            ranks.append(ordered.index(identifiers.index(query["target_id"])) + 1)
        item = {
            "model": model,
            "dimensions": MODEL_DIMENSIONS[model],
            "elapsed_seconds": (clock.now_utc() - started).total_seconds(),
            "target_ranks": ranks,
            "top1": sum(x == 1 for x in ranks) / len(ranks),
            "recall_at_5": sum(x <= 5 for x in ranks) / len(ranks),
            "mrr": sum(1 / x for x in ranks) / len(ranks),
        }
        np.savez_compressed(args.output.parent / (model + "-comparison.npz"), vectors=matrix)
        report["models"].append(item)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps(item), flush=True)


if __name__ == "__main__":
    main()
