-- net_revenue from $start to $end, VND before VAT.
-- DR-006: amounts before VAT. Paid amounts are already net of discounts.
-- DR-002: refunds count on the day of the return, whatever month the sale
--         was in, including returns with no matching sale.
-- DR-004: days are local business days.
with sales as (
    select sum(paid_excl_vat) as amount
    from ref_sales
    where business_day between $start::date and $end::date
      and store in (from in_scope_store($store, $district))
      and sku in (from in_scope_sku($sku, $category))
),

refunds as (
    select sum(refund_excl_vat) as amount
    from ref_returns
    where return_day between $start::date and $end::date
      and store in (from in_scope_store($store, $district))
      and sku in (from in_scope_sku($sku, $category))
)

select coalesce(sales.amount, 0) - coalesce(refunds.amount, 0) as value
from sales, refunds
