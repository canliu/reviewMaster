"""Generate `sample_orders_p4.xlsx` — companion to the P3 sample for
demonstrating cross-shop repeat detection.

Re-run with:
    docker compose exec backend python tests/fixtures/generate_sample_p4.py

Upload BOTH `sample_orders.xlsx` (P3) and `sample_orders_p4.xlsx` (P4),
then in the header shop switcher pick "All shops · US (2)" to see the
cross-shop view. The interesting cases:

- Alice (alice@example.com) bought ASIN A1 three times on P3 and twice
  more on P4 → 5 repeat orders pooled under `all:US`.
- Alice bought ASIN A2 once on each shop → singleton in each per-shop
  view, but a repeat in `all:US` (cross-shop-only repeat).
- Frank (frank@example.com) bought ASIN A1 twice on P4 — a normal
  same-shop repeat.
- Greg (greg@example.com) bought ASIN A2 twice on P4 — same.

Under `p3:US` alone: 3 repeat orders. Under `p4:US` alone: 6.
Under `all:US`: 11 (5+2+2+2). The two extra ones over the sum (3+6=9)
are the cross-shop-only Alice+A2 pair.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

OUTPUT = Path(__file__).parent / "sample_orders_p4.xlsx"

HEADERS = [
    "店铺/站点",
    "订单编号",
    "ASIN",
    "MSKU",
    "SKU",
    "SPU",
    "产品名称",
    "父产品名称",
    "商品标题",
    "订单类型",
    "买家邮箱",
    "订购时间（零时区）",
    "发货时间（零时区）",
    "预计到达时间（零时区）",
    "商品售价",
    "币种",
    "发货数量",
    "收货城市",
    "收货地区",
    "收货国家/地区",
    "追踪号码",
    "承运人",
    "备注",
    "仓库",
]

BASE_TIME = datetime(2025, 3, 1, 12, 0)  # offset from P3 base so timelines interleave


def _row(
    order_id: str,
    asin: str,
    spu: str,
    product: str,
    email: str | None,
    city: str | None,
    state: str | None,
    country: str | None,
    price: float,
    qty: int,
    day_offset: int,
    shop: str = "p4:US",
) -> dict[str, object]:
    return {
        "店铺/站点": shop,
        "订单编号": order_id,
        "ASIN": asin,
        "MSKU": f"M-{asin}",
        "SKU": f"K-{asin}",
        "SPU": spu,
        "产品名称": product,
        "父产品名称": product.split(" ")[0],
        "商品标题": f"{product} — single",
        "订单类型": "Standard",
        "买家邮箱": email,
        "订购时间（零时区）": BASE_TIME + timedelta(days=day_offset),
        "发货时间（零时区）": BASE_TIME + timedelta(days=day_offset, hours=8),
        "预计到达时间（零时区）": BASE_TIME + timedelta(days=day_offset + 3),
        "商品售价": price,
        "币种": "USD",
        "发货数量": qty,
        "收货城市": city,
        "收货地区": state,
        "收货国家/地区": country,
        "追踪号码": f"TRK-{order_id}",
        "承运人": "FedEx",
        "备注": "",
        "仓库": "FBA",
    }


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        # --- Alice (overlaps with P3 Alice — cross-shop merging here) ---
        _row("P4-O1", "A1", "S-WIDGET", "Widget A1",
             "alice@example.com", "Austin", "TX", "US", 9.99, 1, 0),
        _row("P4-O2", "A2", "S-GADGET", "Gadget A2",
             "alice@example.com", "Austin", "TX", "US", 14.50, 1, 8),
        _row("P4-O3", "A4", "S-GIZMO", "Gizmo A4",
             "alice@example.com", "Austin", "TX", "US", 24.00, 1, 16),
        _row("P4-O10", "A1", "S-WIDGET", "Widget A1",
             "alice@example.com", "Austin", "TX", "US", 9.99, 1, 50),

        # --- Frank — 2 orders of A1, same-shop repeat on P4 ---
        _row("P4-O4", "A1", "S-WIDGET", "Widget A1",
             "frank@example.com", "Fresno", "CA", "US", 9.99, 1, 5),
        _row("P4-O5", "A1", "S-WIDGET", "Widget A1",
             "frank@example.com", "Fresno", "CA", "US", 9.99, 1, 20),

        # --- Greg — 2 orders of A2, same-shop repeat on P4 ---
        _row("P4-O6", "A2", "S-GADGET", "Gadget A2",
             "greg@example.com", "Gainesville", "FL", "US", 14.50, 1, 12),
        _row("P4-O7", "A2", "S-GADGET", "Gadget A2",
             "greg@example.com", "Gainesville", "FL", "US", 14.50, 2, 28),

        # --- Henry — singleton on P4 ---
        _row("P4-O8", "A1", "S-WIDGET", "Widget A1",
             "henry@example.com", "Houston", "TX", "US", 9.99, 1, 35),

        # --- Iris — singleton on a different ASIN ---
        _row("P4-O9", "A4", "S-GIZMO", "Gizmo A4",
             "iris@example.com", "Indianapolis", "IN", "US", 24.00, 1, 45),
    ]

    df = pd.DataFrame(rows, columns=HEADERS)
    with pd.ExcelWriter(OUTPUT, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="配送信息", index=False)
    print(f"wrote {OUTPUT} ({len(rows)} rows × {len(HEADERS)} cols)")


if __name__ == "__main__":
    main()
