"""User-approved embedding contracts; dialogue models remain separately restricted."""

MODEL_DIMENSIONS = {
    "text-embedding-v1": 1536,
    "text-embedding-v2": 1536,
    "text-embedding-v3": 1024,
    "text-embedding-v4": 1024,
    "qwen3.7-text-embedding-flash": 1024,
    "text-embedding-async-v1": 1536,
    "text-embedding-async-v2": 1536,
}
ASYNC_MODELS = {name for name in MODEL_DIMENSIONS if "-async-" in name}
MODEL_BATCH_SIZES = {name: (1 if name == "qwen3.7-text-embedding-flash" else 10) for name in MODEL_DIMENSIONS}
