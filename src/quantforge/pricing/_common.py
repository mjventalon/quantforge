"""Shared types and input validation for the pricing module."""

from __future__ import annotations

from enum import Enum

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]


class OptionType(str, Enum):
    """Option payoff direction."""

    CALL = "call"
    PUT = "put"

    @classmethod
    def parse(cls, value: OptionType | str) -> OptionType:
        if isinstance(value, OptionType):
            return value
        try:
            return cls(str(value).lower().strip())
        except ValueError as exc:
            raise ValueError(f"option_type must be 'call' or 'put', got {value!r}") from exc


class ExerciseStyle(str, Enum):
    """When the option holder may exercise."""

    EUROPEAN = "european"
    AMERICAN = "american"

    @classmethod
    def parse(cls, value: ExerciseStyle | str) -> ExerciseStyle:
        if isinstance(value, ExerciseStyle):
            return value
        try:
            return cls(str(value).lower().strip())
        except ValueError as exc:
            raise ValueError(f"exercise must be 'european' or 'american', got {value!r}") from exc


def as_float_array(x: ArrayLike, name: str) -> FloatArray:
    arr = np.asarray(x, dtype=np.float64)
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must be finite")
    return arr


def require_positive(x: ArrayLike, name: str) -> FloatArray:
    arr = as_float_array(x, name)
    if np.any(arr <= 0):
        raise ValueError(f"{name} must be strictly positive")
    return arr


def require_non_negative(x: ArrayLike, name: str) -> FloatArray:
    arr = as_float_array(x, name)
    if np.any(arr < 0):
        raise ValueError(f"{name} must be non-negative")
    return arr


def maybe_scalar(x: FloatArray) -> float | FloatArray:
    """Return a Python float for 0-d results, the array otherwise."""
    return float(x) if np.ndim(x) == 0 else x


def intrinsic_value(spot: ArrayLike, strike: ArrayLike, option_type: OptionType) -> FloatArray:
    spot = np.asarray(spot, dtype=np.float64)
    strike = np.asarray(strike, dtype=np.float64)
    if option_type is OptionType.CALL:
        return np.maximum(spot - strike, 0.0)
    return np.maximum(strike - spot, 0.0)
