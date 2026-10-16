"""Direction checks for the four cases. Callers pass headlines; this module does not read the export."""


def openai_labels(text):
    lowered = text.lower()
    labels = set()
    if "coreweave" in lowered and any(word in lowered for word in ("yield", "debt", "bond")):
        labels.add("coreweave_debt")
    names = ("dell", "hewlett", "hpe", "netapp")
    if "barclays" in lowered and "downgrad" in lowered and any(name in lowered for name in names):
        labels.add("barclays_downgrade")
    if "cpi" in lowered and "vs" in lowered:
        labels.add("cpi_hot")
    if any(phrase in lowered for phrase in ("annualised revenue", "annualized revenue", "run rate")):
        labels.add("arr_background")
    return labels


def openai_cover(ranked):
    """Top four candidates must include at least three of the four required labels."""
    found = set()
    for row in ranked[:4]:
        found.update(row["labels"])
    required = {"coreweave_debt", "barclays_downgrade", "cpi_hot", "arr_background"}
    return len(found & required) >= 3


def muse_chart(text):
    lowered = text.lower()
    return "muse" in lowered and any(word in lowered for word in ("app store", "no. 1", "chart"))


def deepseek_source(text):
    lowered = text.lower()
    return "deepseek" in lowered and any(word in lowered for word in ("r1", "app store"))
