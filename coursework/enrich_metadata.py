import json
import time
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

BENCHMARK_FILE = os.path.join(HERE, "input_payload.json")
OUTPUT_FILE    = os.path.join(HERE, "output_payload_sample.json")
RECALL_K       = 3

def recall_at_k(expected: list, retrieved: list, k: int):
    """Fraction of expected dishes found in the top-k retrieved dishes."""
    if not expected:
        return None
    top_k = retrieved[:k]
    hits = sum(
        1 for exp in expected
        if any(exp.lower() in ret.lower() or ret.lower() in exp.lower()
               for ret in top_k)
    )
    return round(hits / len(expected), 4)

def run_evaluation():
    print("=" * 60)
    print("  South Asian Culinary RAG — Benchmark Evaluation")
    print("=" * 60)

    with open(BENCHMARK_FILE, "r", encoding="utf-8") as f:
        benchmark = json.load(f)

    print("\n[1/3] Loading LangGraph pipeline… (This will download the model if missing)")
    from assistant_core import get_assistant_response
    print("      Pipeline loaded.\n")

    results       = []
    latencies     = []
    recall_scores = []
    intent_correct = 0
    intent_total   = 0

    print("[2/3] Running queries…\n")
    for item in benchmark:
        qid        = item.get("query_id", item.get("id", "Unknown"))
        query      = item["question"] # Matches our generated benchmark schema
        expected   = [item.get("target_dish")] if item.get("target_dish") else []
        exp_intent = item.get("expected_intent", "")

        print(f"  [{qid}] {query}")

        t0       = time.time()
        response = get_assistant_response(query, chat_history=[])
        latency  = round(time.time() - t0, 3)

        # Robust extraction based on our final assistant_core output
        retrieved_dishes = response.get("selected_dishes", [])
        if not retrieved_dishes:
            # Fallback just in case it's using an older chunk format
            chunks = response.get("chunks", [])
            retrieved_dishes = [c.get("dish_name", "") for c in chunks if isinstance(c, dict)]
            
        predicted_intent = response.get("intent", "UNKNOWN")
        answer           = response.get("answer", "")

        r_at_k = recall_at_k(expected, retrieved_dishes, RECALL_K)
        if r_at_k is not None:
            recall_scores.append(r_at_k)

        intent_match = (predicted_intent == exp_intent)
        if exp_intent:
            intent_total += 1
            if intent_match:
                intent_correct += 1

        latencies.append(latency)

        results.append({
            "id":               qid,
            "query":            query,
            "expected_intent":  exp_intent,
            "predicted_intent": predicted_intent,
            "intent_correct":   intent_match,
            "expected_dishes":  expected,
            "retrieved_dishes": retrieved_dishes,
            f"recall@{RECALL_K}": r_at_k,
            "latency_seconds":  latency,
        })

        print(f"         intent={predicted_intent} | "
              f"recall@{RECALL_K}={r_at_k} | latency={latency}s")

    avg_latency     = round(sum(latencies) / len(latencies), 3) if latencies else 0
    avg_recall      = round(sum(recall_scores) / len(recall_scores), 4) if recall_scores else 0
    intent_accuracy = round(intent_correct / intent_total, 4) if intent_total else 0

    summary = {
        "total_queries":           len(benchmark),
        f"mean_recall@{RECALL_K}": avg_recall,
        "intent_accuracy":         intent_accuracy,
        "mean_latency_seconds":    avg_latency,
        "min_latency_seconds":     round(min(latencies), 3) if latencies else 0,
        "max_latency_seconds":     round(max(latencies), 3) if latencies else 0,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"evaluation_summary": summary, "per_query_results": results},
                  f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("[3/3] Evaluation complete. Summary:")
    print(f"      Total queries   : {summary['total_queries']}")
    print(f"      Mean Recall@{RECALL_K}  : {avg_recall}")
    print(f"      Intent Accuracy : {intent_accuracy}")
    print(f"      Mean Latency    : {avg_latency}s")
    print(f"\n  Results saved → {OUTPUT_FILE}")
    print("=" * 60)

if __name__ == "__main__":
    run_evaluation()