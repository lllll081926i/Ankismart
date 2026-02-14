"""Log file export utilities for Ankismart.

Provides functionality to collect and export application logs for troubleshooting.
"""

from __future__ import annotations

import logging
import zipfile
from datetime import datetime
from pathlib import Path

from ankismart.core.logging import get_log_directory

logger = logging.getLogger(__name__)


class LogExporter:
    """Utility class for exporting application logs."""

    def __init__(self):
        """Initialize log exporter."""
        self.log_dir = self._get_log_directory()

    def _get_log_directory(self) -> Path:
        """Get the application log directory.

        Returns:
            Path to log directory
        """
        configured_dir = get_log_directory()
        if configured_dir.exists() and configured_dir.is_dir():
            return configured_dir

        # Try to find log directory in common locations
        possible_dirs = [
            Path.cwd() / "logs",
            Path.home() / ".ankismart" / "logs",
            Path.home() / "AppData" / "Local" / "Ankismart" / "logs",  # Windows
            Path.home() / "Library" / "Logs" / "Ankismart",  # macOS
        ]

        for log_dir in possible_dirs:
            if log_dir.exists() and log_dir.is_dir():
                return log_dir

        # Default to current directory logs
        return Path.cwd() / "logs"

    def get_log_files(self, max_files: int = 10) -> list[Path]:
        """Get recent log files.

        Args:
            max_files: Maximum number of log files to include

        Returns:
            List of log file paths, sorted by modification time (newest first)
        """
        if not self.log_dir.exists():
            return []

        # Find all log files
        log_files = []
        for pattern in ["*.log", "*.txt"]:
            log_files.extend(self.log_dir.glob(pattern))

        # Sort by modification time (newest first)
        log_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        # Return up to max_files
        return log_files[:max_files]

    def export_logs(self, output_path: Path, max_files: int = 10) -> bool:
        """Export log files to a zip archive.

        Args:
            output_path: Path to output zip file
            max_files: Maximum number of log files to include

        Returns:
            True if export successful, False otherwise

        Raises:
            FileNotFoundError: If no log files found
            PermissionError: If cannot write to output path
            Exception: For other errors
        """
        log_files = self.get_log_files(max_files)

        if not log_files:
            raise FileNotFoundError("No log files found")

        try:
            # Create zip archive
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for log_file in log_files:
                    # Add file to zip with relative name
                    arcname = log_file.name
                    zipf.write(log_file, arcname)

                # Add metadata file
                metadata = self._generate_metadata(log_files)
                zipf.writestr("export_info.txt", metadata)

            logger.info(f"Logs exported successfully to {output_path}")
            return True

        except PermissionError as e:
            logger.error(f"Permission denied when exporting logs: {e}")
            raise

        except Exception as e:
            logger.error(f"Failed to export logs: {e}")
            raise

    def _generate_metadata(self, log_files: list[Path]) -> str:
        """Generate metadata information for the export.

        Args:
            log_files: List of exported log files

        Returns:
            Metadata string
        """
        lines = [
            "Ankismart Log Export",
            "=" * 50,
            f"Export Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total Files: {len(log_files)}",
            "",
            "Included Files:",
        ]

        for log_file in log_files:
            stat = log_file.stat()
            size_kb = stat.st_size / 1024
            mod_time = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"  - {log_file.name} ({size_kb:.1f} KB, modified: {mod_time})")

        lines.extend([
            "",
            "=" * 50,
            "Please include this file when reporting issues.",
        ])

        return "\n".join(lines)

    def get_total_log_size(self) -> int:
        """Get total size of all log files in bytes.

        Returns:
            Total size in bytes
        """
        log_files = self.get_log_files()
        return sum(f.stat().st_size for f in log_files)

    def get_log_count(self) -> int:
        """Get count of available log files.

        Returns:
            Number of log files
        """
        return len(self.get_log_files())
