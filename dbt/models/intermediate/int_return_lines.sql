-- Returned items in base units and before VAT, with the business date of the
-- original sale when the receipt can be found. A return with no receipt, or
-- with a receipt from before the extract window, keeps a null sale date.
with returns as (
    select * from {{ ref('stg_returns__returns') }}
),

lines as (
    select * from {{ ref('stg_returns__return_lines') }}
),

uoms as (
    select sku_code, uom_code, factor_to_base from {{ ref('stg_erp__sku_uoms') }}
),

skus as (
    select sku_code, vat_rate from {{ ref('stg_erp__skus') }}
),

sale_receipts as (
    select
        receipt_no,
        min(business_date) as sale_business_date
    from {{ ref('int_sales_lines') }}
    group by receipt_no
)

select
    {{ dbt.concat(["lines.return_id", "'-'", "cast(lines.line_no as " ~ dbt.type_string() ~ ")"]) }} as return_line_id,
    lines.return_id,
    lines.line_no,
    returns.store_code,
    lines.sku_code,
    returns.returned_at,
    returns.return_date,
    returns.original_receipt_no,
    sale_receipts.sale_business_date,
    sale_receipts.receipt_no is not null as has_matching_sale,
    lines.uom_code,
    lines.qty,
    lines.qty * uoms.factor_to_base as qty_base,
    cast(skus.vat_rate as decimal(5, 4)) as vat_rate,
    lines.refund_vnd as refund_incl_vat,
    cast(lines.refund_vnd / (1 + skus.vat_rate) as decimal(18, 4)) as refund_excl_vat,
    returns.return_reason
from lines
inner join returns
    on lines.return_id = returns.return_id
inner join uoms
    on lines.sku_code = uoms.sku_code
    and lines.uom_code = uoms.uom_code
inner join skus
    on lines.sku_code = skus.sku_code
left join sale_receipts
    on returns.original_receipt_no = sale_receipts.receipt_no
