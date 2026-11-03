import asyncio
import sys
sys.path.insert(0, ".")
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from krsna_ai.core.store import Store
from krsna_ai.core.engine import answer_question
from krsna_ai.core import citations

store = Store.load()
question = "I feel exhausted by constantly trying to improve myself spiritually. How do I stop this struggle?"

print("Question:", question)
res = asyncio.run(answer_question(store, question))

print("\n--- GENERATED ANSWER ---")
print(res["answer"])

retrieved_ids = [r["id"] for r in res["retrieved"]]
report = citations.check(res["answer"], store, retrieved_ids)
print("\n--- CITATION VERIFICATION REPORT ---")
print("All Pass (ok):", report.get("ok"))
for k, v in report.items():
    if k != "ok":
        print(f"  {k}: {v}")
