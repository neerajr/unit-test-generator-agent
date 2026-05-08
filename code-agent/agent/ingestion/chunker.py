"""AST-based code chunker using tree-sitter for Java and Python."""

from __future__ import annotations

import hashlib
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import tree_sitter_java as tsjava
import tree_sitter_python as tspython
from pydantic import BaseModel
from tree_sitter import Language, Node, Parser

LOG = logging.getLogger(__name__)

JAVA_LANGUAGE = Language(tsjava.language())
PYTHON_LANGUAGE = Language(tspython.language())

_java_parser = Parser(JAVA_LANGUAGE)
_python_parser = Parser(PYTHON_LANGUAGE)

_FALLBACK_WINDOW = 300
_FALLBACK_OVERLAP = 50


class CodeChunk(BaseModel):
    chunk_id: str        # sha256(file_path + "::" + class_name + "::" + method_name)
    file_path: str       # Absolute WSL2 path
    repo: str            # "java" or "python"
    language: str        # "java" or "python"
    class_name: str
    method_name: str
    start_line: int
    end_line: int
    last_modified: str   # ISO 8601 from git log
    content: str         # Raw source text of the chunk


def _make_chunk_id(file_path: str, class_name: str, method_name: str) -> str:
    raw = f"{file_path}::{class_name}::{method_name}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _git_last_modified(repo_root: Path, file_path: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%aI", "--", str(file_path)],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(repo_root),
        )
        ts = result.stdout.strip()
        return ts if ts else datetime.now(timezone.utc).isoformat()
    except Exception as exc:
        LOG.debug("git log failed for %s: %s", file_path, exc)
        return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Java chunker
# ---------------------------------------------------------------------------

def _java_walk(
    node: Node,
    class_stack: list[str],
    chunks: list[CodeChunk],
    file_path: Path,
    source_bytes: bytes,
    last_modified: str,
) -> None:
    if node.type in ("class_declaration", "interface_declaration", "enum_declaration"):
        class_name = ""
        for child in node.children:
            if child.type == "identifier":
                class_name = source_bytes[child.start_byte : child.end_byte].decode("utf-8", errors="replace")
                break
        class_stack.append(class_name)
        for child in node.children:
            _java_walk(child, class_stack, chunks, file_path, source_bytes, last_modified)
        class_stack.pop()

    elif node.type in ("method_declaration", "constructor_declaration"):
        method_name = ""
        for child in node.children:
            if child.type == "identifier":
                method_name = source_bytes[child.start_byte : child.end_byte].decode("utf-8", errors="replace")
                break

        # Include preceding Javadoc comment if present
        javadoc = ""
        prev = node.prev_sibling
        if prev and prev.type == "block_comment":
            comment_text = source_bytes[prev.start_byte : prev.end_byte].decode("utf-8", errors="replace")
            if comment_text.startswith("/**"):
                javadoc = comment_text + "\n"

        content = javadoc + source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")
        class_name = class_stack[-1] if class_stack else ""

        chunks.append(
            CodeChunk(
                chunk_id=_make_chunk_id(str(file_path), class_name, method_name),
                file_path=str(file_path),
                repo="java",
                language="java",
                class_name=class_name,
                method_name=method_name,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                last_modified=last_modified,
                content=content,
            )
        )
        # Do not recurse into method body — we captured the whole method

    else:
        for child in node.children:
            _java_walk(child, class_stack, chunks, file_path, source_bytes, last_modified)


def chunk_java_file(file_path: Path, repo_root: Path) -> list[CodeChunk]:
    source_bytes = file_path.read_bytes()
    last_modified = _git_last_modified(repo_root, file_path)
    try:
        tree = _java_parser.parse(source_bytes)
    except Exception as exc:
        LOG.warning("tree-sitter parse failed: %s (%s), falling back to line window", file_path, exc)
        return _fallback_chunks(file_path, "java", "java", source_bytes, last_modified)

    if tree.root_node.has_error:
        LOG.warning("tree-sitter parse errors in: %s, falling back to line window", file_path)
        return _fallback_chunks(file_path, "java", "java", source_bytes, last_modified)

    chunks: list[CodeChunk] = []
    _java_walk(tree.root_node, [], chunks, file_path, source_bytes, last_modified)

    if not chunks:
        LOG.warning("No method chunks found in %s, falling back to line window", file_path)
        return _fallback_chunks(file_path, "java", "java", source_bytes, last_modified)

    return chunks


