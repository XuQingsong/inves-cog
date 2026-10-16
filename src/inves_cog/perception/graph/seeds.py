"""Reviewed seed definitions are data; primary themes do not follow LLM guesses."""

from copy import deepcopy
from pathlib import Path

import yaml

L3 = {
    "hdd": ("HDD", "WDC STX", "SMH"),
    "memory": ("NAND / DRAM / HBM", "SNDK MU SKHY", "SMH"),
    "semi_equipment": ("半导体设备", "AMAT LRCX KLAC ASML", "SOXX"),
    "cpu": ("CPU", "AMD INTC ARM QCOM", "SOXX"),
    "ai_accelerators": ("AI 加速芯片", "NVDA AMD AVGO MRVL", "SMH"),
    "ai_network": ("AI 网络与光", "ANET CIEN COHR LITE AVGO MRVL", "SMH"),
    "dc_power": ("数据中心电力", "VRT ETN GEV CEG BE", "XLU/XLI"),
    "ai_servers": ("AI 服务器", "DELL SMCI", "XLK"),
    "cloud": ("云厂商", "MSFT GOOGL AMZN META ORCL", "QQQ"),
    "openai_partners": ("OpenAI 合作方", "MSFT ORCL NVDA AMD AVGO CRWV", "QQQ"),
    "enterprise_software": ("企业软件", "MSFT ORCL CRM NOW ADBE PLTR", "IGV"),
    "cybersecurity": ("网络安全", "CRWD PANW FTNT ZS", "IGV"),
}
PRIMARY = {
    "hdd": "WDC STX",
    "memory": "SNDK MU SKHY",
    "semi_equipment": "AMAT LRCX KLAC ASML",
    "cpu": "INTC ARM QCOM",
    "ai_accelerators": "NVDA AMD AVGO MRVL",
    "ai_network": "ANET CIEN COHR LITE",
    "dc_power": "VRT ETN GEV CEG BE",
    "ai_servers": "DELL SMCI",
    "cloud": "GOOGL AMZN META",
    "openai_partners": "CRWV",
    "enterprise_software": "MSFT ORCL CRM NOW ADBE PLTR",
    "cybersecurity": "CRWD PANW FTNT ZS",
}
L2_ETF = {
    "AI 算力芯片": "SMH",
    "存储": "SMH",
    "CPU 与代工": "SOXX",
    "AI 网络与光通信": "SMH",
    "软件与平台": "IGV",
    "互联网": "XLC",
    "消费硬件与汽车": "XLY",
    "零售": "XLY",
    "医疗": "XLV",
    "金融与支付": "XLF",
    "能源": "XLE",
    "工业": "XLI",
    "半导体设备": "SOXX",
    "数据中心电力与散热": "XLU/XLI",
    "AI 服务器与算力云": "XLK",
    "网络安全": "IGV",
}


def initial_baskets(universe, *, effective_from="2015-01-01"):
    definitions = deepcopy(L3)
    chain = set("TSM".split())
    for name in ("ai_accelerators", "ai_network", "hdd", "memory", "dc_power", "ai_servers"):
        chain.update(definitions[name][1].split())
    definitions["ai_capex_chain"] = ("AI 资本开支链", " ".join(sorted(chain)), "SMH")
    primaries = {ticker: name for name, symbols in PRIMARY.items() for ticker in symbols.split()}
    sectors = {}
    for entity in universe:
        sectors.setdefault(entity["sector"], []).append(entity["ticker"])
    result = []
    for index, (sector, tickers) in enumerate(sectors.items()):
        result.append(
            {
                "basket_id": f"l2_{index:02d}",
                "level": "L2",
                "name": sector,
                "benchmark": L2_ETF[sector],
                "members": [
                    {
                        "ticker": t,
                        "weight": 1 / len(tickers),
                        "primary": True,
                        "effective_from": effective_from,
                        "effective_to": None,
                    }
                    for t in tickers
                ],
                "factor_basis": {"kind": "market_only"},
            }
        )
    sector_by_ticker = {row["ticker"]: row["sector"] for row in universe}
    for identifier, (name, symbols, benchmark) in definitions.items():
        tickers = symbols.split()
        parents = {sector_by_ticker[t] for t in tickers}
        basis = (
            {"kind": "l2", "sector": next(iter(parents))}
            if len(parents) == 1
            else {"kind": "benchmark", "tickers": benchmark.split("/")}
        )
        result.append(
            {
                "basket_id": identifier,
                "level": "L3",
                "name": name,
                "benchmark": benchmark,
                "factor_basis": basis,
                "members": [
                    {
                        "ticker": t,
                        "weight": 1 / len(tickers),
                        "primary": primaries.get(t) == identifier,
                        "effective_from": effective_from,
                        "effective_to": None,
                    }
                    for t in tickers
                ],
            }
        )
    return result


def monitored_seed(path=None):
    path = Path(path) if path else Path(__file__).resolve().parents[4] / "config/monitored_entities.yaml"
    rows = yaml.safe_load(path.read_text())["entities"]
    rows.append(
        {
            "entity_id": "toshiba",
            "name": "Toshiba",
            "aliases": ["东芝"],
            "kind": "private_company",
            "trend_keywords": ["Toshiba HDD"],
            "official_urls": ["https://www.global.toshiba/ww/news/corporate.html"],
        }
    )
    return rows
