"""Price-only anomaly detection. News tables are not inputs."""

INPUT_TABLES = (
    "marketstate.daily",
    "marketstate.baskets",
    "marketstate.rotation",
    "marketstate.market",
    "graph.baskets",
    "graph.cluster_suggestions",
    "ingest.bars_daily",
    "ingest.bars_minute",
    "ingest.macro_observations",
    "ingest.short_interest",
    "ingest.issuer_profiles",
)
