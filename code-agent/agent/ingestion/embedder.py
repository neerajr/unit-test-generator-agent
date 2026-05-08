"""Ollama embedding wrapper — batches chunks and calls nomic-embed-text."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from langchain_ollama import OllamaEmbeddings

from agent.ingestion.chunker import CodeChunk

if TYPE_CHECKING:
    from agent.config import AgentConfig

LOG = logging.getLogger(__name__)

_BATCH_SIZE = 32


class ChunkEmbedder:
    def __init__(self, config: AgentConfig) -> None:
        self._embeddings = OllamaEmbeddings(
            model=config.llm.embed_model,
            base_url=config.llm.base_url,
        )

    def embed(self, chunks: list[CodeChunk]) -> list[tuple[CodeChunk, list[float]]]:
        """Embed a list of chunks in batches. Returns (chunk, vector) pairs."""
        results: list[tuple[CodeChunk, list[float]]] = []

        for batch_start in range(0, len(chunks), _BATCH_SIZE):
            batch = chunks[batch_start : batch_start + _BATCH_SIZE]
            texts = [c.content for c in batch]
            try:
                vectors = self._embeddings.embed_documents(texts)
            except Exception as exc:
                LOG.error(
                    "Embedding batch %d-%d failed: %s",
                    batch_start,
                    batch_start + len(batch),
                    exc,
                    exc_info=True,
                )
                raise

            for chunk, vector in zip(batch, vectors):
                results.append((chunk, vector))

            LOG.debug(
                "Embedded batch %d-%d (%d chunks)",
                batch_start,
                batch_start + len(batch),
                len(batch),
            )

        LOG.info("Embedded %d chunks total.", len(results))
        return results

    def embed_query(self, text: str) -> list[float]:
        return self._embeddings.embed_query(text)


if __name__ == "__main__":
    import sys
    import logging as _logging
    from pathlib import Path

    _logging.basicConfig(level=_logging.INFO, format="%(levelname)s %(message)s")

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from agent.config import get_config, validate_runtime
    from agent.ingestion.chunker import chunk_python_file

    cfg = get_config()
    validate_runtime(cfg, skip_repo_check=True)

    fixtures = Path(__file__).parent.parent.parent / "tests" / "fixtures"
    sample = fixtures / "sample_router.py"
    if not sample.exists():
        print(f"Fixture not found: {sample}")
        sys.exit(1)

    chunks = chunk_python_file(sample, fixtures)[:2]
    embedder = ChunkEmbedder(cfg)
    pairs = embedder.embed(chunks)
    for chunk, vec in pairs:
        print(f"  {chunk.method_name}: vector dim={len(vec)}, first3={vec[:3]}")
    print("embedder.py smoke test passed.")
