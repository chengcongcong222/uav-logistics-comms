"""Export internal Q2 results to official submission template layout (new file)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl import Workbook

from src.common.paths import PROCESSED_DIR, RESULTS_Q2


def main() -> None:
    sorties = pd.read_csv(RESULTS_Q2 / "q2_sorties.csv")
    boxes = pd.read_csv(RESULTS_Q2 / "q2_box_delivery.csv")
    nodes = pd.read_csv(PROCESSED_DIR / "nodes.csv")
    xy = nodes.set_index("node_id")[["x_m", "y_m"]]

    out = RESULTS_Q2 / "Q2_submission.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Q2_运输架次"
    ws.append(
        [
            "架次编号",
            "无人机编号",
            "机型",
            "电池编号",
            "准备开始时刻(s)",
            "起飞时刻(s)",
            "访问服务区顺序",
            "返回O01时刻(s)",
            "能耗(kWh)",
            "能源裕量(kWh)",
            "箱数",
            "初始载荷(kg)",
        ]
    )
    for r in sorties.itertuples():
        ws.append(
            [
                r.sortie_id,
                r.uav_id,
                r.uav_type,
                r.battery_id,
                r.preparation_start_s,
                r.takeoff_s,
                r.service_sequence,
                r.return_s,
                r.energy_kwh,
                r.energy_margin_kwh,
                r.n_boxes,
                r.payload_kg,
            ]
        )

    ws2 = wb.create_sheet("Q2_逐箱交付")
    ws2.append(
        [
            "货箱编号",
            "架次编号",
            "服务区",
            "交付时刻(s)",
            "期望送达时间(s)",
            "首批截止时间(s)",
            "硬时限(s)",
            "硬时限满足",
            "归一化送达时间",
        ]
    )
    for r in boxes.itertuples():
        ws2.append(
            [
                r.box_id,
                r.sortie_id,
                r.service_id,
                r.delivery_time_s,
                r.expected_deadline_s,
                r.first_deadline_s,
                r.hard_deadline_s,
                bool(r.hard_deadline_ok),
                r.normalized_delivery_time,
            ]
        )

    wb.save(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
