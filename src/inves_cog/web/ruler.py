"""Price ruler. Same lane rules as the investor prototype."""

from html import escape

LANES = {"t0": 32, "t1": 19, "t2": 7, "b0": 78, "b1": 92, "b2": 106}
PREFER = {
    "cur": ["b0", "b1", "b2", "t0"],
    "cost": ["b0", "b1", "b2", "t0", "t1"],
    "ref": ["b0", "b1", "b2", "t0", "t1", "t2"],
    "stop": ["t0", "t1", "t2", "b0", "b1", "b2"],
    "tp": ["t0", "t1", "t2", "b0", "b1", "b2"],
}


def text_width(text, size=11):
    width = 0.0
    for ch in str(text):
        if "\u3000" <= ch <= "\u9fff" or "\uff00" <= ch <= "\uffef":
            width += size
        else:
            width += size * 0.61
    return width


def usd(value):
    if value is None:
        return "暂缺"
    return f"${float(value):,.2f}"


def _free(used, lane, start, end):
    return all(end + 6 < left or start > right + 6 for left, right in used[lane])


def ruler(holding, width=470):
    """SVG plus label boxes. Boxes are the text bounds used to check overlap."""
    points = []
    stop = holding.get("stop")
    if stop and stop.get("p") is not None:
        points.append({"k": "stop", "n": stop.get("n") or "止损", "p": float(stop["p"])})
    for item in holding.get("tp") or []:
        if item.get("p") is None:
            continue
        points.append(
            {
                "k": "tp",
                "n": item.get("n") or "止盈",
                "p": float(item["p"]),
                "reached": bool(item.get("reached")),
            }
        )
    kind = holding.get("type")
    ma200 = holding.get("ma200")
    if ma200 is not None and kind != "观察波段仓":
        points.append({"k": "ref", "n": "200 日线", "p": float(ma200)})
    if holding.get("cost") is not None:
        points.append({"k": "cost", "n": "成本", "p": float(holding["cost"])})
    price = holding.get("px")
    if price is None:
        return {"svg": "", "boxes": []}
    price = float(price)
    points.append({"k": "cur", "n": "现价", "p": price})
    low = min(item["p"] for item in points)
    high = max(item["p"] for item in points)
    pad = (high - low) * 0.05 or 1
    low -= pad
    high += pad
    left, right = 10, width - 10
    span = high - low or 1

    def x_of(level):
        return left + (level - low) / span * (right - left)

    axis_y = 54
    height = 112
    used = {lane: [] for lane in LANES}
    triggers = [item for item in points if item["k"] in {"stop", "tp"} and not item.get("reached")]
    nearest = None
    for item in triggers:
        distance = abs(item["p"] - price) / price if price else None
        if distance is None:
            continue
        if nearest is None or distance < nearest["d"]:
            nearest = {**item, "d": distance}
    parts = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'style="max-width:100%;height:auto" role="img" aria-label="{escape(str(holding.get("t") or ""))} 价格尺">',
        f'<line x1="{left}" y1="{axis_y}" x2="{right}" y2="{axis_y}" stroke="#E2DDD3" '
        'stroke-width="4" stroke-linecap="round"/>',
    ]
    boxes = []
    distance_text = ""
    if nearest is not None:
        color = "var(--r-hi-line)" if nearest["k"] == "stop" else "var(--tp-line)"
        x1, x2 = x_of(price), x_of(nearest["p"])
        distance = (nearest["p"] / price - 1) * 100
        parts.append(
            f'<line x1="{x1}" y1="{axis_y}" x2="{x2}" y2="{axis_y}" stroke="{color}" '
            'stroke-width="5" stroke-linecap="round" opacity=".85"/>'
        )
        label = f"{'+' if distance > 0 else '−'}{abs(distance):.1f}%"
        label_width = text_width(label)
        mid = (x1 + x2) / 2
        anchor = max(2, min(width - 2 - label_width, mid - label_width / 2))
        distance_text = (
            f'<text x="{anchor}" y="{axis_y - 8}" font-size="11" fill="{color}" font-weight="700" '
            f'paint-order="stroke" stroke="#fff" stroke-width="3">{escape(label)}</text>'
        )
        boxes.append({"x": anchor, "y": axis_y - 8 - 11, "w": label_width, "h": 11, "text": label})
    else:
        ref = next((item for item in points if item["k"] == "ref"), None)
        if ref is not None:
            x1, x2 = x_of(price), x_of(ref["p"])
            below = price < ref["p"]
            distance = (1 - price / ref["p"]) * 100 if below else (1 - ref["p"] / price) * 100
            warm = below or distance < 10
            color = "var(--r-mid-line)" if warm else "#B9B2A4"
            parts.append(
                f'<line x1="{x1}" y1="{axis_y}" x2="{x2}" y2="{axis_y}" stroke="{color}" '
                f'stroke-width="{4 if warm else 3}" stroke-dasharray="5 3" opacity=".8"/>'
            )
            label = f"已低于 200 日线 {distance:.1f}%" if below else f"再跌 {distance:.1f}% 跌破 200 日线"
            label_width = text_width(label)
            mid = (x1 + x2) / 2
            anchor = max(2, min(width - 2 - label_width, mid - label_width / 2))
            fill = "var(--r-mid)" if warm else "var(--ref)"
            weight = 700 if warm else 400
            distance_text = (
                f'<text x="{anchor}" y="{axis_y - 8}" font-size="11" fill="{fill}" font-weight="{weight}" '
                f'paint-order="stroke" stroke="#fff" stroke-width="3">{escape(label)}</text>'
            )
            boxes.append({"x": anchor, "y": axis_y - 8 - 11, "w": label_width, "h": 11, "text": label})
    ordered = []
    for item in points:
        ordered.append({**item, "x": x_of(item["p"])})
    ordered.sort(key=lambda item: (0 if item["k"] == "cur" else 1, item["x"]))
    for item in ordered:
        item["lab"] = f"{item['n']} {usd(item['p'])}{' ✓' if item.get('reached') else ''}"
        label_width = text_width(item["lab"])
        anchor = max(2, min(width - 2 - label_width, item["x"] - label_width / 2))
        lane = next((name for name in PREFER[item["k"]] if _free(used, name, anchor, anchor + label_width)), None)
        if lane is None:
            lane = PREFER[item["k"]][-1]
        used[lane].append((anchor, anchor + label_width))
        item["lane"] = lane
        item["a"] = anchor
        item["lw"] = label_width
    for item in ordered:
        color = {"stop": "var(--r-hi)", "tp": "var(--tp)", "cur": "var(--ink)"}.get(item["k"], "var(--ref)")
        lane_y = LANES[item["lane"]]
        top = item["lane"].startswith("t")
        dash = ' stroke-dasharray="2 2"' if item["k"] == "ref" else ""
        parts.append(
            f'<line x1="{item["x"]}" y1="{axis_y}" x2="{item["x"]}" y2="{lane_y + 3 if top else lane_y - 11}" '
            f'stroke="{color}" stroke-width="1"{dash} opacity=".55"/>'
        )
        if item["k"] == "ref":
            parts.append(
                f'<line x1="{item["x"]}" y1="{axis_y - 10}" x2="{item["x"]}" y2="{axis_y + 10}" '
                f'stroke="{color}" stroke-width="2" stroke-dasharray="3 2"/>'
            )
        else:
            fill = "#1F2A2A" if item["k"] == "cur" else ("#fff" if item.get("reached") else color)
            stroke = 2 if item.get("reached") else 0
            radius = 6 if item["k"] == "cur" else 4.5
            parts.append(
                f'<circle cx="{item["x"]}" cy="{axis_y}" r="{radius}" fill="{fill}" '
                f'stroke="{color}" stroke-width="{stroke}"/>'
            )
        weight = ' font-weight="700"' if item["k"] == "cur" else ""
        parts.append(
            f'<text x="{item["a"]}" y="{lane_y}" font-size="11" fill="{color}"{weight}>{escape(item["lab"])}</text>'
        )
        boxes.append({"x": item["a"], "y": lane_y - 11, "w": item["lw"], "h": 11, "text": item["lab"]})
    parts.append(distance_text)
    parts.append("</svg>")
    return {"svg": "".join(parts), "boxes": boxes}


def boxes_overlap(left, right):
    return not (
        left["x"] + left["w"] <= right["x"]
        or right["x"] + right["w"] <= left["x"]
        or left["y"] + left["h"] <= right["y"]
        or right["y"] + right["h"] <= left["y"]
    )
