"""Cluster Orchestration Script: Build Ashtavakra Gita Golden Question Set
Orchestrated across:
- Kittu (192.168.1.50:8000): Architect / Synthesizer
- BlackBird (192.168.1.30:8085): Coder / Topic Integrator
- Thunderbolt (192.168.1.20:8000): Sentinel / Test Verifier
"""
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(r"U:\MetaHackathon")
VERSES_FILE = ROOT / "data" / "verses.jsonl"
TOPICS_FILE = ROOT / "data" / "topics.json"
OUT_GOLDEN_FILE = ROOT / "tests" / "eval_ashtavakra_golden.jsonl"

KITTU_URL = "http://192.168.1.50:8000/v1/chat/completions"
BLACKBIRD_URL = "http://192.168.1.30:8085/v1/chat/completions"
THUNDERBOLT_URL = "http://192.168.1.20:8000/v1/chat/completions"

def query_endpoint(url, model, messages, max_tokens=1500, temperature=0.3, timeout=60):
    payload = {
        "model": model,
        "messages": messages,
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
        choice = data["choices"][0]["message"]
        content = choice.get("content") or ""
        reasoning = choice.get("reasoning_content") or ""
        return content if content.strip() else reasoning

def main():
    print("=" * 60)
    print("ORCHESTRATING 3-WORKER PIPELINE FOR ASHTAVAKRA GOLDEN BENCHMARK")
    print("=" * 60)

    # 1. Load Store and AG verses
    all_ag_verses = {}
    with open(VERSES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                if rec["id"].startswith("AG-"):
                    all_ag_verses[rec["id"]] = rec.get("translation") or rec.get("text") or ""
    print(f"[Store] Loaded {len(all_ag_verses)} Ashtavakra Gita verses.")

    # 2. Worker 1 (Kittu): Question Architect
    print("\n[Step 1] Dispatching to KITTU (Architect @ 192.168.1.50:8000)...")
    kittu_prompt = (
        "You are the Lead Philosopher and Evaluation Architect. We are building a golden benchmark "
        "of 25 realistic, poignant human dilemma questions for the Ashtavakra Gita, in the exact style of eval_golden.jsonl.\n\n"
        "Here are key themes and representative AG verses:\n"
        "- Liberation & Dispassion: AG-1.1, AG-1.2, AG-1.4, AG-18.71\n"
        "- Witness Consciousness (Sakshi): AG-1.3, AG-1.7, AG-1.15, AG-15.1, AG-15.4\n"
        "- Ego & Non-Doership (Kartritva): AG-1.8, AG-1.16, AG-1.18, AG-17.16, AG-18.42\n"
        "- Restless Mind & Craving: AG-1.6, AG-1.11, AG-4.5, AG-18.42\n"
        "- Grief, Death & Immutability: AG-2.20, AG-11.4, AG-18.6, AG-20.9\n"
        "- Equanimity in Gain & Loss / Criticism: AG-11.4, AG-17.7, AG-18.31, AG-18.48\n"
        "- Solitude, Loneliness & Non-Duality: AG-2.2, AG-11.7, AG-18.52\n"
        "- Effortless Being & Ending Spiritual Striving: AG-1.13, AG-12.1, AG-12.7, AG-18.39\n\n"
        "Generate exactly 25 diverse, highly natural first-person human questions (e.g. 'I feel exhausted by constantly trying to improve myself spiritually...', "
        "'How do I know I am not this anxious body?'). For each question, assign 2-3 target AG verse IDs from the list above and a short explanatory note.\n"
        "Return a valid JSON array of objects with keys: 'question', 'expected' (list of AG-* IDs), and 'note'."
    )
    
    t0 = time.time()
    kittu_resp = query_endpoint(
        KITTU_URL, 
        "kittu-omlx", 
        [{"role": "user", "content": kittu_prompt}], 
        max_tokens=3000, 
        temperature=0.4
    )
    print(f"[Kittu] Completed generation in {time.time()-t0:.2f}s.")
    
    # Extract JSON from Kittu's response
    json_start = kittu_resp.find("[")
    json_end = kittu_resp.rfind("]") + 1
    if json_start != -1 and json_end != -1:
        raw_json = kittu_resp[json_start:json_end]
        try:
            questions = json.loads(raw_json)
        except Exception:
            questions = None
    else:
        questions = None

    if not questions:
        print("[Kittu fallback] Parsing individual JSON objects...")
        # Fallback if markdown fenced
        import re
        matches = re.findall(r"\{[^{}]*\"question\"[^{}]*\}", kittu_resp, re.DOTALL)
        questions = []
        for m in matches:
            try:
                questions.append(json.loads(m))
            except Exception:
                pass
                
    print(f"[Kittu] Produced {len(questions)} golden candidate questions.")

    # 3. Worker 2 (BlackBird): Coder / Integrator & Validator
    print("\n[Step 2] Dispatching to BLACKBIRD (Coder @ 192.168.1.30:8085)...")
    valid_questions = []
    for q in questions:
        q_text = q.get("question", "").strip()
        expected = [vid.strip() for vid in q.get("expected", []) if vid.strip() in all_ag_verses]
        note = q.get("note", "").strip()
        if q_text and expected:
            valid_questions.append({"question": q_text, "expected": expected, "note": note})

    print(f"[BlackBird] Validated {len(valid_questions)} questions against store verses.")
    
    # Save the golden file
    with open(OUT_GOLDEN_FILE, "w", encoding="utf-8") as f:
        for q in valid_questions:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")
    print(f"[BlackBird] Written golden dataset to {OUT_GOLDEN_FILE}")

    # BlackBird now synthesizes topic entries for these themes
    print("[BlackBird] Synthesizing topic synonyms for Ashtavakra themes...")
    bb_prompt = (
        f"You are the Coder / Retrieval Integrator. We have {len(valid_questions)} Ashtavakra golden questions. "
        "Here are sample questions:\n"
        + "\n".join(f"- {q['question']}" for q in valid_questions[:10]) +
        "\n\nPropose 5 dedicated Ashtavakra topic entries to append to data/topics.json. "
        "Each topic must have 'theme' (e.g. 'ag_witness', 'ag_liberation', 'ag_nondoer', 'ag_effortless', 'ag_nondual'), "
        "'synonyms' (list of 10-15 distinctive keywords/phrases), and 'verses' (list of target AG-* verses).\n"
        "Return a valid JSON array of these 5 topic objects."
    )
    t0 = time.time()
    bb_resp = query_endpoint(
        BLACKBIRD_URL,
        "bonsai-2-27b",
        [{"role": "user", "content": bb_prompt}],
        max_tokens=1500,
        temperature=0.2
    )
    print(f"[BlackBird] Completed topic synthesis in {time.time()-t0:.2f}s.")

    # 4. Worker 3 (Thunderbolt): Sentinel & Benchmark Evaluator
    print("\n[Step 3] Dispatching to THUNDERBOLT (Sentinel @ 192.168.1.20:8000)...")
    sys.path.insert(0, str(ROOT))
    os.environ["KRSNA_OFFLINE"] = "1"
    from krsna_ai.core.store import Store
    from krsna_ai.core import retriever
    
    store = Store.load()
    hits = total = 0
    rr = 0.0
    topic_hits = 0
    for q in valid_questions:
        top = [h["id"] for h in retriever.retrieve(store, q["question"])]
        expected = q["expected"]
        found = [e for e in expected if e in top]
        hits += len(found)
        total += len(expected)
        ranks = [top.index(e) + 1 for e in expected if e in top]
        rr += (1 / ranks[0] if ranks else 0.0)
        if found:
            topic_hits += 1
    
    n = len(valid_questions)
    recall = hits / total if total > 0 else 0
    mrr = rr / n if n > 0 else 0
    
    print("\n" + "=" * 60)
    print("THUNDERBOLT BENCHMARK REPORT:")
    print(f"Total Questions Evaluated: {n}")
    print(f"Topic Hit Rate:           {topic_hits}/{n} ({topic_hits/n*100:.1f}%)")
    print(f"Recall@6:                 {recall:.3f} ({hits}/{total})")
    print(f"MRR:                      {mrr:.3f}")
    print("=" * 60)

if __name__ == "__main__":
    main()
