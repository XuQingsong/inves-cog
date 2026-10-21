"""Append-only factor definitions; a changed definition creates another version."""

from copy import deepcopy

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
                "definition": text,
                "inputs": "按M9 FR11–18既有只读输入",
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
