"""Prior-window intercept OLS using scaled SVD, never normal-equation inversion."""

import numpy as np


def fit_predict(y, factors, *, signal_index, minimum=60, window=120):
    keys = list(factors.columns)
    result = {
        "alpha": None,
        "betas": {key: None for key in keys},
        "sigma": None,
        "resid": None,
        "resid_z": None,
        "nobs": 0,
        "dof": None,
        "null_reason": "insufficient_history",
        "health_codes": ["insufficient_history"],
    }
    begin = max(0, signal_index - window)
    values = np.asarray(factors.iloc[begin:signal_index], dtype=float)
    targets = np.asarray(y.iloc[begin:signal_index], dtype=float)
    valid = np.isfinite(targets) & np.isfinite(values).all(axis=1)
    x, target = values[valid], targets[valid]
    n, p = len(target), len(keys) + 1
    result.update(nobs=n, dof=n - p)
    if n < minimum or n <= p:
        return result
    means, scales = x.mean(axis=0), x.std(axis=0)
    if (scales == 0).any():
        return {**result, "null_reason": "rank_deficient", "health_codes": ["rank_deficient"]}
    design = np.column_stack([np.ones(n), (x - means) / scales])
    coefficients, _, rank, _ = np.linalg.lstsq(design, target, rcond=None)
    if rank < p:
        return {**result, "null_reason": "rank_deficient", "health_codes": ["rank_deficient"]}
    betas = coefficients[1:] / scales
    alpha = coefficients[0] - means @ betas
    errors = target - alpha - x @ betas
    sigma = float(np.sqrt(np.dot(errors, errors) / (n - p)))
    result.update(
        alpha=float(alpha),
        betas=dict(zip(keys, map(float, betas), strict=True)),
        sigma=sigma,
        null_reason=None,
        health_codes=[],
    )
    current, observed = np.asarray(factors.iloc[signal_index], dtype=float), float(y.iloc[signal_index])
    if not np.isfinite(observed) or not np.isfinite(current).all():
        return {**result, "null_reason": "missing_current_return", "health_codes": ["missing_current_return"]}
    residual = float(observed - alpha - current @ betas)
    tolerance = np.finfo(float).eps * max(1.0, float(np.max(np.abs(target)))) * 100
    if abs(residual) < tolerance:
        residual = 0.0
    if sigma < tolerance:
        result.update(sigma=0.0, null_reason="zero_residual_sigma", health_codes=["zero_residual_sigma"])
    result.update(resid=residual, resid_z=residual / sigma if sigma >= tolerance else None)
    return result


def residual_series(y, factors, *, minimum=60, window=120):
    return [fit_predict(y, factors, signal_index=i, minimum=minimum, window=window)["resid"] for i in range(len(y))]
