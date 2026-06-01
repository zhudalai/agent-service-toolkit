"""
Document Ingestion Pipeline for RAG Agent.

Converts PDF/TXT/Markdown documents into vectorized chunks stored in ChromaDB,
making them searchable by the RAG agent's database_search tool.

Usage:
    python -m scripts.ingest_documents --input-dir ./data/documents
    python -m scripts.ingest_documents --file ./data/handbook.pdf
    python -m scripts.ingest_documents --input-dir ./data/documents --reset
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add project root to path so we can import from src/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

load_dotenv()

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────
CHROMA_DB_DIR = "./chroma_db"
CHUNK_SIZE = 512
CHUNK_OVERLAP = 64
SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown"}


def get_embedding_function():
    """Initialize the embedding function, preferring Azure OpenAI if configured."""
    from core.settings import settings

    if settings.AZURE_OPENAI_API_KEY:
        from langchain_openai import AzureOpenAIEmbeddings

        logger.info("Using Azure OpenAI for embeddings")
        return AzureOpenAIEmbeddings(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            model="text-embedding-3-small",
        )
    elif settings.OPENROUTER_API_KEY:
        from langchain_openai import OpenAIEmbeddings

        logger.info("Using OpenRouter for embeddings (OpenAI-compatible)")
        return OpenAIEmbeddings(
            openai_api_base="https://openrouter.ai/api/v1",
            api_key=settings.OPENROUTER_API_KEY,
            model="text-embedding-3-small",
        )
    else:
        from langchain_openai import OpenAIEmbeddings

        logger.info("Using OpenAI for embeddings")
        return OpenAIEmbeddings()


def load_documents(input_path: str) -> list:
    """Load documents from a file or directory."""
    from langchain_community.document_loaders import (
        DirectoryLoader,
        PyPDFLoader,
        TextLoader,
    )
    from langchain_core.documents import Document

    path = Path(input_path)
    documents: list[Document] = []

    if path.is_file():
        if path.suffix.lower() == ".pdf":
            loader = PyPDFLoader(str(path))
        elif path.suffix.lower() in (".txt", ".md", ".markdown"):
            loader = TextLoader(str(path), encoding="utf-8")
        else:
            logger.warning(f"Unsupported file type: {path.suffix}")
            return []
        documents = loader.load()
        logger.info(f"Loaded {len(documents)} page(s) from {path.name}")

    elif path.is_dir():
        for ext in SUPPORTED_EXTENSIONS:
            pattern = f"**/*{ext}"
            if ext == ".pdf":
                loader_cls = PyPDFLoader
            else:
                loader_cls = lambda fp, **kw: TextLoader(fp, encoding="utf-8")

            try:
                loader = DirectoryLoader(
                    str(path),
                    glob=pattern,
                    loader_cls=loader_cls,
                    show_progress=True,
                )
                docs = loader.load()
                documents.extend(docs)
                logger.info(f"  {ext}: {len(docs)} document(s)")
            except Exception as e:
                logger.warning(f"Error loading {ext} files: {e}")

    else:
        logger.error(f"Path not found: {input_path}")

    return documents


def split_documents(documents: list) -> list:
    """Split documents into chunks for vectorization."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    logger.info(f"Split into {len(chunks)} chunks (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    return chunks


def ingest_to_chroma(chunks: list, reset: bool = False) -> None:
    """Store document chunks in ChromaDB."""
    from langchain_chroma import Chroma

    embedding_fn = get_embedding_function()

    if reset and os.path.exists(CHROMA_DB_DIR):
        import shutil
        shutil.rmtree(CHROMA_DB_DIR)
        logger.info(f"Reset: removed existing {CHROMA_DB_DIR}")

    if os.path.exists(CHROMA_DB_DIR):
        # Append to existing DB
        db = Chroma(persist_directory=CHROMA_DB_DIR, embedding_function=embedding_fn)
        db.add_documents(chunks)
        logger.info(f"Added {len(chunks)} chunks to existing DB ({CHROMA_DB_DIR})")
    else:
        # Create new DB
        db = Chroma.from_documents(
            documents=chunks,
            embedding=embedding_fn,
            persist_directory=CHROMA_DB_DIR,
        )
        logger.info(f"Created new DB with {len(chunks)} chunks ({CHROMA_DB_DIR})")

    # Verify
    count = db._collection.count()
    logger.info(f"Total chunks in DB: {count}")


def main():
    parser = argparse.ArgumentParser(
        description="Ingest documents into ChromaDB for RAG agent"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input-dir", type=str, help="Directory containing documents")
    group.add_argument("--file", type=str, help="Single file to ingest")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset the vector database before ingesting",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug logging"
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    input_path = args.file or args.input_dir
    logger.info(f"Starting document ingestion from: {input_path}")

    # 1. Load
    documents = load_documents(input_path)
    if not documents:
        logger.error("No documents loaded. Exiting.")
        sys.exit(1)

    logger.info(f"Total documents loaded: {len(documents)}")

    # 2. Split
    chunks = split_documents(documents)

    # 3. Ingest
    ingest_to_chroma(chunks, reset=args.reset)

    logger.info("✅ Ingestion complete!")


if __name__ == "__main__":
    main()
