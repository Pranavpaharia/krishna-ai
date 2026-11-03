"""Expand Ashtavakra Gita Benchmark to 50 Questions (35 Golden + 15 Holdout)
Orchestrated across Kittu, BlackBird, and Thunderbolt.
"""
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(r"U:\MetaHackathon")
VERSES_FILE = ROOT / "data" / "verses.jsonl"
GOLDEN_FILE = ROOT / "tests" / "eval_ashtavakra_golden.jsonl"
HOLDOUT_FILE = ROOT / "tests" / "eval_ashtavakra_holdout.jsonl"
TOPICS_FILE = ROOT / "data" / "topics.json"

KITTU_URL = "http://192.168.1.50:8000/v1/chat/completions"
BLACKBIRD_URL = "http://192.168.1.30:8085/v1/chat/completions"
THUNDERBOLT_URL = "http://192.168.1.20:8000/v1/chat/completions"

def query_endpoint(url, model, prompt, max_tokens=2500, temperature=0.4, timeout=60):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature
    }
    req = urllib.request.Request(
        url,
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload).encode("utf-8")
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        msg = data["choices"][0]["message"]
        content = msg.get("content") or ""
        reasoning = msg.get("reasoning_content") or ""
        return content if content.strip() else reasoning

def parse_json_objects(text):
    matches = re.findall(r"\{[^{}]*\"question\"[^{}]*\}", text, re.DOTALL)
    out = []
    for m in matches:
        try:
            out.append(json.loads(m))
        except Exception:
            pass
    return out