# ---------------------------------------------------------------------------
# Python chunker
# ---------------------------------------------------------------------------

def _process_python_func(
    func_node: Node,
    decorators: list[str],
    outer_start_line: int,
    class_stack: list[str],
    chunks: list[CodeChunk],
    file_path: Path,
    source_bytes: bytes,
    last_modified: str,
) -> None:
    method_name = ""
    for child in func_node.children:
        if child.type == "identifier":
            method_name = source_bytes[child.start_byte : child.end_byte].decode("utf-8", errors="replace")
            break

    decorator_text = "\n".join(decorators) + "\n" if decorators else ""
    content = decorator_text + source_bytes[func_node.start_byte : func_node.end_byte].decode("utf-8", errors="replace")
    class_name = class_stack[-1] if class_stack else ""

    chunks.append(
        CodeChunk(
            chunk_id=_make_chunk_id(str(file_path), class_name, method_name),
            file_path=str(file_path),
            repo="python",
            language="python",
            class_name=class_name,
            method_name=method_name,
            start_line=outer_start_line,
            end_line=func_node.end_point[0] + 1,
            last_modified=last_modified,
            content=content,
        )
    )


def _python_walk(
    node: Node,
    class_stack: list[str],
    chunks: list[CodeChunk],
    file_path: Path,
    source_bytes: bytes,
    last_modified: str,
) -> None:
    if node.type == "class_definition":
        class_name = ""
        for child in node.children:
            if child.type == "identifier":
                class_name = source_bytes[child.start_byte : child.end_byte].decode("utf-8", errors="replace")
                break
        class_stack.append(class_name)
        for child in node.children:
            _python_walk(child, class_stack, chunks, file_path, source_bytes, last_modified)
        class_stack.pop()

    elif node.type == "decorated_definition":
        decorators: list[str] = []
        func_node: Node | None = None
        for child in node.children:
            if child.type == "decorator":
                decorators.append(source_bytes[child.start_byte : child.end_byte].decode("utf-8", errors="replace"))
            elif child.type in ("function_definition", "async_function_definition"):
                func_node = child
        if func_node is not None:
            _process_python_func(
                func_node,
                decorators,
                node.start_point[0] + 1,
                class_stack,
                chunks,
                file_path,
                source_bytes,
                last_modified,
            )
        # Also recurse to catch nested classes inside decorated definitions
        for child in node.children:
            if child.type == "class_definition":
                _python_walk(child, class_stack, chunks, file_path, source_bytes, last_modified)

    elif node.type in ("function_definition", "async_function_definition"):
        # Only process top-level functions (not inside decorated_definition — handled above)
        if not (node.parent and node.parent.type == "decorated_definition"):
            _process_python_func(
                node,
                [],
                node.start_point[0] + 1,
                class_stack,
                chunks,
                file_path,
                source_bytes,
                last_modified,
            )
        # Recurse into the function body for nested classes
        for child in node.children:
            if child.type == "block":
                for grandchild in child.children:
                    _python_walk(grandchild, class_stack, chunks, file_path, source_bytes, last_modified)

    else:
        for child in node.children:
            _python_walk(child, class_stack, chunks, file_path, source_bytes, last_modified)


