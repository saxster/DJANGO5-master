"""
Base extractor class for ontology extraction.

Provides common functionality for all specialized extractors.
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BaseExtractor(ABC):
    """
    Abstract base class for ontology extractors.

    Provides common functionality for file handling, error reporting,
    and metadata structure.
    """

    def __init__(self, root_path: Optional[Path] = None):
        """
        Initialize the extractor.

        Args:
            root_path: Root directory to search for files (default: project root)
        """
        self.root_path = root_path or Path.cwd()
        self.errors: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []

    @abstractmethod
    def extract(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Extract ontology metadata from a file.

        Args:
            file_path: Path to the file to analyze

        Returns:
            List of metadata dictionaries
        """
        pass

    @abstractmethod
    def can_handle(self, file_path: Path) -> bool:
        """
        Check if this extractor can handle the given file.

        Args:
            file_path: Path to check

        Returns:
            True if this extractor can process the file
        """
        pass

    def extract_directory(
        self, directory: Path, recursive: bool = True, file_pattern: str = "*.py"
    ) -> List[Dict[str, Any]]:
        """
        Extract metadata from all matching files in a directory.

        Args:
            directory: Directory to search
            recursive: Whether to search subdirectories
            file_pattern: Glob pattern for files to process

        Returns:
            List of all extracted metadata
        """
        all_metadata = []
        search_pattern = f"**/{file_pattern}" if recursive else file_pattern

        for file_path in directory.glob(search_pattern):
            if file_path.is_file() and self.can_handle(file_path):
                try:
                    metadata = self.extract(file_path)
                    all_metadata.extend(metadata)
                except Exception as e:
                    self.add_error(file_path, str(e))
                    logger.error(f"Error extracting from {file_path}: {e}", exc_info=True)

        return all_metadata

    def add_error(self, file_path: Path, message: str, line: Optional[int] = None) -> None:
        """
        Record an error encountered during extraction.

        Args:
            file_path: File where error occurred
            message: Error message
            line: Optional line number
        """
        self.errors.append(
            {"file": str(file_path), "message": message, "line": line, "type": "error"}
        )

    def add_warning(self, file_path: Path, message: str, line: Optional[int] = None) -> None:
        """
        Record a warning encountered during extraction.

        Args:
            file_path: File where warning occurred
            message: Warning message
            line: Optional line number
        """
        self.warnings.append(
            {"file": str(file_path), "message": message, "line": line, "type": "warning"}
        )

    def get_report(self) -> Dict[str, Any]:
        """
        Get a report of errors and warnings.

        Returns:
            Dictionary with error and warning statistics
        """
        return {
            "errors": self.errors,
            "warnings": self.warnings,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
        }

    def clear_report(self) -> None:
        """Clear all recorded errors and warnings."""
        self.errors.clear()
        self.warnings.clear()

    @staticmethod
    def normalize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize metadata to ensure consistent structure.

        Args:
            metadata: Raw metadata dictionary

        Returns:
            Normalized metadata dictionary
        """
        defaults = {
            "inputs": [],
            "outputs": [],
            "side_effects": [],
            "depends_on": [],
            "used_by": [],
            "tags": [],
            "deprecated": False,
            "replacement": None,
            "security_notes": None,
            "performance_notes": None,
            "examples": [],
        }

        # Merge defaults with provided metadata
        normalized = {**defaults, **metadata}

        # Ensure lists are actually lists
        for list_field in ["inputs", "outputs", "side_effects", "depends_on", "used_by", "tags", "examples"]:
            if not isinstance(normalized[list_field], list):
                normalized[list_field] = []

        return normalized
