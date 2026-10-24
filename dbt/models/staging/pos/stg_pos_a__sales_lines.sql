-- Vendor A: drop upload retries, move UTC to local business time, and map
-- the vendor's unit codes to the ERP's.
with source as (
    select * from {{ source('pos_a', 'sales_lines') }}
),

deduplicated as (
    -- A retry resends the same receipt line later, in the same file or the
    -- next day's. Keep the first upload of each line.
    select *
    from source
    qualify row_number() over (partition by txn_id, line_no order by exported_at, filename) = 1
)

select
    'A' as pos_vendor,
    txn_id as receipt_no,
    cast(line_no as integer) as line_no,
    store_code,
    item_code as sku_code,
    case uom
        when 'BTL' then 'BOTTLE'
        when 'PCS' then 'PIECE'
        else uom
    end as uom_code,
    cast(qty as integer) as qty,
    cast(unit_price as bigint) as unit_price_vnd,
    cast(discount_amount as bigint) as discount_vnd,
    cast(line_amount as bigint) as line_amount_vnd,
    {{ parse_iso_seconds('txn_ts') }} as sold_at_utc,
    {{ utc_to_local(parse_iso_seconds('txn_ts')) }} as sold_at,
    cast({{ utc_to_local(parse_iso_seconds('txn_ts')) }} as date) as business_date,
    filename as source_file
from deduplicated
