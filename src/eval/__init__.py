"""Eval set + Braintrust integration.

30 test queries, stratified 10/10/10 across stats / prose / hybrid routes.
Tracks router accuracy, SQL correctness, retrieval recall@5 and MRR, plus
an LLM-as-judge rubric on the final synthesized answer.

New eval cases must be reviewed by the `rag-eval-reviewer` agent before
landing.
"""
