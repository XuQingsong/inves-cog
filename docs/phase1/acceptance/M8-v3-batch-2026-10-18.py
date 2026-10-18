"""M8 v3 live batch. One HTTP attempt per slot. No database and no retries.

Code pin 820e5e9, prompt evidence-bridge-v3-links. Four historical cases, five
anomalies: four unique claim payloads once, then each candidate payload three
times. Claims are attached before the candidate payload is hashed. The
2026-10-17 recordings are not read. News text is not written to git.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

CODE_PIN = "820e5e958e21716c768000ac1b2b4a1809eeb9c0"
BATCH = "m8-v3-2026-10-18"
PROMPT = "evidence-bridge-v3-links"
CAP = 19
RUNS = 3
WORKERS = 5
LLM_BASE = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
CLAIM_PREFIX = {
    "2025-01-27:close:001": "1ce62f664de0",
    "2026-09-21:close:001": "c92b8e2d3772",
    "2026-09-21:close:002": "c92b8e2d3772",
    "2026-10-02:close:001": "69a8399837ec",
    "2026-10-14:close:001": "9fe317c92128",
}
EMPTY_CANDIDATE_PREFIX = {
    "2025-01-27:close:001": "b1d6db8ea0e4",
    "2026-09-21:close:001": "a19a9856d3d7",
    "2026-09-21:close:002": "d422f73df7b0",
    "2026-10-02:close:001": "5d6a640b6afa",
    "2026-10-14:close:001": "9fa7bc3af061",
}


class BatchStop(RuntimeError):
    pass


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("plan", "run", "self-check"))
    parser.add_argument("--src", required=True)
    parser.add_argument("--root")
    parser.add_argument("--fixture")
    parser.add_argument("--key-file")
    args = parser.parse_args(argv)
    modules = pin_src(Path(args.src))
    fixture = Path(args.fixture) if args.fixture else Path(args.src).resolve().parent / "tests/fixtures/phase1"
    if args.command == "plan":
        json.dump(build_manifest(modules, fixture), sys.stdout, ensure_ascii=False, indent=1)
        sys.stdout.write("\n")
        return 0
    if args.command == "self-check":
        self_check(modules, fixture)
        print("self-check ok")
        return 0
    if not args.root:
        raise SystemExit("run 需要 --root")
    return live(modules, fixture, Path(args.root), key_file_path(args.key_file))


def pin_src(src):
    src = src.resolve()
    repo = src.parent
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    if head != CODE_PIN:
        raise SystemExit(f"代码不是 {CODE_PIN[:12]}，当前 {head[:12]}")
    sys.path.insert(0, str(src))
    for name in list(sys.modules):
        if name == "inves_cog" or name.startswith("inves_cog."):
            del sys.modules[name]
    from inves_cog.perception.attribution.capture_plan import case_payloads
    from inves_cog.perception.attribution.claims import _bind_source_level, read_claims
    from inves_cog.perception.attribution.historical import judge_recording
    from inves_cog.perception.attribution.propose import PROMPT_VERSION, candidate_payload

    from inves_cog.llm.client import CallSpec, canonical_payload
    from inves_cog.llm.registry import Registry
    from inves_cog.llm.usage import DialogueResult, tokens

    if PROMPT_VERSION != PROMPT:
        raise SystemExit(f"提示词不是 {PROMPT}，当前 {PROMPT_VERSION}")
    return {
        "canonical_payload": canonical_payload,
        "registry": Registry(repo / "config/llm_tasks.yaml"),
        "CallSpec": CallSpec,
        "DialogueResult": DialogueResult,
        "tokens": tokens,
        "case_payloads": case_payloads,
        "bind": _bind_source_level,
        "read_claims": read_claims,
        "candidate_payload": candidate_payload,
        "judge_recording": judge_recording,
    }


def digest(canonical, payload):
    return hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()


def build_manifest(modules, fixture):
    rows = modules["case_payloads"](fixture)
    groups = claim_groups(modules, rows)
    claims = []
    for group in groups:
        claims.append(
            {
                "sha256": group["sha256"],
                "calls": 1,
                "model": "deepseek-v4.1-flash",
                "anomaly_ids": [item["anomaly_id"] for item in group["cases"]],
            }
        )
    empty = []
    for row in rows:
        anomaly_id = row["anomaly"]["anomaly_id"]
        empty.append(
            {
                "case_kind": row["case_kind"],
                "anomaly_id": anomaly_id,
                "sha256": digest(modules["canonical_payload"], row["candidate_payload"]),
                "called": False,
            }
        )
    return {
        "batch": BATCH,
        "code": CODE_PIN,
        "prompt_version": PROMPT,
        "read_on": "2026-10-16",
        "neighbors": [],
        "http_cap": CAP,
        "retries": 0,
        "order": "先四次说法抽取，接上说法后再冻结候选哈希，然后每个候选载荷跑 3 次",
        "models": {"claim_extraction": "deepseek-v4.1-flash", "anomaly_candidates": "glm-5.3"},
        "claims": claims,
        "empty_claim_candidates_not_called": empty,
        "five_day_in_pool": {
            "included": False,
            "reason": "本机没有 2026-10-12 至 10-16 的 9 个池内异常输入，仓库夹具不能代替",
        },
    }


def claim_groups(modules, rows):
    groups = []
    index = {}
    for row in rows:
        payload = row["claim_payload"]
        if not isinstance(payload, dict):
            raise BatchStop(f"{row['anomaly']['anomaly_id']} 没有说法载荷")
        sha = digest(modules["canonical_payload"], payload)
        if sha not in index:
            index[sha] = {"sha256": sha, "payload": payload, "cases": [], "items": row["items"]}
            groups.append(index[sha])
        index[sha]["cases"].append({"case_kind": row["case_kind"], "anomaly_id": row["anomaly"]["anomaly_id"]})
    if len(groups) != 4 or len(rows) != 5:
        raise BatchStop(f"对象数量不对：说法 {len(groups)}，异常 {len(rows)}")
    return groups


def key_file_path(explicit):
    if explicit:
        return Path(explicit)
    return Path(__file__).resolve().parents[3] / "secrets" / "bailian.env"


def read_bailian(path):
    if not path.is_file():
        raise BatchStop(f"还没有文件 {path}")
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        name, value = text.split("=", 1)
        values[name.strip()] = value.strip().strip('"').strip("'")
    key = values.get("LLM_API_KEY") or ""
    if not key:
        raise BatchStop(f"{path} 里还没有 LLM 对话 key")
    return key, values.get("LLM_BASE_URL") or LLM_BASE


def dialogue_config(key, base):
    """The existing client looks up two internal slots. Both carry this one Bailian key."""
    config = {}
    for prefix in ("LLM_HARD", "LLM_STANDARD"):
        config[prefix + "_API_KEY"] = key
        config[prefix + "_BASE_URL"] = base
        config[prefix + "_API_STYLE"] = "openai-compatible"
    return config


def live(modules, fixture, root, key_file):
    try:
        key, base = read_bailian(key_file)
    except BatchStop as exc:
        print(f"停：{exc}")
        print("在 LLM_API_KEY= 后面写上 Token Plan 的对话 key，保存即可。不要贴到对话里。")
        return 2
    from inves_cog.llm.transport import OpenAICompatibleTransport

    transport = OpenAICompatibleTransport(dialogue_config(key, base))
    install_normal_thinking()
    try:
        execute(modules, fixture, root, transport, workers=WORKERS)
    except BatchStop as exc:
        print(f"停：{exc}")
        return 3
    print("本批 19 次已落盘")
    return 0


def install_normal_thinking():
    """glm-5.3 cannot turn thinking off. low is its shallowest effort; the default is max."""
    from inves_cog.ingest.http import HTTPClient

    if getattr(HTTPClient.request, "_m8_normal_thinking", False):
        return
    original = HTTPClient.request

    def request(self, method, url, *, params=None, headers=None, json=None, limiter=None):
        if isinstance(json, dict) and json.get("model") == "glm-5.3":
            json = dict(json)
            json["enable_thinking"] = True
            json["reasoning_effort"] = "low"
        return original(self, method, url, params=params, headers=headers, json=json, limiter=limiter)

    request._m8_normal_thinking = True
    HTTPClient.request = request


def execute(modules, fixture, root, transport, workers=1):
    prepare_root(root)
    ledger = Ledger(root)
    try:
        rows = modules["case_payloads"](fixture)
        groups = claim_groups(modules, rows)
        extracted = {}
        for group in groups:
            raw = send(modules, ledger, transport, root, "claim_extraction", group["payload"], "1")
            accept_claims(modules, group["items"], raw)
            extracted[group["sha256"]] = raw
        frozen = freeze_candidates(modules, root, rows, extracted)
        dispatch_candidates(modules, ledger, transport, root, frozen, workers)
    finally:
        write_summary(root, ledger)


def dispatch_candidates(modules, ledger, transport, root, frozen, workers):
    jobs = [(item["payload"], str(slot)) for item in frozen for slot in range(1, RUNS + 1)]
    if workers <= 1:
        for payload, slot in jobs:
            send(modules, ledger, transport, root, "anomaly_candidates", payload, slot)
        return
    stop = threading.Event()
    errors = []

    def one(job):
        if stop.is_set():
            return
        try:
            send(modules, ledger, transport, root, "anomaly_candidates", job[0], job[1])
        except BatchStop as exc:
            stop.set()
            errors.append(exc)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, jobs))
    if errors:
        raise errors[0]


def prepare_root(root):
    root.mkdir(parents=True, exist_ok=True)
    marker = root / "batch.json"
    body = {"batch": BATCH, "code": CODE_PIN, "retries": 0, "http_cap": CAP}
    if marker.is_file():
        if json.loads(marker.read_text(encoding="utf-8")) != body:
            raise BatchStop("目录不是这一批")
        return
    if any(root.iterdir()):
        raise BatchStop("目录不是空的")
    marker.write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def accept_claims(modules, items, raw):
    requested = {item["info_id"] for item in items}
    try:
        parsed = modules["read_claims"](raw)
    except ValueError as exc:
        raise BatchStop("说法结构不合格，不生成候选") from exc
    if set(parsed) != requested:
        raise BatchStop("说法没有覆盖全部材料，不生成候选")


def freeze_candidates(modules, root, rows, extracted):
    frozen = []
    for row in rows:
        claim_sha = digest(modules["canonical_payload"], row["claim_payload"])
        attached = attach(modules, row["items"], extracted[claim_sha])
        payload = modules["candidate_payload"](row["anomaly"], attached, [])
        frozen.append(
            {
                "case_kind": row["case_kind"],
                "anomaly_id": row["anomaly"]["anomaly_id"],
                "sha256": digest(modules["canonical_payload"], payload),
                "claim_sha256": claim_sha,
                "runs": RUNS,
                "payload": payload,
            }
        )
    public = [{key: item[key] for key in item if key != "payload"} for item in frozen]
    path = root / "candidate-freeze.json"
    body = {"batch": BATCH, "candidates": public}
    if path.is_file() and json.loads(path.read_text(encoding="utf-8")) != body:
        raise BatchStop("候选哈希和已冻结的不一致")
    path.write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return frozen


def attach(modules, items, raw):
    parsed = modules["read_claims"](raw)
    return [modules["bind"](item, parsed.get(item["info_id"], [])) for item in items]


def send(modules, ledger, transport, root, task, payload, slot):
    sha = digest(modules["canonical_payload"], payload)
    path = recording_path(root, task, sha, slot)
    if path.is_file():
        return stored_result(path, task, sha)
    state = ledger.reserve(task, sha, slot, CAP)
    if state == "attempted":
        raise BatchStop(f"已尝试过且没有完整录音，不重试 {task} {sha[:12]}")
    if state == "full":
        raise BatchStop("已到 19 次上限")
    spec = modules["CallSpec"](**asdict(modules["registry"].resolve(task)), task=task)
    try:
        outcome = transport(spec, payload)
    except Exception as exc:
        write_json(path, {"task": task, "payload_sha256": sha, "slot": slot, "error": type(exc).__name__})
        raise BatchStop(f"{task} 失败 {type(exc).__name__}") from exc
    data, usage = split_outcome(outcome, modules["DialogueResult"])
    missing = usage_missing(modules["tokens"], usage)
    body = {
        "task": task,
        "payload_sha256": sha,
        "slot": slot,
        "batch": BATCH,
        "synthetic": False,
        "result": data,
        "usage": usage,
        "usage_missing": missing,
    }
    if task == "anomaly_candidates":
        body["prompt_version"] = PROMPT
        body["reasoning_effort"] = "low"
    else:
        body["prompt_version"] = payload["output"]["grounding_policy"]["version"]
    write_json(path, body)
    print(f"{task} {sha[:12]} slot {slot} 完成", flush=True)
    if missing:
        raise BatchStop(f"{task} 没有用量，停止后续调用")
    return data


def stored_result(path, task, sha):
    body = json.loads(path.read_text(encoding="utf-8"))
    if body.get("task") != task or body.get("payload_sha256") != sha:
        raise BatchStop("录音和载荷哈希不一致")
    if body.get("error") or body.get("usage_missing"):
        raise BatchStop("上次已停止，不重试也不继续")
    result = body.get("result")
    if not isinstance(result, dict):
        raise BatchStop("录音没有结果对象")
    return result


def split_outcome(outcome, dialogue_type):
    if isinstance(outcome, dialogue_type):
        if not isinstance(outcome.data, dict):
            raise BatchStop("结果不是对象")
        return outcome.data, outcome.usage
    if isinstance(outcome, dict):
        return outcome, None
    raise BatchStop("结果不是对象")


def usage_missing(tokens, usage):
    incoming, outgoing = tokens(usage)
    return incoming is None or outgoing is None


def recording_path(root, task, sha, slot):
    folder = root / task
    if task == "claim_extraction":
        return folder / f"{sha}.json"
    return folder / f"{sha}-run{slot}.json"


def write_json(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def write_summary(root, ledger):
    if not root.exists():
        return
    write_json(
        root / "summary.json",
        {"batch": BATCH, "http_attempts": ledger.count(), "cap": CAP, "retries": 0},
    )


class Ledger:
    def __init__(self, root):
        self.path = root / "attempts.jsonl"
        self.rows = []
        self._lock = threading.Lock()
        if self.path.is_file():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self.rows.append(json.loads(line))

    def count(self):
        with self._lock:
            return len(self.rows)

    def reserve(self, task, sha, slot, cap):
        with self._lock:
            if any(row["task"] == task and row["payload_sha256"] == sha and row["slot"] == slot for row in self.rows):
                return "attempted"
            if len(self.rows) >= cap:
                return "full"
            row = {"n": len(self.rows) + 1, "task": task, "payload_sha256": sha, "slot": slot}
            self.rows.append(row)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            return "go"


def self_check(modules, fixture):
    _expect_bailian_file()
    manifest = build_manifest(modules, fixture)
    _expect_prefixes(manifest)
    _expect_attached_hash_changes(modules, fixture)
    _expect_complete_batch(modules, fixture)
    _expect_http_failure_stops(modules, fixture)
    _expect_missing_usage_stops(modules, fixture)


def _expect_bailian_file():
    try:
        read_bailian(Path("/tmp/m8-v3-missing-bailian.env"))
    except BatchStop:
        pass
    else:
        raise BatchStop("缺文件没有拦住")
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "bailian.env"
        path.write_text("DASHSCOPE_API_KEY=embed-key\nLLM_API_KEY=\n", encoding="utf-8")
        try:
            read_bailian(path)
        except BatchStop:
            pass
        else:
            raise BatchStop("空 key 没有拦住")
        path.write_text(
            "\n".join(
                (
                    "DASHSCOPE_API_KEY=embed-key",
                    "DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1",
                    "LLM_API_KEY=sk-test",
                    "LLM_HARD_API_KEY=other",
                )
            )
            + "\n",
            encoding="utf-8",
        )
        key, base = read_bailian(path)
        config = dialogue_config(key, base)
        if key != "sk-test" or base != LLM_BASE:
            raise BatchStop("没有读到 LLM 对话 key")
        if config["LLM_HARD_API_KEY"] != "sk-test" or config["LLM_STANDARD_API_KEY"] != "sk-test":
            raise BatchStop("两个模型没有共用这一把 key")
        if "other" in config.values():
            raise BatchStop("读到了不该使用的 key")


def _expect_prefixes(manifest):
    if len(manifest["claims"]) != 4:
        raise BatchStop("说法不是 4 份")
    seen = {}
    for row in manifest["empty_claim_candidates_not_called"]:
        anomaly_id = row["anomaly_id"]
        if not row["sha256"].startswith(EMPTY_CANDIDATE_PREFIX[anomaly_id]):
            raise BatchStop(f"空说法候选哈希变了 {anomaly_id}")
        seen[anomaly_id] = True
    claim_by_anomaly = {}
    for row in manifest["claims"]:
        for anomaly_id in row["anomaly_ids"]:
            claim_by_anomaly[anomaly_id] = row["sha256"]
    if set(seen) != set(CLAIM_PREFIX) or set(claim_by_anomaly) != set(CLAIM_PREFIX):
        raise BatchStop("五个对象没有对齐")
    for anomaly_id, prefix in CLAIM_PREFIX.items():
        if not claim_by_anomaly[anomaly_id].startswith(prefix):
            raise BatchStop(f"说法哈希变了 {anomaly_id}")


def _expect_attached_hash_changes(modules, fixture):
    row = modules["case_payloads"](fixture)[0]
    raw = {
        "items": [
            {
                "info_id": item["info_id"],
                "claims": [{"subject": "供应商", "mechanism": "供给", "direction": "down"}],
            }
            for item in row["items"]
        ]
    }
    attached = attach(modules, row["items"], raw)
    filled = modules["candidate_payload"](row["anomaly"], attached, [])
    if digest(modules["canonical_payload"], filled) == digest(modules["canonical_payload"], row["candidate_payload"]):
        raise BatchStop("接上说法后候选哈希没有变化")


def _expect_complete_batch(modules, fixture):
    calls = []

    def transport(spec, payload):
        calls.append(spec.task)
        if spec.task == "claim_extraction":
            data = {"items": [{"info_id": item["info_id"], "claims": []} for item in payload["items"]]}
        else:
            data = {"candidates": []}
        return modules["DialogueResult"](data, {"prompt_tokens": 3, "completion_tokens": 4})

    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        execute(modules, fixture, root, transport)
        if len(calls) != CAP:
            raise BatchStop(f"应发送 19 次，实际 {len(calls)}")
        _expect_recordings(modules, fixture, root)
        execute(modules, fixture, root, transport)
        if len(calls) != CAP:
            raise BatchStop("重入又发送了请求")


def _expect_recordings(modules, fixture, root):
    files = list((root / "anomaly_candidates").glob("*.json"))
    if len(files) != 15:
        raise BatchStop(f"候选录音不是 15 份：{len(files)}")
    body = json.loads(files[0].read_text(encoding="utf-8"))
    if body.get("prompt_version") != PROMPT or body.get("synthetic") is not False:
        raise BatchStop("候选录音不能进入 v3 判定")
    row = modules["case_payloads"](fixture)[0]
    verdict = modules["judge_recording"](row["anomaly"], row["items"], body)
    if verdict.get("eligible") is not True or verdict.get("synthetic") is not False:
        raise BatchStop("判定器没有收下这份录音")
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    if summary["http_attempts"] != CAP:
        raise BatchStop("计数不是 19")


def _expect_http_failure_stops(modules, fixture):
    calls = []

    def transport(spec, payload):
        calls.append(1)
        raise TimeoutError("down")

    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        try:
            execute(modules, fixture, root, transport)
        except BatchStop:
            pass
        else:
            raise BatchStop("失败后没有停下")
        if len(calls) != 1 or (root / "candidate-freeze.json").exists():
            raise BatchStop("失败后仍继续发送")
        try:
            execute(modules, fixture, root, transport)
        except BatchStop:
            pass
        else:
            raise BatchStop("失败后重入没有停下")
        if len(calls) != 1:
            raise BatchStop("失败后又重试了")


def _expect_missing_usage_stops(modules, fixture):
    calls = []

    def transport(spec, payload):
        calls.append(1)
        data = {"items": [{"info_id": item["info_id"], "claims": []} for item in payload["items"]]}
        return modules["DialogueResult"](data, None)

    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        try:
            execute(modules, fixture, root, transport)
        except BatchStop:
            pass
        else:
            raise BatchStop("缺用量没有停下")
        if len(calls) != 1:
            raise BatchStop("缺用量后仍继续发送")
        try:
            execute(modules, fixture, root, transport)
        except BatchStop:
            pass
        else:
            raise BatchStop("缺用量后重入没有停下")
        if len(calls) != 1:
            raise BatchStop("缺用量后又发送了")


if __name__ == "__main__":
    raise SystemExit(main())
