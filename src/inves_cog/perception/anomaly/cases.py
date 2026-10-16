"""Case windows. The panel is cached so the four dates do not rebuild the same file."""

from inves_cog.perception.anomaly.panel import PricePanel

_PANELS = {}


def case_anomalies(fixture_dir, bars_filename, date_str):
    key = (str(fixture_dir), bars_filename)
    panel = _PANELS.get(key)
    if panel is None:
        panel = PricePanel(fixture_dir, bars_name=bars_filename)
        _PANELS[key] = panel
    return panel.detect(date_str)
