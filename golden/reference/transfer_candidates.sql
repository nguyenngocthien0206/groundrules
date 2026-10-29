-- Transfer candidates at $as_of (DR-012): every target store-SKU paired
-- with every donor of the same SKU within 30 minutes' drive. reference.py
-- picks the donor and shares out each donor's spare boxes.
--
-- Pace: base units sold over the 28 full days before $as_of (DR-010).
-- Available stock follows DR-001 and DR-003, as in available_stock.sql.
-- Cover = available / (units sold / 28). Comparisons below multiply both
-- sides by 28 so they stay in whole numbers.
--
-- Target: cover under 7 days.            available * 28 < 7 * sold
-- Donor:  cover over 60 days.             available * 28 > 60 * sold
-- Need:   whole purchase units to bring the target to 14 days, rounded up.
-- Cap:    whole purchase units that keep the target at 60 days or less.
-- Spare:  whole purchase units the donor can give and keep 30 days.
--
-- Neither side may be a lagging store (DR-004) or a store opened on or
-- after the first day of the pace window. A store with no route has no
-- pair. A store-SKU with no sales in the window has no cover: never a
-- target, never a donor.
with excluded as (
    select store from ref_pos_data_through where data_through < $as_of::date - 1
    union
    select store from raw_stores where opened_on >= $as_of::date - 28
),

long_dated as (
    select store, sku, sum(on_hand_base) as units
    from raw_batches
    where expires - $as_of::date >= 90
    group by store, sku
),

in_transit as (
    select t.from_store as store, t.sku, sum(t.qty * u.factor) as units
    from raw_transfers t
    join raw_units u on u.sku = t.sku and u.unit = t.unit
    where t.status = 'TR'
    group by t.from_store, t.sku
),

sold as (
    select store, sku, sum(units) as units
    from ref_sales
    where business_day between $as_of::date - 28 and $as_of::date - 1
    group by store, sku
),

positions as (
    select
        s.store,
        s.sku,
        k.purchase_unit,
        u.factor,
        coalesce(l.units, 0) - coalesce(t.units, 0) as available,
        s.units as sold_28d
    from sold s
    join raw_skus k on k.sku = s.sku
    join raw_units u on u.sku = s.sku and u.unit = k.purchase_unit
    left join long_dated l on l.store = s.store and l.sku = s.sku
    left join in_transit t on t.store = s.store and t.sku = s.sku
    where s.units > 0
      and s.store not in (from excluded)
),

targets as (
    select
        *,
        (14 * sold_28d - 28 * available + 28 * factor - 1) // (28 * factor) as need_units,
        (60 * sold_28d - 28 * available) // (28 * factor) as cap_units
    from positions
    where available * 28 < 7 * sold_28d
),

donors as (
    select
        *,
        (28 * available - 30 * sold_28d) // (28 * factor) as spare_units
    from positions
    where available * 28 > 60 * sold_28d
      and 28 * available - 30 * sold_28d >= 28 * factor
)

select
    t.store as target,
    d.store as donor,
    t.sku,
    t.purchase_unit,
    t.factor,
    t.available as target_available,
    t.sold_28d as target_sold_28d,
    t.need_units,
    t.cap_units,
    d.available as donor_available,
    d.sold_28d as donor_sold_28d,
    d.spare_units,
    r.drive_seconds
from targets t
join donors d on d.sku = t.sku and d.store <> t.store
join raw_routes r on r.origin = d.store and r.destination = t.store
where r.drive_seconds <= 30 * 60
order by t.store, t.sku, r.drive_seconds, d.store
