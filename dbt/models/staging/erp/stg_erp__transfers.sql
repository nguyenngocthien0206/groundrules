select
    "TRF_NO" as transfer_no,
    "ITEM_NO" as sku_code,
    "LOT_NO" as lot_no,
    "FROM_STORE" as from_store_code,
    "TO_STORE" as to_store_code,
    cast("QTY" as integer) as qty,
    "UOM" as uom_code,
    "STATUS" as transfer_status_code,
    case "STATUS"
        when 'TR' then 'in_transit'
        when 'DL' then 'delivered'
        when 'CX' then 'cancelled'
    end as transfer_status,
    {{ parse_ymd('"CREATED_AT"') }} as created_on,
    {{ parse_ymd('"SHIPPED_AT"') }} as shipped_on,
    {{ parse_ymd('"RECEIVED_AT"') }} as received_on,
    {{ parse_ymd('"UPDATED_AT"') }} as updated_on
from {{ source('erp', 'transfers') }}
