"""Prior-window intercept OLS using scaled SVD, never normal-equation inversion."""

import numpy as np


def fit_predict(y, factors, *, signal_index, minimum=60, window=120):
    keys = list(factors.columns)
    return _pack(
        keys,
        _core(
            np.asarray(y, dtype=float),
            np.asarray(factors, dtype=float),
            signal_index,
            minimum,
            window,
        ),
    )


def residual_series(y, factors, *, minimum=60, window=120):
    targets, values = _arrays(y, factors)
    return [_core(targets, values, index, minimum, window)[5] for index in range(targets.shape[0])]


def fit_columns(y, factors, *, minimum=60, window=120):
    """One conversion, then the same window fit written into columns."""
    targets, values = _arrays(y, factors)
    count = targets.shape[0]
    resid = np.full(count, np.nan)
    resid_z = np.full(count, np.nan)
    sigma = np.full(count, np.nan)
    alpha = np.full(count, np.nan)
    beta_m = np.full(count, np.nan)
    market = list(factors.columns).index("m") if "m" in factors.columns else None
    for index in range(count):
        _nobs, _dof, fitted, betas, scale, residual, score, _null, _health = _core(
            targets, values, index, minimum, window
        )
        if residual is not None:
            resid[index] = residual
        if score is not None:
            resid_z[index] = score
        if scale is not None:
            sigma[index] = scale
        if fitted is not None:
            alpha[index] = fitted
        if betas is not None and market is not None:
            beta_m[index] = betas[market]
    return resid, resid_z, sigma, alpha, beta_m


def _arrays(y, factors):
    return np.asarray(y, dtype=float), np.asarray(factors, dtype=float)


def _pack(keys, core):
    nobs, dof, alpha, betas, sigma, resid, resid_z, null_reason, health = core
    return {
        "alpha": alpha,
        "betas": {key: None for key in keys} if betas is None else dict(zip(keys, betas, strict=True)),
        "sigma": sigma,
        "resid": resid,
        "resid_z": resid_z,
        "nobs": nobs,
        "dof": dof,
        "null_reason": null_reason,
        "health_codes": health,
    }


def _core(targets, values, signal_index, minimum, window):
    begin = max(0, signal_index - window)
    sample = values[begin:signal_index]
    observed_window = targets[begin:signal_index]
    valid = np.isfinite(observed_window) & np.isfinite(sample).all(axis=1)
    x, target = sample[valid], observed_window[valid]
    n, p = len(target), sample.shape[1] + 1
    dof = n - p
    if n < minimum or n <= p:
        return n, dof, None, None, None, None, None, "insufficient_history", ["insufficient_history"]
    means, scales = x.mean(axis=0), x.std(axis=0)
    if (scales == 0).any():
        return n, dof, None, None, None, None, None, "rank_deficient", ["rank_deficient"]
    design = np.column_stack([np.ones(n), (x - means) / scales])
    coefficients, _, rank, _ = np.linalg.lstsq(design, target, rcond=None)
    if rank < p:
        return n, dof, None, None, None, None, None, "rank_deficient", ["rank_deficient"]
    slope = coefficients[1:] / scales
    alpha = float(coefficients[0] - means @ slope)
    errors = target - alpha - x @ slope
    sigma = float(np.sqrt(np.dot(errors, errors) / (n - p)))
    betas = [float(item) for item in slope]
    current, observed = values[signal_index], float(targets[signal_index])
    if not np.isfinite(observed) or not np.isfinite(current).all():
        return n, dof, alpha, betas, sigma, None, None, "missing_current_return", ["missing_current_return"]
    residual = float(observed - alpha - current @ slope)
    tolerance = np.finfo(float).eps * max(1.0, float(np.max(np.abs(target)))) * 100
    if abs(residual) < tolerance:
        residual = 0.0
    score = residual / sigma if sigma >= tolerance else None
    if sigma < tolerance:
        return n, dof, alpha, betas, 0.0, residual, score, "zero_residual_sigma", ["zero_residual_sigma"]
    return n, dof, alpha, betas, sigma, residual, score, None, []
