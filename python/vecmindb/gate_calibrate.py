"""Gate calibration sweep for `memory.search_min_score`.

Runs the labeled query set (tests/fixtures/search_gate_eval.json or a
custom JSONL/JSON file) against a live server, reading RAW scores via
the per-call `min_score: 0` override, then computes precision/recall at
every candidate threshold and prints the recommendation.

Usage:
    python -m vecmindb.gate_calibrate \
        --server http://10.3.0.18:5520 --api-key <KEY> \
        [--labels tests/fixtures/search_gate_eval.json] \
        [--target-precision 0.9]

The evaluator prefers the threshold that maximizes recall while keeping
precision >= --target-precision (default 0.9): for a memory product,
leaking noise is worse than missing a marginal hit.
"""

import argparse
import json
import re
import sys
import urllib.request
from typing import Dict, List, Optional, Tuple


def search(server: str, api_key: str, query: str, top_k: int) -> str:
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "search_memory",
                "arguments": {"query": query, "top_k": top_k, "min_score": 0},
            },
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        server.rstrip("/") + "/api/v1/mcp/message",
        data=body,
        headers={"content-type": "application/json", "x-api-key": api_key},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read().decode("utf-8"))
    return d["result"]["content"][0]["text"]


def scores_of(report: str) -> List[float]:
    if "No relevant memory" in report:
        return []
    return [float(s) for s in re.findall(r"Score: ([\d.]+)", report)]


def load_labels(path: str) -> List[Tuple[str, str]]:
    with open(path, encoding="utf-8") as f:
        if path.endswith(".json"):
            data = json.load(f)
            items = data["queries"] if isinstance(data, dict) else data
        else:  # JSONL
            items = [json.loads(line) for line in f if line.strip()]
    return [(it["query"], it["expected"]) for it in items]


def sweep(
    server: str, api_key: str, labels: List[Tuple[str, str]]
) -> Dict[float, Tuple[float, float, int, int]]:
    """Collects raw scores once per query, then evaluates every threshold."""
    observed: List[Tuple[bool, List[float]]] = []
    for query, expected in labels:
        report = search(server, api_key, query, top_k=5)
        observed.append((expected == "hit", scores_of(report)))

    results: Dict[float, Tuple[float, float, int, int]] = {}
    for th in [round(0.50 + 0.02 * i, 2) for i in range(24)]:  # 0.50..0.96
        tp = fp = fn = 0
        for is_hit, scores in observed:
            cleared = any(s >= th for s in scores)
            if is_hit:
                if cleared:
                    tp += 1
                else:
                    fn += 1
            elif cleared:
                fp += 1
        precision = tp / (tp + fp) if (tp + fp) else 1.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        results[th] = (precision, recall, tp, fn)
    return results


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="gate_calibrate")
    p.add_argument("--server", required=True)
    p.add_argument("--api-key", required=True)
    p.add_argument("--labels", default="tests/fixtures/search_gate_eval.json")
    p.add_argument("--target-precision", type=float, default=0.9)
    args = p.parse_args(argv)

    labels = load_labels(args.labels)
    print(f"[eval] {len(labels)} queries against {args.server}")
    results = sweep(args.server, args.api_key, labels)

    print(f"{'th':>5} {'prec':>6} {'recall':>7} {'tp':>3} {'fn':>3}")
    best_th, best_recall = None, -1.0
    for th in sorted(results):
        precision, recall, tp, fn = results[th]
        print(f"{th:>5.2f} {precision:>6.3f} {recall:>7.3f} {tp:>3} {fn:>3}")
        if precision >= args.target_precision and recall > best_recall:
            best_th, best_recall = th, recall

    if best_th is not None:
        print(
            f"\n[recommend] search_min_score = {best_th:.2f} "
            f"(max recall at precision >= {args.target_precision:.2f}; "
            f"recall={best_recall:.3f})"
        )
    else:
        print("\n[recommend] no threshold satisfies the precision target")
    return 0


if __name__ == "__main__":
    sys.exit(main())
