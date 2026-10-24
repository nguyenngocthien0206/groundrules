select
    "ITEM_NO" as sku_code,
    "UOM_CD" as uom_code,
    cast("FACTOR_TO_BASE" as integer) as factor_to_base,
    "IS_BASE" = 'Y' as is_base_uom,
    -- Empty when the SKU is never sold in this unit (for example a carton).
    cast(nullif("SELL_PRICE", '') as bigint) as sell_price_vnd
from {{ source('erp', 'sku_uom') }}
