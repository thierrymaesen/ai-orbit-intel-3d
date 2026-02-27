"""Orbital dynamics module — TLE parsing and feature engineering.

Reads Two-Line Element data via Skyfield, extracts orbital parameters
for each satellite, and produces a pandas DataFrame suitable for
downstream anomaly detection with Isolation Forest.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from skyfield.api import EarthSatellite, load

logger = logging.getLogger(__name__)

DEFAULT_DATA_DIR: Path = Path("data")
TLE_FILENAME: str = "active_satellites.txt"


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


def load_tle_objects(data_dir: Path) -> List[EarthSatellite]:
    """Load satellite objects from a TLE file using Skyfield.

    Args:
        data_dir: Directory containing the TLE file.

    Returns:
        List of EarthSatellite objects parsed from the file.

    Raises:
        FileNotFoundError: If the TLE file does not exist.
    """
    file_path: Path = data_dir / TLE_FILENAME

    if not file_path.exists():
        raise FileNotFoundError(
            f"TLE file not found: {file_path}"
        )

    satellites: List[EarthSatellite] = load.tle_file(
        str(file_path)
    )
    logger.info("Loaded %d satellites from TLE file", len(satellites))
    return satellites


def extract_features(
    satellites: List[EarthSatellite],
) -> pd.DataFrame:
    """Extract orbital parameters from satellite objects.

    Builds a DataFrame with one row per satellite containing
    key orbital features derived from the SGP4 model. Satellites
    with corrupt or unreadable data are skipped with a warning.

    Args:
        satellites: List of EarthSatellite objects.

    Returns:
        DataFrame indexed by norad_id with orbital feature columns.
    """
    records: List[Dict[str, Any]] = []

    for sat in satellites:
        try:
            record: Dict[str, Any] = {
                "name": sat.name,
                "norad_id": sat.model.satnum,
                "inclination": sat.model.inclo,
                "eccentricity": sat.model.ecco,
                "mean_motion": sat.model.no_kozai,
                "bstar": sat.model.bstar,
                "epoch_days": (
                    sat.epoch.utc_datetime().timestamp()
                ),
            }
            records.append(record)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Skipping satellite %s: %s",
                getattr(sat, "name", "UNKNOWN"),
                exc,
            )

    df: pd.DataFrame = pd.DataFrame(records)

    if not df.empty:
        df = df.set_index("norad_id")

    logger.info("Extracted features for %d satellites", len(df))
    return df


def main() -> None:
    """Entry point for the orbital dynamics CLI."""
    parser = argparse.ArgumentParser(
        description=(
            "Parse TLE data and extract orbital features "
            "for anomaly detection."
        ),
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory containing TLE files (default: data/).",
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
        satellites = load_tle_objects(data_dir=args.data_dir)
        df = extract_features(satellites)
        print(df.head())
        print(df.describe())
        logger.info("Feature extraction complete.")
    except (FileNotFoundError, RuntimeError) as exc:
        logger.critical("Fatal error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
