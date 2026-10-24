-- One row per returned item. Unnesting the API's array is DuckDB syntax; on
-- a warehouse the loader usually delivers these lines as a child table, and
-- this model selects from it instead.
with exploded as (
    select
        return_id,
        unnest(lines) as line,
        generate_subscripts(lines, 1) as line_no
    from {{ source('returns', 'returns') }}
)

select
    return_id,
    cast(line_no as integer) as line_no,
    line.sku as sku_code,
    line.uom as uom_code,
    line.qty as qty,
    -- VAT included, net of any discount given at the sale.
    line.refund_vnd as refund_vnd
from exploded
