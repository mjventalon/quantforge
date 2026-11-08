r"""Market regime detection with a Gaussian hidden Markov model (HMM).

Returns are assumed to come from one of *K* hidden regimes (e.g. calm bull,
volatile bear). Each regime has its own mean and volatility; the regime itself
follows a Markov chain with transition matrix ``A[i, j] = P(s_t = j | s_{t-1} = i)``.

Parameters are estimated by the Baum-Welch (EM) algorithm with scaled
forward-backward recursions, from several random starts.

Two kinds of regime probabilities are returned — the difference matters:

* **filtered** ``P(s_t | r_1..r_t)`` uses data up to day *t* only. This is what
  you could have known in real time; use it for trading rules and backtests.
* **smoothed** ``P(s_t | r_1..r_T)`` uses the whole sample, including the future.
  It is better for describing history but must never drive a backtest.

States are sorted from lowest to highest volatility.

References
----------
Hamilton, J. (1989). A New Approach to the Economic Analysis of Nonstationary
Time Series and the Business Cycle. *Econometrica*, 57(2).
Rabiner, L. (1989). A Tutorial on Hidden Markov Models. *Proc. IEEE*, 77(2).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

__all__ = ["HMMResult", "fit_hmm", "hmm_forward"]

_MIN_VAR = 1e-10


@dataclass
class HMMResult:
    means: np.ndarray            # per-period mean of each state
    variances: np.ndarray        # per-period variance of each state
    transition: np.ndarray       # K x K
    initial: np.ndarray
    loglik: float
    filtered: pd.DataFrame       # causal probabilities
    smoothed: pd.DataFrame       # full-sample probabilities
    viterbi: pd.Series           # most likely state path
    n_iter: int
    converged: bool
    periods_per_year: int = 252

    @property
    def n_states(self) -> int:
        return len(self.means)

    @property
    def aic(self) -> float:
        k = self.n_states
        n_params = 2 * k + k * (k - 1) + (k - 1)
        return float(2 * n_params - 2 * self.loglik)

    @property
    def bic(self) -> float:
        k = self.n_states
        n_params = 2 * k + k * (k - 1) + (k - 1)
        return float(n_params * np.log(len(self.viterbi)) - 2 * self.loglik)

    @property
    def expected_duration(self) -> np.ndarray:
        """Average number of periods spent in each regime once entered: 1 / (1 − A_ii)."""
        return 1.0 / (1.0 - np.diag(self.transition))

    @property
    def stationary(self) -> np.ndarray:
        """Long-run share of time in each regime."""
        w, v = np.linalg.eig(self.transition.T)
        pi = np.real(v[:, np.argmin(np.abs(w - 1))])
        return pi / pi.sum()

    def summary(self, labels: list[str] | None = None) -> pd.DataFrame:
        p = self.periods_per_year
        lab = labels or default_labels(self.n_states)
        return pd.DataFrame({
            "annual_return": self.means * p,
            "annual_vol": np.sqrt(self.variances * p),
            "expected_duration": self.expected_duration,
            "long_run_share": self.stationary,
            "share_of_sample": np.bincount(self.viterbi.to_numpy(), minlength=self.n_states)
            / len(self.viterbi),
        }, index=lab)


def default_labels(k: int) -> list[str]:
    return {1: ["Single"], 2: ["Calm", "Turbulent"], 3: ["Calm", "Normal", "Turbulent"]}.get(
        k, [f"Regime {i + 1} (vol rank)" for i in range(k)])


def _emission(x: np.ndarray, means: np.ndarray, var: np.ndarray) -> np.ndarray:
    return np.exp(-0.5 * (x[:, None] - means) ** 2 / var) / np.sqrt(2 * np.pi * var)


def hmm_forward(x: np.ndarray, means: np.ndarray, var: np.ndarray, A: np.ndarray,
                pi: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Scaled forward pass: filtered probabilities, scaling constants, log-likelihood."""
    B = np.maximum(_emission(x, means, var), 1e-300)
    n, k = B.shape
    alpha = np.empty((n, k))
    c = np.empty(n)
    a = pi * B[0]
    c[0] = a.sum()
    alpha[0] = a / c[0]
    for t in range(1, n):
        a = (alpha[t - 1] @ A) * B[t]
        c[t] = a.sum()
        alpha[t] = a / c[t]
    return alpha, c, float(np.log(c).sum())


def _backward(B: np.ndarray, A: np.ndarray, c: np.ndarray) -> np.ndarray:
    n, k = B.shape
    beta = np.empty((n, k))
    beta[-1] = 1.0
    for t in range(n - 2, -1, -1):
        beta[t] = (A @ (B[t + 1] * beta[t + 1])) / c[t + 1]
    return beta