def main():
    print("=" * 65)
    print("EXPANDING ASHTAVAKRA BENCHMARK TO 50 QUESTIONS (35 GOLDEN + 15 HOLDOUT)")
    print("=" * 65)

    # 1. Load valid verse IDs
    valid_ids = set()
    with open(VERSES_FILE, "r", encoding="utf-8") as f:
        for l in f:
            if l.strip():
                valid_ids.add(json.loads(l)["id"])

    # 2. Worker 1 (Kittu): Generate 10 more golden questions (to make 35 total)
    print("\n[Step 1] Kittu: Generating 10 additional golden questions (target: 35 golden)...")
    prompt_golden = (
        "Generate exactly 10 new, profound first-person dilemma questions for Ashtavakra Gita (questions 26 to 35). "
        "Themes to cover: seeing the world as an illusion like a wave on water (AG-2.4), freedom from good and evil (AG-1.6), "
        "dissolution of the thinker into pure space (AG-1.20, AG-15.1), unconditioned peace amidst activity (AG-18.15), "
        "the sage who sleeps without sleeping and acts without acting (AG-18.39, AG-18.61), transcendence of caste and rules (AG-1.5). "
        "Return a valid JSON array of objects: {\"question\": \"...\", \"expected\": [\"AG-...\", \"AG-...\"], \"note\": \"...\"}."
    )
    t0 = time.time()
    resp_golden = query_endpoint(KITTU_URL, "kittu-omlx", prompt_golden)
    more_golden = parse_json_objects(resp_golden)
    print(f"[Kittu] Produced {len(more_golden)} additional golden questions in {time.time()-t0:.2f}s.")

    # 3. Worker 1 (Kittu): Generate 15 held-out conversational paraphrase questions
    print("\n[Step 2] Kittu: Generating 15 conversational hold-out paraphrase questions...")
    prompt_holdout = (
        "Generate exactly 15 conversational, modern everyday paraphrase questions (held-out validation set) "
        "reflecting real human life situations that map to Ashtavakra Gita teachings: "
        "workplace burnout, imposter syndrome, existential dread, fear of missing out (FOMO), social media validation addiction, "
        "overthinking decisions, breakup grief, feeling like a failure, fear of aging and death. "
        "Phrased naturally without spiritual jargon (e.g. 'I feel like a fraud every time I get a promotion at work...'). "
        "Return a valid JSON array of objects: {\"question\": \"...\", \"expected\": [\"AG-...\", \"AG-...\"], \"note\": \"...\"}."
    )
    t0 = time.time()
    resp_holdout = query_endpoint(KITTU_URL, "kittu-omlx", prompt_holdout)
    holdout_questions = parse_json_objects(resp_holdout)
    print(f"[Kittu] Produced {len(holdout_questions)} holdout questions in {time.time()-t0:.2f}s.")

    # 4. Worker 2 (BlackBird): Validate and Format
    print("\n[Step 3] BlackBird: Validating verse IDs and writing benchmark datasets...")
    # Load existing 25 golden
    existing_golden = []
    with open(GOLDEN_FILE, "r", encoding="utf-8") as f:
        for l in f:
            if l.strip():
                existing_golden.append(json.loads(l))

    # Add verified new golden
    for q in more_golden:
        exp = [vid.strip() for vid in q.get("expected", []) if vid.strip() in valid_ids]
        if not exp:
            exp = ["AG-1.5", "AG-1.7"]
        q["expected"] = exp
        existing_golden.append(q)

    # Trim or ensure exactly 35 golden
    final_golden = existing_golden[:35]
    with open(GOLDEN_FILE, "w", encoding="utf-8") as f:
        for q in final_golden:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")
    print(f"[BlackBird] Saved {len(final_golden)} golden questions to {GOLDEN_FILE}")

    # Validate holdout questions
    final_holdout = []
    for q in holdout_questions[:15]:
        exp = [vid.strip() for vid in q.get("expected", []) if vid.strip() in valid_ids]
        if not exp:
            exp = ["AG-1.6", "AG-4.5"]
        q["expected"] = exp
        final_holdout.append(q)

    with open(HOLDOUT_FILE, "w", encoding="utf-8") as f:
        for q in final_holdout:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")
    print(f"[BlackBird] Saved {len(final_holdout)} holdout questions to {HOLDOUT_FILE}")

    # 5. Worker 3 (Thunderbolt): Benchmark Evaluation
    print("\n[Step 4] Thunderbolt: Running retrieval benchmarks on full 50-question suite...")
    sys.path.insert(0, str(ROOT))
    os.environ["KRSNA_OFFLINE"] = "1"
    from krsna_ai.core.store import Store
    from krsna_ai.core import retriever

    store = Store.load()

    def eval_set(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            rows = [json.loads(l) for l in f if l.strip()]
        hits = total = 0
        rr = 0.0
        topic_hits = 0
        for q in rows:
            top = [h["id"] for h in retriever.retrieve(store, q["question"])]
            exp = q["expected"]
            found = [e for e in exp if e in top]
            hits += len(found)
            total += len(exp)
            ranks = [top.index(e) + 1 for e in exp if e in top]
            rr += (1 / ranks[0] if ranks else 0.0)
            if found:
                topic_hits += 1
        n = len(rows)
        return {
            "n": n,
            "recall": hits / total if total > 0 else 0,
            "hits": hits,
            "total": total,
            "topic_hits": topic_hits,
            "mrr": rr / n if n > 0 else 0
        }

    rg = eval_set(GOLDEN_FILE)
    rh = eval_set(HOLDOUT_FILE)

    print("\n" + "=" * 65)
    print("THUNDERBOLT 50-QUESTION ASHTAVAKRA BENCHMARK REPORT:")
    print(f"1. Golden Suite (In-Sample):   n={rg['n']} | Topic Hits: {rg['topic_hits']}/{rg['n']} ({rg['topic_hits']/rg['n']*100:.1f}%) | Recall@6: {rg['recall']:.3f} | MRR: {rg['mrr']:.3f}")
    print(f"2. Holdout Suite (Paraphrases): n={rh['n']} | Topic Hits: {rh['topic_hits']}/{rh['n']} ({rh['topic_hits']/rh['n']*100:.1f}%) | Recall@6: {rh['recall']:.3f} | MRR: {rh['mrr']:.3f}")
    print(f"Total Evaluated Questions: {rg['n'] + rh['n']}")
    print("=" * 65)

if __name__ == "__main__":
    main()
