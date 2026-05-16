"""Prose retrieval path: hybrid BM25 + dense vector + Cohere Rerank 3.5.

Pre-filters by `player_ids` GIN when the question mentions a specific
player; otherwise scans the corpus. Returns top 5-10 chunks for synthesis.
"""
