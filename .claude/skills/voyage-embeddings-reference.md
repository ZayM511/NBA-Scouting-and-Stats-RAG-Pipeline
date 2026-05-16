# Voyage Embeddings — Reference

Use Voyage AI for embeddings. The Python SDK is `voyageai`. Get an API key at voyageai.com and set it as `VOYAGE_API_KEY`.

## Which model

| Model | Dimensions | Context | Use when |
|---|---|---|---|
| `voyage-3-large` | 1024 | 32K tokens | **This project's default.** General-purpose, strongest non-domain model. |
| `voyage-3` | 1024 | 32K tokens | If cost matters more than accuracy. Roughly 75% the quality of `voyage-3-large` at lower price. |
| `voyage-3-lite` | 512 | 32K tokens | Fast and cheap. For dev and smoke tests. |
| `voyage-finance-2` | 1024 | 32K tokens | Domain-tuned for finance. Not relevant for the NBA project; mentioned for completeness. |
| `voyage-code-3` | 1024 | 32K tokens | Code-specific. Useful if you ever index `src/`. |

The NBA project uses **`voyage-3-large`** for the articles corpus. Generic sports prose doesn't have a domain-tuned Voyage model; the general one is the right call.

## Free tier (as of 2026)

- General-purpose models (`voyage-3-large`, `voyage-3`, `voyage-3-lite`): **200M tokens** lifetime.
- Domain models (`voyage-finance-2`, `voyage-code-3`): **50M tokens** lifetime per model.

For this project, ingesting ~1000 articles at ~2K tokens each is 2M tokens — about 1% of the general free tier. Headroom is plenty.

## API call shape

```python
import voyageai

client = voyageai.Client()  # reads VOYAGE_API_KEY from env

result = client.embed(
    texts=["chunk 1 text", "chunk 2 text"],
    model="voyage-3-large",
    input_type="document",  # "document" for ingestion, "query" at retrieve time
)
vectors: list[list[float]] = result.embeddings
```

Two important details:

1. **`input_type` matters.** Voyage models are asymmetric: documents and queries get embedded slightly differently to improve retrieval. Use `"document"` at ingest, `"query"` at retrieval. Forgetting to switch costs roughly 5–10% recall.
2. **Batching.** Up to 128 texts per call, up to 320K total tokens. Larger batches are cheaper per token and dramatically faster.

## Batching pattern

```python
def embed_chunks(client, chunks: list[str], model="voyage-3-large", batch_size=128):
    out = []
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        # token-aware safety: cap at 320K tokens per call
        result = client.embed(texts=batch, model=model, input_type="document")
        out.extend(result.embeddings)
    return out
```

Add token counting upstream if any individual chunk could exceed 32K tokens (the per-text context). For the NBA project's 400-token chunks, this is never the case.

## Retry pattern

The Voyage API is reliable but transient 429s and 5xxs happen. Wrap calls with exponential backoff:

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import voyageai

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((voyageai.error.RateLimitError, voyageai.error.APIError)),
)
def embed_with_retry(client, batch, model, input_type):
    return client.embed(texts=batch, model=model, input_type=input_type)
```

## Reranker

Voyage also ships rerankers (`rerank-2`, `rerank-2-lite`), but this project uses **Cohere Rerank 3.5** instead because it has slightly better latency at the top of the retrieval set. Either is defensible; the choice is a project preference, not a quality verdict.

## Cost (as of 2026)

- `voyage-3-large`: $0.18 per 1M tokens
- `voyage-3`: $0.06 per 1M tokens
- `voyage-3-lite`: $0.02 per 1M tokens

Embedding 1000 articles at 2K tokens each = 2M tokens = $0.36 with `voyage-3-large`. One-time cost.

## Anti-patterns

- **Calling the API one chunk at a time.** Batch by 128.
- **Mixing input types.** Always set `input_type="document"` for ingest and `"query"` at retrieval.
- **Embedding raw chunks without contextual-retrieval prefix.** See `chunking-strategies.md` — prepending the source/date/player context before embedding is one of the largest free wins.
- **Storing embeddings without a content hash.** Add a `content_sha256` column so you can detect when the underlying article text changed and the embedding is stale.
- **Embedding with `voyage-3-lite` for production.** It's a dev model. Use `voyage-3-large` for the real corpus.
