"""Generate `sample_orders_p4.xlsx` — companion to the P3 sample for
demonstrating cross-shop repeat detection.

Re-run with:
    docker compose exec backend python tests/fixtures/generate_sample_p4.py

Design (20 rows, all on `p4:US` so they pool with `p3:US` under `all:US`):

  • Rows 1–10 — same email + same ASIN as a P3 order. Other columns (order_id,
    prices, ship addresses, dates, carrier) are different. These produce
    cross-shop product-level repeats:
       alice@ + A1 — 3 P4 orders × 3 P3 orders = 6 repeat rows
       alice@ + A2 — 2 P4 × 1 P3 = 3 repeat rows
       alice@ + A3 — 1 P4 × 1 P3 = 2 repeat rows  (cross-shop-only!)
       bob@   + A1 — 2 P4 × 1 P3 = 3 repeat rows
       dave@  + A2 — 2 P4 × 1 P3 = 3 repeat rows
                                     -----
                                  17 repeat rows under `all:US`

  • Rows 11–20 — same email as a P3 order, NEW ASIN (A5–A8 are P4-only).
    Each (buyer, asin) pair is a singleton across the entire dataset, so
    these rows do **not** appear in the repeat-orders list. They surface
    only in the buyer-history slide-over (proof that buyer matching works
    without inflating product-level repeats).

Per-scope counts to expect:
    p3:US alone  →  3 repeat rows (Alice+A1 × 3)
    p4:US alone  →  9 repeat rows  (Alice+A1 × 3, +A2 × 2, Bob+A1 × 2, Dave+A2 × 2)
    all:US       → 17 repeat rows  (cross-shop magnification: +5)
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

# Offset from P3 base (2025-01-01) so timelines interleave.
BASE_TIME = datetime(2025, 3, 1, 12, 0)


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
    carrier: str = "FedEx",
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
        "承运人": carrier,
        "备注": "",
        "仓库": "FBA",
    }


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    # -- Block A: same email + same ASIN as P3.  Other columns differ. --
    block_a = [
        # alice + A1 (Widget) — P3 has 3 of these; P4 adds 3 more.
        _row("P4-A1", "A1", "S-WIDGET", "Widget A1",
             "alice@example.com", "Houston", "TX", "US", 11.99, 1, 1),
        _row("P4-A2", "A1", "S-WIDGET", "Widget A1",
             "alice@example.com", "Dallas", "TX", "US", 11.99, 2, 7),
        _row("P4-A3", "A1", "S-WIDGET", "Widget A1",
             "alice@example.com", "San Antonio", "TX", "US", 11.99, 1, 14),
        # alice + A2 (Gadget) — P3 has 1; P4 adds 2.
        _row("P4-A4", "A2", "S-GADGET", "Gadget A2",
             "alice@example.com", "Plano", "TX", "US", 16.50, 1, 21,
             carrier="UPS"),
        _row("P4-A5", "A2", "S-GADGET", "Gadget A2",
             "alice@example.com", "Frisco", "TX", "US", 16.50, 1, 28,
             carrier="UPS"),
        # alice + A3 (Doohickey) — P3 has 1; P4 adds 1. Cross-shop-only repeat.
        _row("P4-A6", "A3", "S-DOO", "Doohickey A3",
             "alice@example.com", "Austin", "TX", "US", 22.00, 1, 35),
        # bob + A1 — P3 has 1; P4 adds 2.
        _row("P4-A7", "A1", "S-WIDGET", "Widget A1",
             "bob@example.com", "Cambridge", "MA", "US", 10.99, 1, 4,
             carrier="UPS"),
        _row("P4-A8", "A1", "S-WIDGET", "Widget A1",
             "bob@example.com", "Worcester", "MA", "US", 10.99, 1, 18),
        # dave + A2 — P3 has 1; P4 adds 2.
        _row("P4-A9", "A2", "S-GADGET", "Gadget A2",
             "dave@example.com", "Boulder", "CO", "US", 15.99, 1, 10),
        _row("P4-A10", "A2", "S-GADGET", "Gadget A2",
             "dave@example.com", "Aurora", "CO", "US", 15.99, 2, 24,
             carrier="UPS"),
    ]

    # -- Block B: same email as P3, NEW ASIN (P4-only). Each pair is unique. --
    # A5–A8 are P4-introduced products; none appear in P3.
    block_b = [
        _row("P4-B1", "A5", "S-SPROCKET", "Sprocket A5",
             "alice@example.com", "Austin", "TX", "US", 7.49, 1, 3),
        _row("P4-B2", "A6", "S-BRACKET", "Bracket A6",
             "alice@example.com", "Houston", "TX", "US", 12.25, 1, 9),
        _row("P4-B3", "A7", "S-LEVER", "Lever A7",
             "alice@example.com", "Dallas", "TX", "US", 18.75, 1, 16),
        _row("P4-B4", "A8", "S-PULLEY", "Pulley A8",
             "alice@example.com", "Plano", "TX", "US", 26.00, 1, 30),
        _row("P4-B5", "A5", "S-SPROCKET", "Sprocket A5",
             "bob@example.com", "Boston", "MA", "US", 7.49, 1, 6),
        _row("P4-B6", "A6", "S-BRACKET", "Bracket A6",
             "bob@example.com", "Cambridge", "MA", "US", 12.25, 1, 19),
        _row("P4-B7", "A7", "S-LEVER", "Lever A7",
             "bob@example.com", "Brookline", "MA", "US", 18.75, 1, 32),
        _row("P4-B8", "A5", "S-SPROCKET", "Sprocket A5",
             "dave@example.com", "Denver", "CO", "US", 7.49, 1, 13),
        _row("P4-B9", "A6", "S-BRACKET", "Bracket A6",
             "dave@example.com", "Lakewood", "CO", "US", 12.25, 1, 26),
        _row("P4-B10", "A7", "S-LEVER", "Lever A7",
             "dave@example.com", "Aurora", "CO", "US", 18.75, 1, 38),
    ]

    rows = block_a + block_b

    df = pd.DataFrame(rows, columns=HEADERS)
    with pd.ExcelWriter(OUTPUT, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="配送信息", index=False)
    print(f"wrote {OUTPUT} ({len(rows)} rows × {len(HEADERS)} cols)")


if __name__ == "__main__":
    main()
