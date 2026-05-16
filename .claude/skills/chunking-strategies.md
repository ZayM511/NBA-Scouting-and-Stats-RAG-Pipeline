# Chunking Strategies — 2026 Reference

Consult this skill before writing any chunking code. Chunking is one of the highest-leverage decisions in a RAG pipeline; the wrong choice cannot be saved by better embeddings or rerankers.

## The 2026 cheat sheet

| Document type | Recommended strategy | Why |
|---|---|---|
| Generic prose (news, articles, Reddit) | **Recursive, 400-512 tokens, 10-20% overlap** | The 2026 default. Best balance of precision and context. |
| Multi-topic prose with clear sections | Semantic chunking with a 200-token minimum floor | Semantic alone produces tiny fragments (43-token average); the floor fixes it. |
| Structured documents (10-Ks, earnings calls) | Structure-aware (by section / speaker turn) | The structure is a free signal; ignoring it is wasteful. |
| Code | AST-based (tree-sitter) | Function and class boundaries are the natural unit. |
| Short focused docs (FAQs, tickets) | No chunking, embed the whole doc | Chunking small docs hurts retrieval more than it helps. |
| Tables and numeric data | Don't embed — query SQL instead (route) | Vector search is the wrong tool for numeric questions. |

## What this project does

**Articles, Reddit posts, scouting newsletters: recursive chunking, 400 tokens, 15% overlap.**

This is the 2026 default. Recursive chunking splits on the most natural separator first (paragraphs), then sentences, then words, then characters as a last resort. The 400-token target preserves enough context for synthesis while keeping each chunk semantically focused. The 15% overlap stops a single idea from being split across two chunks with no anchor.

**Top-30 authored summaries: no chunking, embed the whole 500-word summary.**

These are short focused docs by definition. Splitting a 500-word summary loses the structure that makes the summary useful. Stored as a single chunk with `article_type = 'authored_summary'` and a higher retrieval prior.

**Stats: never chunk.** They live in `players`, `games`, `player_game_stats`, and `play_by_play`. Queries go through text-to-SQL.

## Layered upgrades

Once the base strategy is in place, three upgrades give big wins for low effort. Worth knowing both for the project and for interviews.

### Contextual retrieval (Anthropic, 2024)

Before embedding each chunk, prepend a short context line. Format used in this project:

```
Article from {source}, {date}, about {comma_separated_player_names}: {chunk_text}
```

Concrete example:

```
Article from The Athletic, 2026-04-12, about Victor Wembanyama, Chet Holmgren:
Wembanyama's defensive instincts continue to set him apart. In Sunday's loss
to Denver, he recorded six blocks and altered an estimated twelve more shots
at the rim, according to Second Spectrum tracking...
```

Expect a 35–50% recall lift on hard queries. One-time embedding cost; permanent benefit. Pay attention to this on the eval set — it's often the single largest accuracy improvement available.

### Late chunking (Jina AI, 2024)

Embed the long document first with a long-context model, then split the embeddings rather than the text. Each chunk vector retains awareness of its neighbors. Often a one-parameter change with the right model. Significant nDCG improvement.

Not the default for this project because `voyage-3-large` is not optimized for late chunking, but worth experimenting with if recall plateaus.

### Parent-child / small-to-large

Embed small chunks (precise retrieval) but return the surrounding larger chunk (better context for synthesis). 10-15% accuracy gain.

For this project, the "parent" could be the full article paragraph (500-700 tokens) and the "child" the 400-token recursive chunk. Worth adding once the base pipeline is shipping.

### Rich metadata on every chunk

Metadata pre-filtering is the cheapest accuracy gain in RAG. Every chunk in `articles_chunks` carries:

- `player_ids INT[]` — GIN-indexed. Filter to a player before vector search.
- `team TEXT`
- `date DATE` — for time-aware retrieval, especially playoff freshness.
- `source TEXT` — The Athletic, ESPN, The Ringer, r/nba, etc.
- `article_type TEXT` — `news`, `scouting`, `reddit_thread`, `authored_summary`.

Filtering on `player_ids` first turns a 200K-chunk vector search into a 50-chunk vector search. That's roughly a 4000x speedup at the access-path level, and a meaningful accuracy lift because irrelevant chunks can't sneak into the top-K.

## Decision tree (in code form)

```
def pick_strategy(doc):
    if doc.kind == "stats_table":
        return "do not embed, route to SQL"
    if doc.kind == "code":
        return "AST-based (tree-sitter)"
    if doc.kind == "earnings_call" or doc.kind == "transcript_with_speakers":
        return "structure-aware on speaker turns, 200-token floor"
    if doc.token_count < 200:
        return "embed whole doc, no chunking"
    if doc.has_explicit_sections and doc.token_count > 2000:
        return "semantic with 200-token floor"
    # default: generic prose
    return "recursive 400 tokens, 15% overlap, contextual retrieval prepended"
```

## Anti-patterns

- **Fixed-character chunking.** Splits mid-sentence and mid-word; loses meaning. Use recursive splitting that respects paragraph and sentence boundaries.
- **Embedding tables as text.** Numbers in prose form lose their relational structure. Route numeric questions to SQL.
- **Skipping overlap.** Zero overlap means a single idea spanning a chunk boundary appears in neither chunk's embedding context. 10-20% is the standard band.
- **Embedding without metadata.** Storing the raw vector with no `source`, `date`, `author` etc. forces every query to scan the whole corpus. Pre-filtering on metadata is the cheapest win.

## Research links

- Anthropic, "Contextual Retrieval," 2024.
- Jina AI, "Late Chunking in Long-Context Embedding Models," 2024.
- LlamaIndex, "Parent-Child Document Retriever" pattern.
- Pinecone, "Chunking Strategies for LLM Applications," 2024 — useful for the recursive-vs-semantic comparison numbers.
