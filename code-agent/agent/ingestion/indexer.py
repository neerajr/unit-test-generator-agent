"""ChromaDB indexer — upserts code chunks, handles git-diff delta re-indexing."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import chromadb
from chromadb.config import Settings

from agent.ingestion.chunker import CodeChunk, chunk_repo
from agent.ingestion.embedder import ChunkEmbedder

if TYPE_CHECKING:
    from agent.config import AgentConfig

LOG = logging.getLogger(__name__)

_COLLECTION_JAVA = "java_code"
_COLLECTION_PYTHON = "python_code"


class CodeIndexer:
    def __init__(self, config: AgentConfig) -> None:
        self._config = config
        chroma_path = config.rag.chroma_path
        chroma_path.mkdir(parents=True, exist_ok=True)

        try:
            self._client = chromadb.PersistentClient(
                path=str(chroma_path),
                settings=Settings(anonymized_telemetry=False, allow_reset=True),
            )
        except Exception as exc:
            LOG.error("ChromaDB initialization failed at %s: %s", chroma_path, exc)
            raise RuntimeError(f"ChromaDB initialization failed: {exc}") from exc

        self._java_col = self._client.get_or_create_collection(
            name=_COLLECTION_JAVA,
            metadata={"hnsw:space": "cosine"},
        )
        self._python_col = self._client.get_or_create_collection(
            name=_COLLECTION_PYTHON,
            metadata={"hnsw:space": "cosine"},
        )
        self._embedder = ChunkEmbedder(config)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def index_repo(self, repo_path: Path, language: str, dry_run: bool = False) -> int:
        """Index or delta-update a repo. Returns number of chunks upserted."""
        collection = self._java_col if language == "java" else self._python_col

        changed_files = self._git_changed_files(repo_path)
        if changed_files is None:
            LOG.info("No git history or first run — full re-index for %s", repo_path)
            return self._full_index(repo_path, language, collection, dry_run)

        if not changed_files:
            LOG.info("No changed files in last commit for %s — skipping re-index", repo_path)
            return 0

        ext = ".java" if language == "java" else ".py"
        relevant = [f for f in changed_files if f.endswith(ext)]
        if not relevant:
            LOG.info("No %s files changed — skipping re-index", ext)
            return 0

        LOG.info("Delta re-index: %d changed %s files", len(relevant), ext)
        return self._delta_index(repo_path, language, collection, relevant, dry_run)

    def query(self, language: str, query_text: str, top_k: int | None = None) -> list[CodeChunk]:
        """Query the collection by semantic similarity. Returns list of CodeChunk."""
        collection = self._java_col if language == "java" else self._python_col
        k = top_k or self._config.rag.top_k

        query_vec = self._embedder.embed_query(query_text)
        results = collection.query(
            query_embeddings=[query_vec],
            n_results=min(k, collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        chunks: list[CodeChunk] = []
        if not results["ids"] or not results["ids"][0]:
            return chunks

        for doc, meta, distance in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            similarity = 1.0 - distance  # cosine distance → similarity
            if similarity < self._config.rag.similarity_threshold:
                continue
            chunks.append(
                CodeChunk(
                    chunk_id=meta["chunk_id"],
                    file_path=meta["file_path"],
                    repo=meta["repo"],
                    language=meta["language"],
                    class_name=meta["class_name"],
                    method_name=meta["method_name"],
                    start_line=meta["start_line"],
                    end_line=meta["end_line"],
                    last_modified=meta["last_modified"],
                    content=doc,
                )
            )
        return chunks

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _full_index(
        self,
        repo_path: Path,
        language: str,
        collection: chromadb.Collection,
        dry_run: bool,
    ) -> int:
        chunks = chunk_repo(repo_path, language)
        return self._upsert_chunks(chunks, collection, dry_run)

    def _delta_index(
        self,
        repo_path: Path,
        language: str,
        collection: chromadb.Collection,
        changed_files: list[str],
        dry_run: bool,
    ) -> int:
        all_new_chunks: list[CodeChunk] = []

        for rel_path in changed_files:
            abs_path = repo_path / rel_path
            if not abs_path.exists():
                # File was deleted — remove its chunks
                if not dry_run:
                    self._delete_by_file(collection, str(abs_path))
                LOG.debug("Deleted chunks for removed file: %s", abs_path)
                continue

            from agent.ingestion.chunker import chunk_java_file, chunk_python_file

            try:
                if language == "java":
                    new_chunks = chunk_java_file(abs_path, repo_path)
                else:
                    new_chunks = chunk_python_file(abs_path, repo_path)
            except Exception as exc:
                LOG.error("Failed to chunk %s: %s", abs_path, exc, exc_info=True)
                continue

            if not dry_run:
                self._delete_by_file(collection, str(abs_path))
            all_new_chunks.extend(new_chunks)

        return self._upsert_chunks(all_new_chunks, collection, dry_run)

    def _delete_by_file(self, collection: chromadb.Collection, file_path: str) -> None:
        try:
            collection.delete(where={"file_path": file_path})
        except Exception as exc:
            LOG.warning("Failed to delete chunks for %s: %s", file_path, exc)

    def _upsert_chunks(
        self,
        chunks: list[CodeChunk],
        collection: chromadb.Collection,
        dry_run: bool,
    ) -> int:
        if not chunks:
            return 0

        if dry_run:
            LOG.info("[dry-run] Would upsert %d chunks", len(chunks))
            return len(chunks)

        pairs = self._embedder.embed(chunks)

        ids = [c.chunk_id for c, _ in pairs]
        documents = [c.content for c, _ in pairs]
        embeddings = [vec for _, vec in pairs]
        metadatas = [
            {
                "chunk_id": c.chunk_id,
                "file_path": c.file_path,
                "repo": c.repo,
                "language": c.language,
                "class_name": c.class_name,
                "method_name": c.method_name,
                "start_line": c.start_line,
                "end_line": c.end_line,
                "last_modified": c.last_modified,
            }
            for c, _ in pairs
        ]

        collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        LOG.info("Upserted %d chunks into collection '%s'.", len(chunks), collection.name)
        return len(chunks)

    @staticmethod
    def _git_changed_files(repo_path: Path) -> list[str] | None:
        """Returns list of changed file paths relative to repo root, or None for full re-index."""
        try:
            result = subprocess.run(
                ["git", "diff", "HEAD~1", "--name-only"],
                capture_output=True,
                text=True,
                timeout=15,
                cwd=str(repo_path),
            )
            if result.returncode != 0:
                # Likely a repo with only one commit
                return None
            files = [f.strip() for f in result.stdout.splitlines() if f.strip()]
            return files
        except subprocess.TimeoutExpired:
            LOG.warning("git diff timed out for %s — falling back to full re-index", repo_path)
            return None
        except Exception as exc:
            LOG.warning("git diff failed for %s: %s — falling back to full re-index", repo_path, exc)
            return None


if __name__ == "__main__":
    import sys
    import logging as _logging
    from pathlib import Path

    _logging.basicConfig(level=_logging.INFO, format="%(levelname)s %(message)s")

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from agent.config import get_config, validate_runtime

    cfg = get_config()
    validate_runtime(cfg, skip_repo_check=True)

    fixtures = Path(__file__).parent.parent.parent / "tests" / "fixtures"
    indexer = CodeIndexer(cfg)

    print("Indexing fixture Python files...")
    count = indexer.index_repo(fixtures, "python", dry_run=False)
    print(f"Upserted {count} chunks.")

    print("Querying for 'route handler item'...")
    results = indexer.query("python", "route handler item", top_k=3)
    for r in results:
        print(f"  {r.class_name}.{r.method_name} ({r.file_path}:{r.start_line})")

    print("indexer.py smoke test passed.")
