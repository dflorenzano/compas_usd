"""COMPAS wrapper for USD (Universal Scene Description)."""

import os

from .stage import (
    METERS_PER_UNIT,
    create_stage,
    meters_per_unit_from_unit,
    unit_from_meters_per_unit,
    stage_unit,
    unit_scale,
    make_valid_identifier,
    unique_child_path,
)

__author__ = ["Romana Rust", "Daniele Florenzano"]
__copyright__ = "Gramazio Kohler Research - ETH Zurich"
__license__ = "MIT License"
__email__ = "rust@arch.ethz.ch"
__version__ = "0.1.0"


HERE = os.path.dirname(__file__)

HOME = os.path.abspath(os.path.join(HERE, "../../"))
DATA = os.path.abspath(os.path.join(HOME, "data"))
DOCS = os.path.abspath(os.path.join(HOME, "docs"))
TEMP = os.path.abspath(os.path.join(HOME, "temp"))


__all__ = [
    "HOME",
    "DATA",
    "DOCS",
    "TEMP",
    "METERS_PER_UNIT",
    "create_stage",
    "meters_per_unit_from_unit",
    "unit_from_meters_per_unit",
    "stage_unit",
    "unit_scale",
    "make_valid_identifier",
    "unique_child_path",
]
