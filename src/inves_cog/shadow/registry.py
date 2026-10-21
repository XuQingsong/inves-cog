"""Append-only factor definitions; a changed definition creates another version."""

import json
from copy import deepcopy

from inves_cog.shadow.settings import settings

INPUTS = {
    "F-01": [
        "M3.growth",
        "M2.rev_growth",
        "M3.ps",
        "M3.pe",
        "M2.eps_growth",
        "M2.prev_eps_ttm",
        "M2.prev_net_margin",
        "M3.fcf_yield",
    ],
    "F-02": [
        "M3.quality",
        "M3.growth",
        "M2.rev_accel_pp",
        "M2.rev_q_yoy",
        "M2.gross_margin_change_pp",
        "M2.fcf_margin_change_pp",
        "M2.ni_ttm",
    ],
    "F-03": ["M3.growth_subitems", "M2.consensus_snapshot.eps_cy", "M2.fy_cy", "captured_at", "as_of"],
    "F-04": ["M3.quality_subitems", "M2.segments.revenue", "M2.margin_pct", "M2.recast_group", "filed", "period_end"],
    "F-05": ["M3.growth_subitems", "M2.segments.revenue", "M2.yoy_pct", "M2.recast_group", "filed", "period_end"],
    "F-06": ["M4.tier", "rule_a.cap", "M3.vol60", "M3.vol20", "M4.plan.notional_est"],
    "F-07": ["M5.shadow_rules.vt1", "M5.vt2", "M5.version", "M5.observed_at"],
    "F-08": [
        "M4.price_sell",
        "M4.holding_id",
        "M4.equity",
        "M6.shock_flag",
        "M6.resid_5d_z",
        "M1.earnings_events",
        "M2.S1_inputs",
    ],
}

DEFINITIONS = (
    ("F-01", "成长调整估值分B1；PSG50/EPS增长调整PE30/FCF收益率20；缺项重配", "估值账/M31", "高PE成长股买入路径"),
    ("F-02", "拐点质量B2；毛利率变化40/FCF率变化40/TTM净利20，含持有滞回", "质量账/M50质量线", "衡量经营改善"),
    ("F-03", "当年EPS共识30日修订，权重15，其余成长项85；2027-04-08前只记录", "成长账", "纳入一致预期修订"),
    ("F-04", "四季收入最大核心分部利润率同比pp变化，权重15，其余质量项85", "质量账", "识别主营盈利改善"),
    ("F-05", "同一核心分部收入同比，营收曲线，权重20，其余成长项80", "成长账", "识别核心业务增长"),
    ("F-06", "B9目标波动/vol60，缺时vol20，系数限0.5–1；只缩小首笔/加仓", "仓位", "限制单票风险"),
    ("F-07", "只引用M5已发布V-T1/V-T2，保留来源版本，不重算", "门槛/仓位", "估值位置影子对照"),
    ("F-08", "S10四条件及M50/S4/权益浮亏硬线排除；同持仓同冲击一次", "价格型卖出", "系统性冲击止损复核影子"),
)


class Registry:
    def __init__(self):
        self.versions = {}
        self.daily = []

    def initial_definitions(self):
        return [
            {
                "factor_id": key,
                "version": "v1",
                "definition": text
                + "；参数="
                + json.dumps(
                    settings().get("s10" if key == "F-08" else "f" + key[-2:], {}), sort_keys=True, ensure_ascii=False
                ),
                "inputs": INPUTS[key],
                "pit_note": "filed/observed_at/captured_at不晚于cutoff，缺失保留NULL及原因",
                "target": target,
                "rationale": reason,
                "source": "system-spec §§10.3,10.4,13.7",
                "expected_direction": "仅影子；改善账本或收紧风险",
                "status": "影子计算",
            }
            for key, text, target, reason in DEFINITIONS
        ]

    def register(self, factor_id, definition, *, at):
        rows = self.versions.setdefault(factor_id, [])
        comparable = deepcopy(definition)
        if rows and rows[-1]["definition_payload"] == comparable:
            return deepcopy(rows[-1])
        row = {
            "factor_id": factor_id,
            "version": f"v{len(rows) + 1}",
            "definition_payload": comparable,
            "created_at": at.isoformat(),
            "status": "影子计算",
        }
        rows.append(row)
        return deepcopy(row)

    def record(self, row):
        self.daily.append(deepcopy(row))
