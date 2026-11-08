"""Numerical derivatives used for standard errors of MLE estimates."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np


def hessian(f: Callable[[np.ndarray], float], x: np.ndarray, rel_step: float = 1e-4) -> np.ndarray:
    """Central-difference Hessian of a scalar function."""
    x = np.asarray(x, dtype=float)
    n = x.size
    h = rel_step * np.maximum(np.abs(x), 1e-2)
    H = np.empty((n, n))
    for i in range(n):
        for j in range(i, n):
            ei = np.zeros(n)
            ej = np.zeros(n)
            ei[i] = h[i]
            ej[j] = h[j]
            val = (f(x + ei + ej) - f(x + ei - ej) - f(x - ei + ej) + f(x - ei - ej)) / (
                4 * h[i] * h[j]
            )
            H[i, j] = H[j, i] = val
    return H


def standard_errors(neg_loglik: Callable[[np.ndarray], float], x: np.ndarray) -> np.ndarray:
    """Square roots of the diagonal of the inverse Hessian of the negative log-likelihood."""
    H = hessian(neg_loglik, x)
    try:
        cov = np.linalg.inv(H)
    except np.linalg.LinAlgError:
        cov = np.linalg.pinv(H)
    d = np.diag(cov)
    return np.sqrt(np.where(d > 0, d, np.nan))