def _viterbi(x: np.ndarray, means: np.ndarray, var: np.ndarray, A: np.ndarray,
             pi: np.ndarray) -> np.ndarray:
    logB = -0.5 * (x[:, None] - means) ** 2 / var - 0.5 * np.log(2 * np.pi * var)
    logA = np.log(np.maximum(A, 1e-300))
    n, k = logB.shape
    delta = np.log(np.maximum(pi, 1e-300)) + logB[0]
    psi = np.zeros((n, k), dtype=int)
    for t in range(1, n):
        scores = delta[:, None] + logA
        psi[t] = np.argmax(scores, axis=0)
        delta = scores[psi[t], np.arange(k)] + logB[t]
    path = np.empty(n, dtype=int)
    path[-1] = int(np.argmax(delta))
    for t in range(n - 2, -1, -1):
        path[t] = psi[t + 1, path[t + 1]]
    return path


def _em(x: np.ndarray, k: int, rng: np.random.Generator, max_iter: int, tol: float):
    q = np.quantile(x, np.linspace(0.15, 0.85, k)) + rng.normal(0, x.std() * 0.05, k)
    means = np.sort(q)
    var = np.full(k, x.var()) * rng.uniform(0.5, 1.5, k)
    A = np.full((k, k), 0.05 / max(k - 1, 1)) + np.eye(k) * (0.95 - 0.05 / max(k - 1, 1))
    A /= A.sum(axis=1, keepdims=True)
    pi = np.full(k, 1.0 / k)
    prev = -np.inf
    converged = False
    it = 0
    for it in range(1, max_iter + 1):  # noqa: B007 - reported to the caller
        alpha, c, ll = hmm_forward(x, means, var, A, pi)
        B = np.maximum(_emission(x, means, var), 1e-300)
        beta = _backward(B, A, c)
        gamma = alpha * beta
        gamma /= gamma.sum(axis=1, keepdims=True)
        xi = (alpha[:-1, :, None] * A[None] * (B[1:] * beta[1:])[:, None, :]) / c[1:, None, None]
        pi = gamma[0]
        A = xi.sum(axis=0) / gamma[:-1].sum(axis=0)[:, None]
        A /= A.sum(axis=1, keepdims=True)
        w = gamma.sum(axis=0)
        means = gamma.T @ x / w
        var = np.maximum((gamma * (x[:, None] - means) ** 2).sum(axis=0) / w, _MIN_VAR)
        if abs(ll - prev) < tol * max(1.0, abs(ll)):
            converged = True
            break
        prev = ll
    _, _, ll = hmm_forward(x, means, var, A, pi)
    return means, var, A, pi, ll, it, converged


def fit_hmm(returns: pd.Series, n_states: int = 2, n_starts: int = 8, max_iter: int = 500,
            tol: float = 1e-9, seed: int | None = 0, periods_per_year: int = 252) -> HMMResult:
    """Fit a Gaussian HMM to a return series by EM with multiple random starts."""
    s = pd.Series(returns).dropna()
    if len(s) < 50 * n_states:
        raise ValueError("not enough observations for this number of regimes")
    x = s.to_numpy(dtype=float)
    scale = x.std()
    z = (x - x.mean()) / scale                    # standardize for numerical stability
    rng = np.random.default_rng(seed)
    best = None
    for _ in range(n_starts):
        out = _em(z, n_states, rng, max_iter, tol)
        if best is None or out[4] > best[4]:
            best = out
    means_z, var_z, A, pi, ll_z, it, conv = best
    order = np.argsort(var_z)                     # low-vol regime first
    means_z, var_z = means_z[order], var_z[order]
    A = A[np.ix_(order, order)]
    pi = pi[order]
    means = x.mean() + scale * means_z
    var = var_z * scale**2
    alpha, c, ll = hmm_forward(x, means, var, A, pi)
    B = np.maximum(_emission(x, means, var), 1e-300)
    beta = _backward(B, A, c)
    gamma = alpha * beta
    gamma /= gamma.sum(axis=1, keepdims=True)
    labels = default_labels(n_states)
    return HMMResult(
        means=means, variances=var, transition=A, initial=pi, loglik=ll,
        filtered=pd.DataFrame(alpha, index=s.index, columns=labels),
        smoothed=pd.DataFrame(gamma, index=s.index, columns=labels),
        viterbi=pd.Series(_viterbi(x, means, var, A, pi), index=s.index, name="regime"),
        n_iter=it, converged=conv, periods_per_year=periods_per_year,
    )
