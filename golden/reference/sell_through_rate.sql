-- sell_through_rate from $start to $end.
-- DR-011 (keeping DR-009's formula): base units sold (returns not
--         subtracted, they are destroyed) divided by base units received
--         net: everything received (from suppliers and other stores, on the
--         receipt day) minus what the store sent to other stores (on the
--         delivery day). No value when net received is zero or negative.
-- DR-007: base units.
with sold as (
    select sum(units) as units
    from ref_sales
    where business_day between $start::date and $end::date
      and store in (from in_scope_store($store, $district))
      and sku in (from in_scope_sku($sku, $category))
),

received as (
    select sum(b.received_qty * u.factor) as units
    from raw_batches b
    join raw_units u on u.sku = b.sku and u.unit = b.received_unit
    where b.received between $start::date and $end::date
      and b.store in (from in_scope_store($store, $district))
      and b.sku in (from in_scope_sku($sku, $category))
),

sent_away as (
    select sum(t.qty * u.factor) as units
    from raw_transfers t
    join raw_units u on u.sku = t.sku and u.unit = t.unit
    where t.status = 'DL'
      and t.delivered between $start::date and $end::date
      and t.from_store in (from in_scope_store($store, $district))
      and t.sku in (from in_scope_sku($sku, $category))
)

select coalesce(sold.units, 0) * 1.0
    / case when coalesce(received.units, 0) - coalesce(sent_away.units, 0) > 0
           then coalesce(received.units, 0) - coalesce(sent_away.units, 0) end as value
from sold, received, sent_away
