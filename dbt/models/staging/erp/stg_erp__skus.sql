select
    "ITEM_NO" as sku_code,
    "ITEM_NAME" as sku_name,
    "CATEGORY_CD" as category_code,
    "CATEGORY_NAME" as category_name,
    "BASE_UOM" as base_uom,
    "PURCH_UOM" as purchase_uom,
    -- The ERP stores VAT as a whole percent.
    cast("VAT_RATE" as integer) / 100.0 as vat_rate,
    cast("LIST_PRICE" as bigint) as list_price_vnd,
    cast("SHELF_LIFE_DAYS" as integer) as shelf_life_days,
    {{ parse_ymd('"CREATED_AT"') }} as created_on,
    {{ parse_ymd('"UPDATED_AT"') }} as updated_on
from {{ source('erp', 'skus') }}