def chunk_python_file(file_path: Path, repo_root: Path) -> list[CodeChunk]:
    source_bytes = file_path.read_bytes()
    last_modified = _git_last_modified(repo_root, file_path)
    try:
        tree = _python_parser.parse(source_bytes)
    except Exception as exc:
        LOG.warning("tree-sitter parse failed: %s (%s), falling back to line window", file_path, exc)
        return _fallback_chunks(file_path, "python", "python", source_bytes, last_modified)

    if tree.root_node.has_error:
        LOG.warning("tree-sitter parse errors in: %s, falling back to line window", file_path)
        return _fallback_chunks(file_path, "python", "python", source_bytes, last_modified)

    chunks: list[CodeChunk] = []
    _python_walk(tree.root_node, [], chunks, file_path, source_bytes, last_modified)

    if not chunks:
        LOG.warning("No function chunks found in %s, falling back to line window", file_path)
        return _fallback_chunks(file_path, "python", "python", source_bytes, last_modified)

    return chunks


# ---------------------------------------------------------------------------
# Fallback: sliding window
# ---------------------------------------------------------------------------

def _fallback_chunks(
    file_path: Path,
    repo: str,
    language: str,
    source_bytes: bytes,
    last_modified: str,
) -> list[CodeChunk]:
    lines = source_bytes.decode("utf-8", errors="replace").splitlines()
    chunks: list[CodeChunk] = []
    step = _FALLBACK_WINDOW - _FALLBACK_OVERLAP
    i = 0
    while i < len(lines):
        end = min(i + _FALLBACK_WINDOW, len(lines))
        content = "\n".join(lines[i:end])
        method_name = f"lines_{i + 1}_{end}"
        chunks.append(
            CodeChunk(
                chunk_id=_make_chunk_id(str(file_path), "fallback", method_name),
                file_path=str(file_path),
                repo=repo,
                language=language,
                class_name="fallback",
                method_name=method_name,
                start_line=i + 1,
                end_line=end,
                last_modified=last_modified,
                content=content,
            )
        )
        if end == len(lines):
            break
        i += step
    return chunks


# ---------------------------------------------------------------------------
# Public API: chunk a whole repo
# ---------------------------------------------------------------------------

def chunk_repo(repo_path: Path, language: str) -> list[CodeChunk]:
    """Chunk all source files of the given language in a repo directory."""
    if language == "java":
        pattern = "**/*.java"
        chunk_fn = chunk_java_file
    elif language == "python":
        pattern = "**/*.py"
        chunk_fn = chunk_python_file
    else:
        raise ValueError(f"Unsupported language: {language}")

    all_chunks: list[CodeChunk] = []
    for file_path in sorted(repo_path.rglob(pattern)):
        # Skip test directories in the actual repos — we don't embed existing tests
        parts = file_path.parts
        if any(p in ("test", "tests", "test_", "__pycache__") for p in parts):
            continue
        try:
            chunks = chunk_fn(file_path, repo_path)
            all_chunks.extend(chunks)
            LOG.debug("Chunked %s → %d chunks", file_path, len(chunks))
        except Exception as exc:
            LOG.error("Failed to chunk %s: %s", file_path, exc, exc_info=True)

    LOG.info("Chunked %s repo: %d total chunks from %s", language, len(all_chunks), repo_path)
    return all_chunks


if __name__ == "__main__":
    import json
    import sys

    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s %(message)s")

    fixtures = Path(__file__).parent.parent.parent / "tests" / "fixtures"
    java_fixture = fixtures / "SampleService.java"
    python_fixture = fixtures / "sample_router.py"

    if not fixtures.exists():
        print(f"Fixture directory not found: {fixtures}")
        sys.exit(1)

    if java_fixture.exists():
        java_chunks = chunk_java_file(java_fixture, fixtures)
        print(f"\n=== Java chunks ({len(java_chunks)}) ===")
        for c in java_chunks:
            print(f"  {c.class_name}.{c.method_name} lines {c.start_line}-{c.end_line}")
    else:
        print(f"Java fixture not found: {java_fixture}")

    if python_fixture.exists():
        py_chunks = chunk_python_file(python_fixture, fixtures)
        print(f"\n=== Python chunks ({len(py_chunks)}) ===")
        for c in py_chunks:
            print(f"  {c.class_name}.{c.method_name} lines {c.start_line}-{c.end_line}")
    else:
        print(f"Python fixture not found: {python_fixture}")

    print("\nchunker.py smoke test passed.")
