"""Weekly conservative complete-linkage suggestions; never activate a basket."""

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform


def suggestions(returns, *, existing):
    frame = returns.tail(60).dropna(axis=1)
    if len(frame) < 60 or frame.shape[1] < 3:
        return []
    correlation = frame.corr()
    valid = correlation.columns[correlation.notna().all()]
    correlation = correlation.loc[valid, valid]
    if len(valid) < 3:
        return []
    distances = np.clip(1 - correlation.to_numpy(), 0, 2)
    np.fill_diagonal(distances, 0)
    tree = linkage(squareform(distances, checks=False), method="complete")
    labels = fcluster(tree, t=np.nextafter(0.4, 0), criterion="distance")
    result = []
    for label in sorted(set(labels)):
        members = sorted(valid[labels == label])
        if len(members) < 3:
            continue
        current = set(members)
        overlap = []
        for basket in existing:
            other = {row if isinstance(row, str) else row["ticker"] for row in basket["members"]}
            overlap.append(len(current & other) / len(current | other) if current | other else 0)
        if any(value >= 0.5 for value in overlap):
            continue
        result.append({"name": "未命名篮子", "members": members, "status": "候选"})
    return result
