-- Weighted average cost per base unit, per store and SKU (DR-008): the value
-- of everything the store received for the SKU divided by the units
-- received, from suppliers and from other stores, opening stock included.
-- POS lines carry no batch, so the cost of a sale cannot follow its lot.
with batches as (
    select * from {{ ref('stg_erp__batches') }}
),

purchase_units as (
    select sku_code, uom_code, factor_to_base from {{ ref('stg_erp__sku_uoms') }}
)

select
    batches.store_code,
    batches.sku_code,
    sum(batches.received_qty * purchase_units.factor_to_base) as units_received_base,
    sum(batches.received_qty * batches.unit_cost_vnd) as value_received_excl_vat,
    cast(
        sum(batches.received_qty * batches.unit_cost_vnd) * 1.0
        / sum(batches.received_qty * purchase_units.factor_to_base)
        as decimal(18, 4)
    ) as unit_cost_excl_vat
from batches
inner join purchase_units
    on batches.sku_code = purchase_units.sku_code
    and batches.received_uom = purchase_units.uom_code
group by batches.store_code, batches.sku_code
