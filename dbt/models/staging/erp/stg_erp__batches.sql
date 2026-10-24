select
    "BATCH_ID" as batch_id,
    "STORE_CD" as store_code,
    "ITEM_NO" as sku_code,
    "LOT_NO" as lot_no,
    {{ parse_ymd('"EXP_DATE"') }} as expires_on,
    {{ parse_ymd('"RCV_DATE"') }} as received_on,
    -- Received in the purchase unit (box or carton) ...
    cast("RCV_QTY" as integer) as received_qty,
    "RCV_UOM" as received_uom,
    cast("UNIT_COST" as bigint) as unit_cost_vnd,
    "SOURCE_DOC" as source_doc,
    case
        when "SOURCE_DOC" like 'PO%' then 'purchase_order'
        when "SOURCE_DOC" like 'TRF%' then 'transfer'
    end as source_type,
    -- ... but on hand in the base unit (tablet, bottle, piece).
    cast("ONHAND_QTY" as integer) as on_hand_qty,
    "ONHAND_UOM" as on_hand_uom
from {{ source('erp', 'batches') }}
