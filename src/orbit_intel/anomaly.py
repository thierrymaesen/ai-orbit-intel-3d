"""Orbital anomaly detection module — Isolation Forest on orbital features.

Consumes the pandas DataFrame produced by the dynamics module, normalises
orbital features with StandardScaler, trains an Isolation Forest model,
and annotates each satellite with a binary anomaly flag and a continuous
severity score in the 0-1 range.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from .dynamics import load_tle_objects, extract_features

logger = logging.getLogger(__name__)

DEFAULT_DATA_DIR: Path = Path("data")

FEATURES_TO_USE: List[str] = [
    "inclination",
    "eccentricity",
    "mean_motion",
    "bstar",
]

CONTAMINATION_RATE: float = 0.05


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


class OrbitalAnomalyDetector:
    """Detect orbital anomalies using an Isolation Forest model.

    The detector normalises selected orbital features, fits an
    Isolation Forest to identify statistical outliers, and produces
    a continuous anomaly severity score for every satellite.

    Attributes:
        scaler: StandardScaler used to normalise input features.
        model: Isolation Forest estimator.
        is_trained: Whether the model has been fitted.
    """

    def __init__(
        self,
        contamination: float = CONTAMINATION_RATE,
        random_state: int = 42,
    ) -> None:
        """Initialise the anomaly detector.

        Args:
            contamination: Expected proportion of anomalies in the
                dataset.  Defaults to ``CONTAMINATION_RATE`` (0.05).
            random_state: Random seed for reproducibility.
        """
        self.scaler: StandardScaler = StandardScaler()
        self.model: IsolationForest = IsolationForest(
            contamination=contamination,
            random_state=random_state,
        )
        self.is_trained: bool = False

    def fit_predict(
        self,
        df: pd.DataFrame,
        features: List[str] = FEATURES_TO_USE,
    ) -> pd.DataFrame:
        """Fit the Isolation Forest and score every satellite.

        The method normalises the requested feature columns, trains
        the model, and appends ``is_anomaly`` (bool) and
        ``anomaly_score`` (float 0-1, higher means more anomalous)
        columns to a copy of the input DataFrame.

        Args:
            df: DataFrame produced by
                :func:`orbit_intel.dynamics.extract_features`.
            features: Column names to use as model inputs.

        Returns:
            A copy of *df* with ``is_anomaly`` and ``anomaly_score``
            columns added.

        Raises:
            ValueError: If any of the requested *features* are
                missing from *df*.
        """
        missing: List[str] = [
            f for f in features if f not in df.columns
        ]
        if missing:
            raise ValueError(
                f"Missing required features in DataFrame: {missing}"
            )

        x: np.ndarray = df[features].values
        x_scaled: np.ndarray = self.scaler.fit_transform(x)

        logger.info("Training Isolation Forest...")
        self.model.fit(x_scaled)

        raw_scores: np.ndarray = self.model.decision_function(
            x_scaled
        )
        predictions: np.ndarray = self.model.predict(x_scaled)

        df_result: pd.DataFrame = df.copy()
        df_result["is_anomaly"] = predictions == -1

        # Invert scores so higher means more anomalous
        inverted_scores: np.ndarray = -raw_scores

        # Min-max scale to 0-1 range
        min_s: float = float(inverted_scores.min())
        max_s: float = float(inverted_scores.max())
        if max_s > min_s:
            normalized_scores = (
                (inverted_scores - min_s) / (max_s - min_s)
            )
        else:
            normalized_scores = inverted_scores

        df_result["anomaly_score"] = np.clip(
            normalized_scores, 0.0, 1.0
        )

        self.is_trained = True

        n_anomalies: int = int(df_result["is_anomaly"].sum())
        logger.info(
            "Found %d anomalies out of %d satellites",
            n_anomalies,
            len(df_result),
        )

        return df_result


def main() -> None:
    """Entry point for the orbital anomaly detection CLI."""
    parser = argparse.ArgumentParser(
        description=(
            "Run Isolation Forest anomaly detection "
            "on orbital features extracted from TLE data."
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
    parser.add_argument(
        "--contamination",
        type=float,
        default=CONTAMINATION_RATE,
        help=(
            "Expected anomaly ratio "
            f"(default: {CONTAMINATION_RATE})."
        ),
    )
    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    try:
        satellites = load_tle_objects(data_dir=args.data_dir)
        df = extract_features(satellites)

        detector = OrbitalAnomalyDetector(
            contamination=args.contamination,
        )
        df_result = detector.fit_predict(df)

        top_anomalies: pd.DataFrame = (
            df_result.sort_values(
                "anomaly_score", ascending=False
            ).head(10)
        )

        print("\n=== Top 10 Most Anomalous Satellites ===\n")
        for _, row in top_anomalies.iterrows():
            print(
                f"  {row['name']:<30s}  "
                f"score: {row['anomaly_score']:.4f}"
            )

        logger.info("Anomaly detection complete.")
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        logger.critical("Fatal error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
