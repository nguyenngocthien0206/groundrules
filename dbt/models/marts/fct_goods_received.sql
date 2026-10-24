-- Stock received by each store, one row per batch: from suppliers (purchase
-- orders) and from other stores (transfers). Whether transfers count as
-- "received" for sell-through is an open decision, so both are kept with
-- their source_type.
with batches as (
    select * from {{ ref('stg_erp__batches') }}
),

purchase_units as (
    select sku_code, uom_code, factor_to_base from {{ ref('stg_erp__sku_uoms') }}
)

select
    batches.batch_id as goods_received_id,
    batches.store_code,
    batches.sku_code,
    batches.lot_no,
    batches.received_on,
    batches.source_type,
    batches.source_doc,
    batches.received_qty * purchase_units.factor_to_base as qty_base,
    cast(batches.unit_cost_vnd * 1.0 / purchase_units.factor_to_base as decimal(18, 4)) as unit_cost_excl_vat,
    cast(batches.received_qty * batches.unit_cost_vnd as decimal(18, 4)) as received_value_excl_vat
from batches
inner join purchase_units
    on batches.sku_code = purchase_units.sku_code
    and batches.received_uom = purchase_units.uom_code
