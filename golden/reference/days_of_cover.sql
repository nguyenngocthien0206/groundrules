-- days_of_cover at $as_of.
-- DR-010: available stock at $as_of divided by the average daily base units
--         sold over the 28 full days before $as_of (the as-of day itself
--         has no sales yet when the extract runs).
-- Available stock follows DR-001 and DR-003, exactly as in available_stock.sql.
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
),

pace as (
    select sum(units) / 28.0 as units_per_day
    from ref_sales
    where business_day between $as_of::date - 28 and $as_of::date - 1
      and store in (from in_scope_store($store, $district))
      and sku in (from in_scope_sku($sku, $category))
)

select (coalesce(long_dated.units, 0) - coalesce(in_transit.units, 0)) / nullif(pace.units_per_day, 0) as value
from long_dated, in_transit, pace
