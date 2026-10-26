"""Resumable, model-isolated embedding backfill using the ordinary Bailian key."""

import argparse
import gzip
import hashlib
import json
import math
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

from inves_cog.clock import SystemClock
from inves_cog.ingest.adapters import Embedding
from inves_cog.ingest.cli import connect
from inves_cog.ingest.embedding_models import ASYNC_MODELS, MODEL_BATCH_SIZES, MODEL_DIMENSIONS
from inves_cog.ingest.http import SourceError
from inves_cog.ingest.info import extraction_body
from inves_cog.ingest.settings import ROOT, read_environment
from inves_cog.llm.usage import PostgresRecorder, usage_context


def validate_async_row(row, count, dimensions):
    value = row.get("output", {})
    index = value.get("text_index")
    if type(index) is not int or not 0 <= index < count:
        raise ValueError("Invalid asynchronous text_index")
    if value.get("code") != 200:
        return index, None, value.get("message", "provider row failure")
    vector = value.get("embedding")
    if (
        not isinstance(vector, list)
        or len(vector) != dimensions
        or not all(type(x) in (int, float) and math.isfinite(x) for x in vector)
    ):
        raise ValueError("Invalid asynchronous vector")
    return index, vector, None


def collect(connection, model, limit=None, *, include_news=False):
    groups = {}
    with connection.transaction(), connection.cursor(name="model_embedding_input") as cursor:
        cursor.execute(
            """SELECT i.info_id,i.headline,i.body,
            md5(i.headline || E'\\n' || coalesce(i.body,'')) AS fingerprint
            FROM ingest.info_items i WHERE (%s OR i.kind<>'news') AND NOT EXISTS (
                SELECT 1 FROM ingest.info_embeddings e WHERE e.info_id=i.info_id AND e.model=%s)
            ORDER BY md5(i.info_id)""",
            (include_news, model),
        )
        for row in cursor:
            text = (row["headline"] + "\n" + extraction_body(row["body"])[:2000]).replace("\r", " ").replace("\n", " ")
            digest = hashlib.sha256(text.encode()).hexdigest()
            group = groups.setdefault(digest, {"text": text, "sha256": digest, "targets": []})
            if group["text"] != text:
                raise ValueError("Input hash collision")
            group["targets"].append((row["info_id"], row["fingerprint"]))
            if limit and sum(len(g["targets"]) for g in groups.values()) >= limit:
                break
    return list(groups.values())


class Sink:
    def __init__(self, connection, model, clock):
        self.connection, self.model, self.clock = connection, model, clock
        self.pending = []
        self.written = 0

    def add(self, group, vector):
        value = json.dumps(vector, separators=(",", ":"), allow_nan=False)
        for info_id, fingerprint in group["targets"]:
            self.pending.append(
                (info_id, self.model, len(vector), group["sha256"], value, self.clock.now_utc(), info_id, fingerprint)
            )
        if len(self.pending) >= 100:
            self.flush()

    def flush(self):
        if not self.pending:
            return
        with self.connection.transaction(), self.connection.cursor() as cursor:
            cursor.executemany(
                """INSERT INTO ingest.info_embeddings
                (info_id,model,dimensions,input_sha256,embedding,created_at)
                SELECT %s,%s,%s,%s,%s::vector,%s FROM ingest.info_items i
                WHERE i.info_id=%s AND md5(i.headline || E'\\n' || coalesce(i.body,''))=%s
                ON CONFLICT (info_id,model,input_sha256) DO NOTHING""",
                self.pending,
            )
            self.written += cursor.rowcount
        self.pending.clear()


