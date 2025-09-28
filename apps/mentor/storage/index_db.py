"""
SQLite FTS5 database interface for the AI Mentor system.

This module provides the core database schema and operations for indexing
and searching code symbols, files, relationships, and metadata.
"""

import sqlite3
from pathlib import Path
from datetime import datetime
import logging
from typing import Dict, Any, Optional, Set
import re
from apps.core.utils_new.sql_security import SecureSQL

logger = logging.getLogger(__name__)


class MentorIndexDB:
    """SQLite database with FTS5 for code indexing and search."""

    # SECURITY: Define allowed table names as class constant
    ALLOWED_TABLES: Set[str] = {
        'files', 'symbols', 'relations', 'urls', 'models', 'graphql', 'tests'
    }

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the mentor index database.

        Args:
            db_path: Path to the SQLite database file. If None, uses default location.
        """
        if db_path is None:
            # Default to .mentor/index.sqlite in project root
            from django.conf import settings
            project_root = Path(settings.BASE_DIR)
            mentor_dir = project_root / '.mentor'
            mentor_dir.mkdir(exist_ok=True)
            db_path = mentor_dir / 'index.sqlite'

        self.db_path = str(db_path)
        self.conn = None
        self._ensure_database()

    def connect(self):
        """Establish database connection with FTS5 enabled."""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            # Enable FTS5 if available
            try:
                self.conn.execute("SELECT fts5(?)", ("test",))
            except sqlite3.OperationalError:
                logger.warning("FTS5 not available, falling back to basic search")
        return self.conn

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def _ensure_database(self):
        """Create database schema if it doesn't exist."""
        conn = self.connect()

        # Create core tables
        self._create_core_tables(conn)
        self._create_fts_tables(conn)
        self._create_indexes(conn)

        conn.commit()

    def _create_core_tables(self, conn: sqlite3.Connection):
        """Create the core database tables."""

        # Files table - tracks all indexed files
        conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY,
                path TEXT UNIQUE NOT NULL,
                sha TEXT NOT NULL,
                mtime INTEGER NOT NULL,
                size INTEGER NOT NULL,
                lang TEXT,
                is_test BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Symbols table - all code symbols (classes, functions, variables)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS symbols (
                id INTEGER PRIMARY KEY,
                file_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                kind TEXT NOT NULL,  -- 'class', 'function', 'method', 'variable', etc.
                span_start INTEGER,  -- Line number where symbol starts
                span_end INTEGER,    -- Line number where symbol ends
                parents TEXT,        -- JSON array of parent symbols
                decorators TEXT,     -- JSON array of decorators
                doc TEXT,           -- Docstring
                signature TEXT,     -- Function signature
                complexity INTEGER DEFAULT 0,  -- Cyclomatic complexity
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (file_id) REFERENCES files (id) ON DELETE CASCADE
            )
        """)

        # Relations table - tracks relationships between symbols
        conn.execute("""
            CREATE TABLE IF NOT EXISTS relations (
                id INTEGER PRIMARY KEY,
                src_symbol_id INTEGER NOT NULL,
                dst_symbol_id INTEGER NOT NULL,
                kind TEXT NOT NULL,  -- 'import', 'call', 'inherit', 'serialize', etc.
                line_number INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (src_symbol_id) REFERENCES symbols (id) ON DELETE CASCADE,
                FOREIGN KEY (dst_symbol_id) REFERENCES symbols (id) ON DELETE CASCADE,
                UNIQUE(src_symbol_id, dst_symbol_id, kind)
            )
        """)

        # URLs table - Django URL patterns
        conn.execute("""
            CREATE TABLE IF NOT EXISTS urls (
                id INTEGER PRIMARY KEY,
                route TEXT NOT NULL,
                name TEXT,
                view TEXT NOT NULL,
                methods TEXT,        -- JSON array of HTTP methods
                permissions TEXT,    -- JSON array of required permissions
                app_label TEXT,
                file_path TEXT,
                line_number INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Models table - Django models
        conn.execute("""
            CREATE TABLE IF NOT EXISTS models (
                id INTEGER PRIMARY KEY,
                app_label TEXT NOT NULL,
                model_name TEXT NOT NULL,
                fields_json TEXT,    -- JSON description of fields
                db_table TEXT,
                file_path TEXT,
                line_number INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(app_label, model_name)
            )
        """)

        # GraphQL table - GraphQL types and resolvers
        conn.execute("""
            CREATE TABLE IF NOT EXISTS graphql (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                kind TEXT NOT NULL,  -- 'query', 'mutation', 'type', 'resolver'
                type_json TEXT,      -- JSON description of type
                file_path TEXT,
                line_number INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tests table - test discovery and metadata
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tests (
                id INTEGER PRIMARY KEY,
                node TEXT NOT NULL,      -- pytest node ID
                file_path TEXT NOT NULL,
                class_name TEXT,
                method_name TEXT,
                markers TEXT,            -- JSON array of pytest markers
                owns_modules_json TEXT,  -- JSON array of modules this test covers
                execution_time REAL DEFAULT 0.0,
                success_rate REAL DEFAULT 1.0,  -- Flakiness tracking
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Coverage table - test coverage data
        conn.execute("""
            CREATE TABLE IF NOT EXISTS coverage (
                id INTEGER PRIMARY KEY,
                test_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                lines_json TEXT,         -- JSON array of covered line numbers
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_id) REFERENCES tests (id) ON DELETE CASCADE
            )
        """)

        # Index metadata table - tracks indexing state
        conn.execute("""
            CREATE TABLE IF NOT EXISTS index_metadata (
                id INTEGER PRIMARY KEY,
                key TEXT UNIQUE NOT NULL,
                value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def _create_fts_tables(self, conn: sqlite3.Connection):
        """Create FTS5 virtual tables for full-text search."""
        try:
            # FTS table for file contents
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
                    file_id UNINDEXED,
                    path,
                    content,
                    content='',
                    content_rowid='file_id'
                )
            """)

            # FTS table for symbols and docstrings
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS symbols_fts USING fts5(
                    symbol_id UNINDEXED,
                    name,
                    doc,
                    signature,
                    content='',
                    content_rowid='symbol_id'
                )
            """)
        except sqlite3.OperationalError as e:
            logger.warning(f"Could not create FTS5 tables: {e}")

    def _create_indexes(self, conn: sqlite3.Connection):
        """Create database indexes for performance."""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_files_path ON files (path)",
            "CREATE INDEX IF NOT EXISTS idx_files_sha ON files (sha)",
            "CREATE INDEX IF NOT EXISTS idx_files_mtime ON files (mtime)",
            "CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols (name)",
            "CREATE INDEX IF NOT EXISTS idx_symbols_kind ON symbols (kind)",
            "CREATE INDEX IF NOT EXISTS idx_symbols_file_id ON symbols (file_id)",
            "CREATE INDEX IF NOT EXISTS idx_relations_src ON relations (src_symbol_id)",
            "CREATE INDEX IF NOT EXISTS idx_relations_dst ON relations (dst_symbol_id)",
            "CREATE INDEX IF NOT EXISTS idx_relations_kind ON relations (kind)",
            "CREATE INDEX IF NOT EXISTS idx_urls_route ON urls (route)",
            "CREATE INDEX IF NOT EXISTS idx_urls_view ON urls (view)",
            "CREATE INDEX IF NOT EXISTS idx_models_app_model ON models (app_label, model_name)",
            "CREATE INDEX IF NOT EXISTS idx_tests_file_path ON tests (file_path)",
            "CREATE INDEX IF NOT EXISTS idx_coverage_test_file ON coverage (test_id, file_path)",
        ]

        for index_sql in indexes:
            conn.execute(index_sql)

    def get_metadata(self, key: str) -> Optional[str]:
        """Get metadata value by key."""
        conn = self.connect()
        cursor = conn.execute(
            "SELECT value FROM index_metadata WHERE key = ?", (key,)
        )
        row = cursor.fetchone()
        return row['value'] if row else None

    def set_metadata(self, key: str, value: str):
        """Set metadata value."""
        conn = self.connect()
        conn.execute("""
            INSERT OR REPLACE INTO index_metadata (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (key, value))
        conn.commit()

    def get_indexed_commit(self) -> Optional[str]:
        """Get the commit SHA that was last indexed."""
        return self.get_metadata('indexed_commit_sha')

    def set_indexed_commit(self, commit_sha: str):
        """Set the commit SHA that was indexed."""
        self.set_metadata('indexed_commit_sha', commit_sha)
        self.set_metadata('index_updated_at', datetime.now().isoformat())

    def is_file_indexed(self, file_path: str, file_sha: str) -> bool:
        """Check if a file is already indexed with the current content."""
        conn = self.connect()
        cursor = conn.execute(
            "SELECT 1 FROM files WHERE path = ? AND sha = ?",
            (file_path, file_sha)
        )
        return cursor.fetchone() is not None

    def add_file(self, file_path: str, file_sha: str, mtime: int, size: int,
                 lang: str = None, is_test: bool = False) -> int:
        """Add or update a file record."""
        conn = self.connect()
        cursor = conn.execute("""
            INSERT OR REPLACE INTO files (path, sha, mtime, size, lang, is_test, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (file_path, file_sha, mtime, size, lang, is_test))
        conn.commit()
        return cursor.lastrowid

    def search_files(self, query: str, limit: int = 50) -> List[Dict]:
        """Search files using FTS5."""
        conn = self.connect()
        try:
            cursor = conn.execute("""
                SELECT f.path, f.lang, f.is_test, f.mtime
                FROM files_fts fts
                JOIN files f ON f.id = fts.file_id
                WHERE files_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, limit))
        except sqlite3.OperationalError:
            # Fallback to LIKE search if FTS5 is not available
            cursor = conn.execute("""
                SELECT path, lang, is_test, mtime
                FROM files
                WHERE path LIKE ?
                ORDER BY path
                LIMIT ?
            """, (f"%{query}%", limit))

        return [dict(row) for row in cursor.fetchall()]

    def get_file_symbols(self, file_path: str) -> List[Dict]:
        """Get all symbols in a file."""
        conn = self.connect()
        cursor = conn.execute("""
            SELECT s.name, s.kind, s.span_start, s.span_end, s.doc, s.signature
            FROM symbols s
            JOIN files f ON f.id = s.file_id
            WHERE f.path = ?
            ORDER BY s.span_start
        """, (file_path,))
        return [dict(row) for row in cursor.fetchall()]

    def cleanup_old_files(self, days: int = 30):
        """Remove files that haven't been updated in N days."""
        conn = self.connect()
        cutoff_time = datetime.now().timestamp() - (days * 24 * 3600)
        cursor = conn.execute(
            "DELETE FROM files WHERE mtime < ?", (cutoff_time,)
        )
        deleted = cursor.rowcount
        conn.commit()
        logger.info(f"Cleaned up {deleted} old file records")
        return deleted

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        conn = self.connect()
        stats = {}

        # SECURITY FIX: Use SecureSQL utilities for validated table names
        for table in self.ALLOWED_TABLES:
            try:
                # Use SecureSQL utility for validation and query building
                safe_query = SecureSQL.build_safe_sqlite_count_query(table, self.ALLOWED_TABLES)

                # Execute secure query
                cursor = conn.execute(safe_query)
                stats[table] = cursor.fetchone()['count']

            except (ValueError, Exception) as e:
                logger.error(f"Security violation prevented unauthorized table access: {e}")
                stats[table] = 0  # Safe fallback

        # Get last indexed commit and time
        stats['indexed_commit'] = self.get_indexed_commit()
        stats['index_updated_at'] = self.get_metadata('index_updated_at')

        return stats

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()