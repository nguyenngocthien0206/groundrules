-- gross_margin from $start to $end, VND before VAT.
-- Net revenue as in net_revenue.sql (DR-002, DR-006), minus cost of goods sold.
-- DR-008: each base unit sold costs the store's weighted average for the
--         SKU: value of everything it received / base units it received,
--         purchase orders and transfers in, opening stock included.
--         Returns are destroyed, so their cost is not given back.
with avg_cost as (
    select
        b.store,
        b.sku,
        (sum(b.received_qty * b.cost_per_received_unit) * 1.0 / sum(b.received_qty * u.factor))::decimal(38, 10) as cost_per_unit
    from raw_batches b
    join raw_units u on u.sku = b.sku and u.unit = b.received_unit
    group by b.store, b.sku
),

sales as (
    select
        sum(s.paid_excl_vat) as amount,
        sum((s.units * c.cost_per_unit)::decimal(38, 6)) as cost
    from ref_sales s
    join avg_cost c on c.store = s.store and c.sku = s.sku
    where s.business_day between $start::date and $end::date
      and s.store in (from in_scope_store($store, $district))
      and s.sku in (from in_scope_sku($sku, $category))
),

refunds as (
    select sum(refund_excl_vat) as amount
    from ref_returns
    where return_day between $start::date and $end::date
      and store in (from in_scope_store($store, $district))
      and sku in (from in_scope_sku($sku, $category))
)

select coalesce(sales.amount, 0) - coalesce(refunds.amount, 0) - coalesce(sales.cost, 0) as value
from sales, refunds
