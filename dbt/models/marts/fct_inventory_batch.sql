-- Stock at the snapshot, one row per batch. Neutral facts only: how many
-- days each batch has left is here, but which batches count as "available"
-- is decided in the semantic layer (DR-001), not in this model.
{%- set snapshot_date = "cast('" ~ var('snapshot_date') ~ "' as date)" %}

with batches as (
    select * from {{ ref('stg_erp__batches') }}
),

purchase_units as (
    select sku_code, uom_code, factor_to_base from {{ ref('stg_erp__sku_uoms') }}
)

select
    batches.batch_id,
    batches.store_code,
    batches.sku_code,
    batches.lot_no,
    batches.received_on,
    batches.expires_on,
    {{ dbt.datediff(snapshot_date, 'batches.expires_on', 'day') }} as days_to_expiry,
    batches.source_type,
    batches.source_doc,
    -- Includes stock reserved for transfers in transit (see fct_transfers).
    batches.on_hand_qty as on_hand_qty_base,
    cast(batches.unit_cost_vnd * 1.0 / purchase_units.factor_to_base as decimal(18, 4)) as unit_cost_excl_vat,
    cast(batches.on_hand_qty * batches.unit_cost_vnd * 1.0 / purchase_units.factor_to_base as decimal(18, 4)) as on_hand_value_excl_vat,
    {{ snapshot_date }} as snapshot_date
from batches
inner join purchase_units
    on batches.sku_code = purchase_units.sku_code
    and batches.received_uom = purchase_units.uom_code
