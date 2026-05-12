"""Generate `sample_orders.xlsx` — the 10-row fixture for test_upload.py.

Re-run when the column map or test expectations change:
    docker compose exec backend python tests/fixtures/generate_sample.py
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

OUTPUT = Path(__file__).parent / "sample_orders.xlsx"

# Headers in exact order the tests inspect (mapped columns first, then a few
# filler columns to verify `raw_json` keeps the unmapped ones).
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
    # Filler — must survive into raw_json untouched.
    "备注",
    "仓库",
]

# Naive datetime — Excel cells can't store tz info. The column is conventionally
# UTC ("零时区"), and the worker treats naive timestamps as UTC.
BASE_TIME = datetime(2025, 1, 1, 12, 0)


def _row(
    shop: str,
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
        "商品标题": f"{product} — 1 pack",
        "订单类型": "Standard",
        "买家邮箱": email,
        "订购时间（零时区）": BASE_TIME + timedelta(days=day_offset),
        "发货时间（零时区）": BASE_TIME + timedelta(days=day_offset, hours=6),
        "预计到达时间（零时区）": BASE_TIME + timedelta(days=day_offset + 3),
        "商品售价": price,
        "币种": "USD" if shop != "p3:UK" else "GBP",
        "发货数量": qty,
        "收货城市": city,
        "收货地区": state,
        "收货国家/地区": country,
        "追踪号码": f"TRK-{order_id}",
        "承运人": "USPS",
        "备注": "",
        "仓库": "FBA",
    }


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    rows = [
        # Alice + A1 — 3 orders → repeat
        _row("p3:US", "O1", "A1", "S-WIDGET", "Widget A1",
             "alice@example.com", "Austin", "TX", "US", 9.99, 1, 0),
        _row("p3:US", "O2", "A1", "S-WIDGET", "Widget A1",
             "alice@example.com", "Austin", "TX", "US", 9.99, 1, 10),
        _row("p3:US", "O3", "A2", "S-GADGET", "Gadget A2",
             "alice@example.com", "Austin", "TX", "US", 14.50, 2, 20),
        # Bob + A1 — singleton
        _row("p3:US", "O4", "A1", "S-WIDGET", "Widget A1",
             "bob@example.com", "Boston", "MA", "US", 9.99, 1, 25),
        # No-email fallback — same Toronto address twice → repeat by address hash
        _row("p3:CA", "O5", "A1", "S-WIDGET", "Widget A1",
             None, "Toronto", "ON", "CA", 12.00, 1, 30),
        _row("p3:CA", "O6", "A1", "S-WIDGET", "Widget A1",
             None, "Toronto", "ON", "CA", 12.00, 1, 35),
        # Alice + A1 again, third time
        _row("p3:US", "O7", "A1", "S-WIDGET", "Widget A1",
             "alice@example.com", "Austin", "TX", "US", 9.99, 1, 40),
        # Dave + A2
        _row("p3:US", "O8", "A2", "S-GADGET", "Gadget A2",
             "dave@example.com", "Denver", "CO", "US", 14.50, 1, 45),
        # Eve in UK + A1
        _row("p3:UK", "O9", "A1", "S-WIDGET", "Widget A1",
             "eve@example.com", "London", "ENG", "GB", 8.50, 1, 50),
        # Alice + A3 (Doohickey)
        _row("p3:US", "O10", "A3", "S-DOO", "Doohickey A3",
             "alice@example.com", "Austin", "TX", "US", 19.99, 1, 55),
    ]

    df = pd.DataFrame(rows, columns=HEADERS)
    with pd.ExcelWriter(OUTPUT, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="配送信息", index=False)
    print(f"wrote {OUTPUT} ({len(rows)} rows × {len(HEADERS)} cols)")


if __name__ == "__main__":
    main()
