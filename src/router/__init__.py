"""Query router.

Claude Sonnet 4.6 few-shot classifier. Input: the user question. Output:
`{route: stats | prose | hybrid, reasoning: str}`. Dispatches to one of
the three retrieval modules.
"""
