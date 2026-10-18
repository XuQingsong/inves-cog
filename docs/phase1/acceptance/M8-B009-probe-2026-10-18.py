import json
import tempfile
from pathlib import Path

from inves_cog.perception.attribution.diagnose import build_packet, write_packet
from inves_cog.perception.attribution.links import inspect_links

items = [
    {"info_id": "n1", "headline": "Acme ships new chip", "summary": "Acme said shipments began.", "source_root": "r1",
     "published_at": "2026-10-10T00:00:00+00:00"},
    {"info_id": "n2", "headline": "Other news", "summary": "Unrelated.", "source_root": "r2",
     "published_at": "2026-10-10T01:00:00+00:00", "claims": [{"subject": "X"}]},
]

print("== L1 candidate without links")
row = {"mechanism": "需求", "info_ids": ["n1"], "affected": [{"ticker": "NVDA"}, {"ticker": "AMD"}, {"ticker": "INTC"}]}
out = inspect_links(row, items, [])
print("affected kept:", [a["ticker"] for a in out["affected"]], "| link_checked:", out.get("link_checked"),
      "| research_gaps:", out.get("research_gaps"))

print("== L1b same candidate with empty links list")
out = inspect_links({**row, "links": [], "竞争解释": [], "反证条件": "x"}, items, [])
print("affected kept:", [a["ticker"] for a in out["affected"]], "| gaps:", [g["ticker"] for g in out["research_gaps"]])

spec = {
    "object_id": "o1",
    "as_of": "2026-10-11T00:00:00+00:00",
    "reference_answers_generated_at": "2026-10-12T00:00:00+00:00",
    "reference_answers": [{"tier": "可接受"}],
    "materials": {"original": items, "completed": items},
    "extractions": {},
    "delete": {"info_id": "n1"},
    "claims": [{"info_id": "n1"}, {"info_id": "n2"}],
    "direction": "down",
    "placebo": {"trade_date": "2026-10-08", "basket": "b"},
}

print("== E1 blind leakage")
with tempfile.TemporaryDirectory() as folder:
    write_packet(spec, folder)
    packet = json.loads((Path(folder) / "packet.json").read_text())
    table = json.loads((Path(folder) / "blind_table.json").read_text())
    print("files:", sorted(p.name for p in Path(folder).iterdir()))
    print("packet.json has blind_map:", "blind_map" in packet)
    print("blind_table ids:", [r["id"] for r in table])

print("== E2 deletion strips other items")
deleted = build_packet(spec)["deleted"]
print("removed:", deleted["removed"])
print("kept n2 keys:", sorted(deleted["items"][0].keys()))

print("== E3 call plan coverage")
plan = build_packet(spec)["call_plan"]
print("total_cap:", plan["total_cap"], "cells:", [c["cell"] for c in plan["calls"]])
