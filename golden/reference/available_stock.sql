-- available_stock at $as_of, in base units.
-- DR-001: only batches with at least 90 days left to expiry count.
-- DR-003: subtract what the store has shipped and not yet delivered
--         (status TR); a cancelled transfer (CX) is never subtracted.
-- DR-007: everything in base units.
with long_dated as (
    select sum(on_hand_base) as units
    from raw_batches
    where expires - $as_of::date >= 90
      and store in (from in_scope_store($store, $district))
      and sku in (from in_scope_sku($sku, $category))
),

in_transit as (
    select sum(t.qty * u.factor) as units
    from raw_transfers t
    join raw_units u on u.sku = t.sku and u.unit = t.unit
    where t.status = 'TR'
      and t.from_store in (from in_scope_store($store, $district))
      and t.sku in (from in_scope_sku($sku, $category))
)

select coalesce(long_dated.units, 0) - coalesce(in_transit.units, 0) as value
from long_dated, in_transit