class AsyncClient:
    def __init__(self, values, clock, folder):
        self.clock, self.folder = clock, folder
        self.headers = {"Authorization": "Bearer " + values["DASHSCOPE_API_KEY"]}
        self.http = httpx.Client(timeout=60)
        self.base = "https://dashscope.aliyuncs.com/api/v1"
        self.recorder = PostgresRecorder(values["INVES_COG_DATABASE_URL"], ignore_duplicates=True)

    def submit(self, path, model):
        response = self.http.get(
            self.base + "/uploads", headers=self.headers, params={"action": "getPolicy", "model": model}
        )
        response.raise_for_status()
        policy = response.json()["data"]
        host = urlparse(policy["upload_host"])
        if (
            host.scheme != "https"
            or not host.hostname.endswith(".oss-cn-beijing.aliyuncs.com")
            or policy["x_oss_object_acl"] != "private"
        ):
            raise ValueError("Unexpected upload policy")
        key = policy["upload_dir"] + "/" + path.name
        form = {
            "OSSAccessKeyId": policy["oss_access_key_id"],
            "policy": policy["policy"],
            "Signature": policy["signature"],
            "key": key,
            "x-oss-object-acl": "private",
            "x-oss-forbid-overwrite": policy["x_oss_forbid_overwrite"],
            "success_action_status": "200",
        }
        with path.open("rb") as handle:
            result = self.http.post(policy["upload_host"], data=form, files={"file": (path.name, handle, "text/plain")})
        result.raise_for_status()
        result = self.http.post(
            self.base + "/services/embeddings/text-embedding/text-embedding",
            headers={**self.headers, "X-DashScope-Async": "enable", "X-DashScope-OssResourceResolve": "enable"},
            json={"model": model, "input": {"url": "oss://" + key}, "parameters": {"text_type": "document"}},
        )
        result.raise_for_status()
        return result.json()["output"]["task_id"]

    def result(self, task_id, destination):
        while True:
            response = self.http.get(self.base + "/tasks/" + task_id, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            status = data["output"]["task_status"]
            if status in {"FAILED", "CANCELED", "UNKNOWN"}:
                raise RuntimeError("Asynchronous task failed: " + json.dumps(data["output"]))
            if status == "SUCCEEDED":
                break
            time.sleep(10)
        url = data["output"]["url"]
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname.endswith(".aliyuncs.com"):
            raise ValueError("Unexpected result host")
        if not destination.exists():
            partial = destination.with_suffix(".part")
            with self.http.stream("GET", url) as stream, partial.open("wb") as handle:
                stream.raise_for_status()
                for chunk in stream.iter_bytes():
                    handle.write(chunk)
            partial.replace(destination)
        return data


def run_async(client, groups, model, sink, folder, clock):
    summary = {"successful_inputs": 0, "failed_inputs": 0, "tasks": [], "errors": []}
    # Submit the two inventory chunks before waiting, within the provider's
    # three-running-job limit; existing task IDs are always reused.
    for offset in range(0, len(groups), 100000):
        batch = groups[offset : offset + 100000]
        name = f"{model}-{offset}-{hashlib.sha256(json.dumps([g['sha256'] for g in batch]).encode()).hexdigest()[:16]}"
        state_path, input_path = folder / (name + ".json"), folder / (name + ".txt")
        if not state_path.exists():
            input_path.write_text("\n".join(g["text"] for g in batch) + "\n")
            state = {"task_id": client.submit(input_path, model), "started_at": clock.now_utc().isoformat()}
            state_path.write_text(json.dumps(state))
            time.sleep(1)
    for offset in range(0, len(groups), 100000):
        batch = groups[offset : offset + 100000]
        name = f"{model}-{offset}-{hashlib.sha256(json.dumps([g['sha256'] for g in batch]).encode()).hexdigest()[:16]}"
        state_path, input_path = folder / (name + ".json"), folder / (name + ".txt")
        input_path.write_text("\n".join(g["text"] for g in batch) + "\n")
        if state_path.exists():
            state = json.loads(state_path.read_text())
            if state.get("imported"):
                task = state["summary"]
                summary["successful_inputs"] += task["inputs"] - task["failed"]
                summary["failed_inputs"] += task["failed"]
                summary["tasks"].append(task)
                continue
        else:
            state = {"task_id": client.submit(input_path, model), "started_at": clock.now_utc().isoformat()}
            state_path.write_text(json.dumps(state))
        print(
            json.dumps({"model": model, "offset": offset, "inputs": len(batch), "task_id": state["task_id"]}),
            flush=True,
        )
        data = client.result(state["task_id"], folder / (name + ".jsonl.gz"))
        seen, failed = set(), 0
        with gzip.open(folder / (name + ".jsonl.gz"), "rt") as handle:
            for line in handle:
                index, vector, error = validate_async_row(json.loads(line), len(batch), MODEL_DIMENSIONS[model])
                if index in seen:
                    raise ValueError("Duplicate asynchronous text_index")
                seen.add(index)
                if vector is None:
                    failed += 1
                    if len(summary["errors"]) < 30:
                        summary["errors"].append({"input_sha256": batch[index]["sha256"], "error": error})
                else:
                    sink.add(batch[index], vector)
        sink.flush()
        failed += len(batch) - len(seen)
        token_count = data.get("usage", {}).get("total_tokens")
        elapsed = (clock.now_utc() - __import__("datetime").datetime.fromisoformat(state["started_at"])).total_seconds()
        client.recorder(
            {
                "call_id": state["task_id"],
                "task": "embedding",
                "model": model,
                "purpose": "embedding_backfill|async",
                "input_tokens": token_count,
                "output_tokens": 0,
                "latency_ms": elapsed * 1000,
                "status": ("failed" if failed else "ok")
                if token_count is not None
                else ("failed_usage_missing" if failed else "usage_missing"),
                "info_ids": [],
                "created_at": clock.now_utc(),
                "item_count": len(batch),
            }
        )
        summary["failed_inputs"] += failed
        summary["successful_inputs"] += len(batch) - failed
        task = {"task_id": state["task_id"], "inputs": len(batch), "failed": failed, "tokens": token_count}
        summary["tasks"].append(task)
        state.update(imported=True, summary=task)
        state_path.write_text(json.dumps(state))
        (folder / (model + "-progress.json")).write_text(json.dumps(summary, indent=2))
    return summary


def run_sync(values, groups, model, sink, clock, token_budget):
    summary = {"successful_inputs": 0, "failed_inputs": 0, "tokens": 0, "errors": []}
    recorder = PostgresRecorder(values["INVES_COG_DATABASE_URL"])

    def audit(row):
        recorder(row)
        if row["input_tokens"] is not None:
            summary["tokens"] += row["input_tokens"]

    adapter = Embedding({**values, "INVES_COG_EMBEDDING_ENABLED": "1"}, clock=clock, recorder=audit)
    size = MODEL_BATCH_SIZES[model]
    for offset in range(0, len(groups), size):
        if token_budget and summary["tokens"] >= token_budget:
            break
        batch = groups[offset : offset + size]
        try:
            with usage_context(purpose="embedding_backfill|sync", info_ids=[g["targets"][0][0] for g in batch]):
                vectors = adapter.batch([g["text"] for g in batch], model=model, dimensions=MODEL_DIMENSIONS[model])
        except SourceError as exc:
            if getattr(exc, "error_code", None) == "AllocationQuota.FreeTierOnly" or exc.status_code in {401, 403}:
                summary["stopped_reason"] = str(exc)
                break
            for group in batch:
                try:
                    vector = adapter(group["text"], model=model, dimensions=MODEL_DIMENSIONS[model])
                    sink.add(group, vector)
                    summary["successful_inputs"] += 1
                except SourceError as error:
                    summary["failed_inputs"] += 1
                    if len(summary["errors"]) < 30:
                        summary["errors"].append({"input_sha256": group["sha256"], "error": str(error)})
            continue
        for group, vector in zip(batch, vectors, strict=True):
            sink.add(group, vector)
        summary["successful_inputs"] += len(batch)
    sink.flush()
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=[m for m in MODEL_DIMENSIONS if m != "text-embedding-v3"], required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--include-news", action="store_true", help="Explicitly enable news embedding inputs")
    parser.add_argument("--token-budget", type=int, default=0)
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    args = parser.parse_args()
    values, clock = read_environment(args.env), SystemClock()
    folder = args.env.resolve().parent / ".harness/embedding-backfill"
    folder.mkdir(parents=True, exist_ok=True)
    started = clock.now_utc()
    with connect(values) as connection:
        # Never reuse an old cached plan that may contain now-disabled news.
        suffix = ("-with-news" if args.include_news else "-no-news") + (f"-limit{args.limit}" if args.limit else "")
        plan = folder / (args.model + suffix + "-plan.json.gz")
        if plan.exists():
            with gzip.open(plan, "rt") as handle:
                groups = json.load(handle)
        else:
            groups = collect(connection, args.model, args.limit, include_news=args.include_news)
            with gzip.open(plan, "wt") as handle:
                json.dump(groups, handle, ensure_ascii=False)
        sink = Sink(connection, args.model, clock)
        if args.model in ASYNC_MODELS:
            client = AsyncClient(values, clock, folder)
            try:
                result = run_async(client, groups, args.model, sink, folder, clock)
            finally:
                client.http.close()
        else:
            result = run_sync(values, groups, args.model, sink, clock, args.token_budget)
        result.update(
            model=args.model,
            input_rows=sum(len(g["targets"]) for g in groups),
            unique_inputs=len(groups),
            rows_written=sink.written,
            started_at=started.isoformat(),
            finished_at=clock.now_utc().isoformat(),
        )
        path = folder / (args.model + "-report.json")
        path.write_text(json.dumps(result, indent=2))
        print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
