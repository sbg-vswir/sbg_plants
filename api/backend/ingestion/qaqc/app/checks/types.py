"""
Shared data structures for the QAQC pipeline.

CheckContext  — state bag threaded through every check in dependency order.
CheckResult   — return value from every check() function.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CheckContext:
    """
    Carries all shared state through the check pipeline.

    Populated once before the runner starts:
        enums  — { enum_type_name: set(valid_labels) }   loaded from DB
        db     — { ref_name: set | dict }                loaded from db_refs
        data   — { slot_name: DataFrame | dict }         parsed bundle files

    Extended by each check as it runs:
        output — cross-file forwarded values, e.g. campaign_sensor_set,
                 granule_id_set, plot_shape_map.  Each check reads what
                 upstream checks have written and writes what downstream
                 checks will need.
    """
    enums:  dict[str, set]
    db:     dict[str, Any]
    data:   dict[str, Any]
    output: dict[str, Any] = field(default_factory=dict)


@dataclass
class CheckResult:
    """
    Return value from every check() function.

    file_name  — matches the bundle slot key, used as the report dict key.
    row_count  — number of rows / features checked.
    errors     — list of error dicts { file, row, column, message }.
                 Any errors cause the overall run to be QAQC_FAIL.
    warnings   — list of warning dicts with the same shape.
                 Warnings are reported but do not block ingestion.
    """
    file_name: str
    row_count: int
    errors:    list[dict]
    warnings:  list[dict]
