"""A systemic tag needs a level-1 or level-2 citation. Otherwise the rule writes 无."""


def resolve_systemic_tag(tag, info_ids, sources):
    if any(sources.get(item) in (1, 2) for item in info_ids):
        return tag
    return "无"
