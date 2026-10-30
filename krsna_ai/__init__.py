"""Krishna AI assistant — grounded in Bhagavad-gītā As It Is (Macmillan 1972)
and The Uddhava-gītā (Śrīmad-Bhāgavatam Canto 11).

Architecture: offline ingestion -> verses.jsonl + NumPy embedding index ->
retriever -> grounded LLM prompt -> citation checker -> chat UI / CLI.
"""
