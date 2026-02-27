"""CelesTrak TLE data ingestion module.

Downloads Two-Line Element (TLE) data for active satellites from
CelesTrak and persists it locally using atomic file writes.
"""

import argparse
import logging
import shutil
import sys
import tempfile
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

CELESTRAK_ACTIVE_URL: str = (
    "https://celestrak.org/NORAD/elements/gp.php"
    "?GROUP=active&FORMAT=tle"
)
DEFAULT_DATA_DIR: Path = Path("data")
TLE_FILENAME: str = "active_satellites.txt"
REQUEST_TIMEOUT: int = 15


def setup_logging(verbose: bool = False) -> None:
    """Configure root logger with appropriate level and format.

    Args:
        verbose: If True, set log level to DEBUG; otherwise INFO.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


def fetch_tle_data(
    data_dir: Path,
    url: str = CELESTRAK_ACTIVE_URL,
) -> Path:
    """Download TLE data from CelesTrak and save it atomically.

    The file is first written to a temporary location, then moved
    to the final path to prevent data corruption on failure.

    Args:
        data_dir: Directory where TLE data will be stored.
        url: URL to fetch TLE data from.

    Returns:
        Path to the saved TLE file.

    Raises:
        RuntimeError: If the download fails due to network issues.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    final_path: Path = data_dir / TLE_FILENAME

    logger.info("Downloading TLE data from %s ...", url)

    tmp_path: str = ""
    try:
        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            stream=True,
        )
        response.raise_for_status()

        with tempfile.NamedTemporaryFile(
            delete=False,
            mode="w",
            encoding="utf-8",
            suffix=".tle.tmp",
            dir=str(data_dir),
        ) as tmp_file:
            tmp_path = tmp_file.name
            for line in response.iter_lines(decode_unicode=True):
                if line is not None:
                    tmp_file.write(line + "\n")

        logger.debug("Temporary file written to %s", tmp_path)

        shutil.move(tmp_path, str(final_path))
        tmp_path = ""

        logger.info(
            "Successfully saved TLE data to %s", final_path
        )
        return final_path

    except requests.RequestException as exc:
        logger.critical(
            "Failed to download TLE data: %s", exc
        )
        raise RuntimeError(
            f"TLE download failed: {exc}"
        ) from exc

    finally:
        if tmp_path:
            tmp_file_path = Path(tmp_path)
            if tmp_file_path.exists():
                tmp_file_path.unlink()
                logger.debug(
                    "Cleaned up temporary file %s",
                    tmp_path,
                )


def main() -> None:
    """Entry point for the TLE ingestion CLI."""
    parser = argparse.ArgumentParser(
        description="Download active satellite TLE data from CelesTrak.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory to store downloaded TLE files (default: data/).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose (DEBUG) logging.",
    )
    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    try:
        result_path = fetch_tle_data(data_dir=args.data_dir)
        logger.info("Ingestion complete: %s", result_path)
    except RuntimeError:
        sys.exit(1)


if __name__ == "__main__":
    main()
