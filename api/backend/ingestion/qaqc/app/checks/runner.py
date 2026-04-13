"""
QAQC check runner.

Calls each file's check() function in dependency order, threads CheckContext
through the pipeline, and assembles the final report dict.

To add a check for a new bundle file:
  1. Create app/checks/<file_name>.py with a check(context) -> CheckResult function.
  2. Import it below and add it to CHECKS.
"""

from __future__ import annotations

import logging

from app.checks import campaign, wavelengths, granule, plots, traits, spectra
from app.checks.types import CheckContext, CheckResult

logger = logging.getLogger(__name__)

# Execution order matters — each check may read from context.output values
# written by earlier checks (e.g. campaign writes campaign_sensor_set which
# wavelengths and granule read).
CHECKS = [
    campaign,
    wavelengths,
    granule,
    plots,
    traits,
    spectra,
]


def run_all(context: CheckContext) -> tuple[dict, bool]:
    """
    Run every check in order.

    Returns:
        report     — { file_name: { row_count, errors, warnings } }
        has_errors — True if any check produced at least one error
    """
    report:     dict = {}
    has_errors: bool = False

    for module in CHECKS:
        logger.info("Running check: %s", module.__name__.split(".")[-1])
        result: CheckResult = module.check(context)

        report[result.file_name] = {
            "row_count": result.row_count,
            "errors":    result.errors,
            "warnings":  result.warnings,
        }

        if result.errors:
            has_errors = True
            logger.info(
                "Check '%s': %d error(s), %d warning(s)",
                result.file_name, len(result.errors), len(result.warnings),
            )
        else:
            logger.info(
                "Check '%s': PASS (%d warning(s))",
                result.file_name, len(result.warnings),
            )

    return report, has_errors
