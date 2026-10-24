-- Both POS vendors as one set of lines, counted in base units and split
-- into amounts with and without VAT. Shelf prices include VAT, so the
-- amount before VAT is the paid amount divided by (1 + rate). Nothing is
-- rounded here; how to round is a reporting decision, not a fact.
{%- set columns = [
    'pos_vendor', 'receipt_no', 'line_no', 'store_code', 'sku_code', 'uom_code', 'qty',
    'unit_price_vnd', 'discount_vnd', 'line_amount_vnd', 'sold_at_utc', 'sold_at',
    'business_date', 'source_file'
] %}

with sales as (
    select {{ columns | join(', ') }} from {{ ref('stg_pos_a__sales_lines') }}
    union all
    select {{ columns | join(', ') }} from {{ ref('stg_pos_b__sales_lines') }}
),

uoms as (
    select sku_code, uom_code, factor_to_base from {{ ref('stg_erp__sku_uoms') }}
),

skus as (
    select sku_code, vat_rate from {{ ref('stg_erp__skus') }}
)

select
    {{ dbt.concat(["sales.pos_vendor", "'-'", "sales.receipt_no", "'-'", "cast(sales.line_no as " ~ dbt.type_string() ~ ")"]) }} as sales_line_id,
    sales.pos_vendor,
    sales.receipt_no,
    sales.line_no,
    sales.store_code,
    sales.sku_code,
    sales.business_date,
    sales.sold_at,
    sales.sold_at_utc,
    sales.uom_code,
    sales.qty,
    sales.qty * uoms.factor_to_base as qty_base,
    cast(skus.vat_rate as decimal(5, 4)) as vat_rate,
    sales.unit_price_vnd as unit_price_incl_vat,
    sales.qty * sales.unit_price_vnd as gross_incl_vat,
    sales.discount_vnd as discount_incl_vat,
    sales.line_amount_vnd as amount_incl_vat,
    cast(sales.qty * sales.unit_price_vnd / (1 + skus.vat_rate) as decimal(18, 4)) as gross_excl_vat,
    cast(sales.discount_vnd / (1 + skus.vat_rate) as decimal(18, 4)) as discount_excl_vat,
    cast(sales.line_amount_vnd / (1 + skus.vat_rate) as decimal(18, 4)) as amount_excl_vat,
    sales.source_file
from sales
inner join uoms
    on sales.sku_code = uoms.sku_code
    and sales.uom_code = uoms.uom_code
inner join skus
    on sales.sku_code = skus.sku_code
