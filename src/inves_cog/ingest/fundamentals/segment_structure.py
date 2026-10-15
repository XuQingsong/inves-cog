"""Relationships and rendered signs from the filing, without numeric fitting."""

import re
from collections import defaultdict


def qkey(qname):
    return "{" + qname.namespaceURI + "}" + qname.localName


def member_graph(model, axis_name):
    from arelle import XbrlConst

    domains = model.relationshipSet(XbrlConst.dimensionDomain).modelRelationships
    starts = [
        r
        for r in domains
        if r.fromModelObject is not None
        and r.toModelObject is not None
        and r.fromModelObject.qname.localName == axis_name
    ]
    graph = defaultdict(set)
    evidence = defaultdict(list)
    members = set()
    roles = set()
    for start in starts:
        role = start.targetRole or start.linkrole
        pending = [(start.toModelObject, role)]
        seen = set()
        while pending:
            node, role = pending.pop()
            if (node, role) in seen:
                continue
            seen.add((node, role))
            for rel in model.relationshipSet(XbrlConst.domainMember, role).fromModelObject(node):
                target = rel.toModelObject
                if target is None:
                    continue
                graph[qkey(node.qname)].add(qkey(target.qname))
                members.add(qkey(target.qname))
                roles.add(rel.linkrole)
                evidence[(qkey(node.qname), qkey(target.qname))].append(rel.linkrole)
                pending.append((target, rel.targetRole or rel.linkrole))
    return graph, members, roles, evidence


def descendants(graph, node):
    pending = list(graph.get(node, ()))
    seen = set()
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        pending.extend(graph.get(current, ()))
    return seen


def inline_positions(primary_html):
    if not primary_html:
        return {}
    from lxml import html

    try:
        document = html.fromstring(primary_html.encode("utf-8") if isinstance(primary_html, str) else primary_html)
    except (ValueError, TypeError):
        return {}
    result = defaultdict(list)
    for table_id, table in enumerate(document.iter("table")):
        section = 0
        section_text = ""
        row_id = 0
        for row in table.iter("tr"):
            if next(row.iterancestors("table"), None) is not table:
                continue
            cells = [node for node in row if node.tag.lower() in {"td", "th"}]
            row_facts = [
                node for node in row.iter() if isinstance(node.tag, str) and node.tag.lower().endswith("nonfraction")
            ]
            nonempty = [" ".join(cell.text_content().split()) for cell in cells if cell.text_content().strip()]
            if not row_facts and len(nonempty) == 1:
                section += 1
                section_text = nonempty[0][:160]
            column = 0
            for cell in cells:
                displayed = " ".join(cell.text_content().split())
                span = int(cell.get("colspan", "1"))
                facts = [
                    node
                    for node in cell.iter()
                    if isinstance(node.tag, str) and node.tag.lower().endswith("nonfraction")
                ]
                for node in facts:
                    context = node.get("contextref")
                    name = node.get("name")
                    if context and name:
                        negative = bool(
                            re.search(r"\(\s*[$€£]?\s*[\d,.]+\s*\)", displayed)
                        ) or displayed.lstrip().startswith("-")
                        result[(context, name)].append(
                            {
                                "table": table_id,
                                "section": section,
                                "column": column,
                                "column_end": column + span,
                                "row": row_id,
                                "displayed": displayed[:120],
                                "negative": negative,
                                "row_label": nonempty[0][:160] if nonempty else "",
                                "section_label": section_text,
                            }
                        )
                column += span
            row_id += 1
    return dict(result)


def calculation_components(model, total_fact, revenue_names):
    """Explicit non-core revenue children in the same original calculation."""
    from arelle import XbrlConst

    candidates = defaultdict(list)
    relations = model.relationshipSet(XbrlConst.summationItems).fromModelObject(total_fact.concept)
    # A separate standard revenue child establishes the core component. Its
    # siblings can be outside that core; decomposition children alone cannot.
    core_roles = {
        rel.linkrole
        for rel in relations
        if rel.toModelObject is not None and rel.toModelObject.qname.localName in revenue_names
    }
    for rel in relations:
        if rel.linkrole not in core_roles:
            continue
        concept = rel.toModelObject
        if concept is None or not concept.isMonetary or concept.qname.localName in revenue_names:
            continue
        if not re.search(r"Revenue|Sales", concept.qname.localName):
            continue
        for fact in model.factsByQname.get(concept.qname, ()):
            if fact.context is None or fact.context.qnameDims or fact.unit is None:
                continue
            if not fact.context.isEqualTo(total_fact.context) or not fact.unit.isEqualTo(total_fact.unit):
                continue
            candidates[qkey(concept.qname)].append((fact, rel.weight, rel.linkrole, rel.arcrole))
    output = []
    for values in candidates.values():
        if len({(weight, role) for _, weight, role, _ in values}) != 1:
            continue
        fact, weight, role, arcrole = min(values, key=lambda item: item[0].context.id)
        output.append(
            (
                fact,
                weight,
                {
                    "method": "original_calculation_arc",
                    "linkrole": role,
                    "arcrole": arcrole,
                    "from": qkey(total_fact.qname),
                    "to": qkey(fact.qname),
                    "context_ref": fact.context.id,
                },
            )
        )
    return output


