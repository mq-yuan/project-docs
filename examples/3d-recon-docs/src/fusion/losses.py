"""Truncation schedule helper and minimal CLI stub referenced by the example docs."""

import argparse
import logging

logger = logging.getLogger(__name__)


def truncation_band_meters(progress: float) -> float:
    """Compute linear coarse-to-fine TSDF truncation band in meters.

    Args:
        progress: Normalized frame progress in ``[0.0, 1.0]``.

    Returns:
        Truncation distance in meters.
    """
    alpha = min(max(progress / 0.30, 0.0), 1.0)
    return 0.12 + alpha * (0.04 - 0.12)


def main() -> None:
    """Minimal CLI entry point matching ``docs/guides/benchmarking.md``."""
    parser = argparse.ArgumentParser(description="Evaluate TSDF truncation schedule stub.")
    parser.add_argument("--split", default="val")
    parser.add_argument("--trunc-schedule", default="anneal_12_to_4cm")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger.info(
        "split=%s schedule=%s band_start=%.2fm band_end=%.2fm",
        args.split,
        args.trunc_schedule,
        truncation_band_meters(0.0),
        truncation_band_meters(1.0),
    )


if __name__ == "__main__":
    main()
