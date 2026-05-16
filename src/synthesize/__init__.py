"""Answer synthesis with Claude Opus 4.7 (cascade falls back to Sonnet 4.6).

Input: the user question + retrieved stats and/or chunks.
Output: a cited answer plus a tool-trace object the UI can render in the
visible tool-use sidebar.

Every factual claim in the output must carry a citation; the synthesis
prompt enforces this and the eval set checks it.
"""
