-- One row per sales line. Gross, discount and amount come both with and
-- without VAT; which ones make up revenue is decided in the semantic layer
-- (DR-002, DR-006). The cost of each line uses the store's weighted average
-- cost for the SKU (DR-008).
with sales as (
    select * from {{ ref('int_sales_lines') }}
),

costs as (
    select store_code, sku_code, unit_cost_excl_vat from {{ ref('int_store_sku_costs') }}
)

select
    sales.sales_line_id,
    sales.pos_vendor,
    sales.receipt_no,
    sales.line_no,
    sales.store_code,
    sales.sku_code,
    sales.business_date,
    sales.sold_at,
    sales.uom_code,
    sales.qty,
    sales.qty_base,
    sales.vat_rate,
    sales.unit_price_incl_vat,
    sales.gross_incl_vat,
    sales.discount_incl_vat,
    sales.amount_incl_vat,
    sales.gross_excl_vat,
    sales.discount_excl_vat,
    sales.amount_excl_vat,
    costs.unit_cost_excl_vat,
    cast(sales.qty_base * costs.unit_cost_excl_vat as decimal(18, 4)) as cogs_excl_vat
from sales
left join costs
    on sales.store_code = costs.store_code
    and sales.sku_code = costs.sku_code
