-- One row per sales line. Gross, discount and amount come both with and
-- without VAT; which ones make up revenue is decided in the semantic layer
-- (DR-002, DR-006).
select
    sales_line_id,
    pos_vendor,
    receipt_no,
    line_no,
    store_code,
    sku_code,
    business_date,
    sold_at,
    uom_code,
    qty,
    qty_base,
    vat_rate,
    unit_price_incl_vat,
    gross_incl_vat,
    discount_incl_vat,
    amount_incl_vat,
    gross_excl_vat,
    discount_excl_vat,
    amount_excl_vat
from {{ ref('int_sales_lines') }}