def plain_reconciliations(model, primary_html, rows, total_fact, components, period):
    """Read a labeled original corporate revenue row with period/unit anchors.

    The original monetary XBRL component anchors the table's scale. Neither a
    residual against consolidated revenue nor a searched numeric fit is used.
    """
    if not primary_html or not components:
        return []
    from lxml import html

    document = html.fromstring(primary_html.encode("utf-8") if isinstance(primary_html, str) else primary_html)
    start, end = period
    months = "Three" if 80 <= (end - start).days <= 100 else "Twelve" if 350 <= (end - start).days <= 380 else None
    if months is None:
        return []

    def normalized(text):
        return " ".join(text.split()).casefold()

    def labels(concept):
        return {
            normalized(concept.label()),
            normalized(concept.label(preferredLabel="http://www.xbrl.org/2003/role/terseLabel")),
        }

    concepts = {qkey(q): c for q, c in model.qnameConcepts.items()}
    targets = {
        r["evidence"]["member_identity"]: labels(concepts[r["evidence"]["member_identity"]])
        for r in rows
        if r["axis"] == "elimination"
        and r["evidence"].get("revenue_disclosure") == "profit_only"
        and r["evidence"]["member_identity"] in concepts
    }
    output = []
    for table_id, table in enumerate(document.iter("table")):
        table_rows = []
        years = []
        groups = []
        for row_id, row in enumerate(table.iter("tr")):
            if next(row.iterancestors("table"), None) is not table:
                continue
            texts = [" ".join(c.text_content().split()) for c in row if c.tag.lower() in {"td", "th"}]
            current_years = [int(t) for t in texts if re.fullmatch(r"20\d{2}", t)]
            if current_years:
                years = current_years
            found = re.findall(r"(Three|Six|Nine|Twelve) months ended\s+([A-Za-z]+\s+\d{1,2})", " ".join(texts), re.I)
            if found:
                groups = found
            if texts:
                table_rows.append((row_id, next((t for t in texts if t), ""), texts))
        if not years or not groups or len(years) % len(groups):
            continue
        width = len(years) // len(groups)
        columns = [
            i
            for i, y in enumerate(years)
            if y == end.year
            and normalized(groups[i // width][0]) == months.lower()
            and normalized(groups[i // width][1]) == normalized(end.strftime("%B") + " " + str(end.day))
        ]
        if len(columns) != 1:
            continue
        column = columns[0]
        amounts = []
        for row_id, label, texts in table_rows:
            values = []
            for text in texts[1:]:
                value = text.replace(",", "").replace("$", "").strip()
                if re.fullmatch(r"\(?-?\d+(?:\.\d+)?\)?", value):
                    values.append(
                        -float(value[1:-1]) if value.startswith("(") and value.endswith(")") else float(value)
                    )
            if len(values) == len(years):
                amounts.append((row_id, label, values[column]))
        for member, member_labels in targets.items():
            matched = [r for r in amounts if normalized(r[1]) in {label + " revenue" for label in member_labels}]
            if len(matched) != 1:
                continue
            for anchor, _weight, arc in components:
                anchors = [r for r in amounts if normalized(r[1]) in labels(anchor.concept)]
                if len(anchors) != 1 or anchors[0][2] == 0 or anchor.isNil:
                    continue
                scale = float(anchor.value) / anchors[0][2]
                if scale not in {1, 1000, 1000000, 1000000000}:
                    continue
                row_id, label, amount = matched[0]
                output.append(
                    (
                        member,
                        anchor,
                        amount * scale,
                        {
                            "method": "original_labeled_reconciliation_table",
                            "table": table_id,
                            "row": row_id,
                            "row_label": label,
                            "amount": amount,
                            "scale": scale,
                            "year_column": column,
                            "period_header": groups[column // width],
                            "unit_anchor": arc,
                            "unit_anchor_display": anchors[0][2],
                        },
                    )
                )
                break
    # Ambiguous or repeated source rows must not silently choose one.
    return [item for item in output if sum(other[0] == item[0] for other in output) == 1]


def fact_positions(positions, fact):
    if fact is None:
        return []
    return positions.get((fact.context.id, str(fact.qname)), [])


def same_column(*positions):
    return len({(p["table"], p["section"]) for p in positions}) == 1 and max(p["column"] for p in positions) < min(
        p["column_end"] for p in positions
    )


def rendered_weight(fact, positions, *, subtotal_positions=(), total_positions=(), member=None):
    value = float(fact.value) if not fact.isNil else None
    locations = fact_positions(positions, fact)
    if value is None:
        return 1, {"reason": "reported_nil"}
    if value > 0 and any(p["negative"] for p in locations):
        return -1, {
            "method": "original_cell_parentheses",
            "context_ref": fact.context.id,
            "positions": [p for p in locations if p["negative"]],
        }
    if value > 0 and member == "IntersegmentEliminationMember":
        for position in locations:
            for subtotal in subtotal_positions:
                for total in total_positions:
                    if (
                        same_column(position, subtotal, total)
                        and subtotal["row"] < position["row"] < total["row"]
                        and re.search(r"\bnet\b", total["row_label"], re.I)
                    ):
                        return -1, {
                            "method": "original_gross_intersegment_net_rows",
                            "row_label": total["row_label"],
                            "context_ref": fact.context.id,
                            "positions": [subtotal, position, total],
                        }
    return 1, {"method": "original_signed_value", "context_ref": fact.context.id}
