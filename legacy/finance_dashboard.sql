-- Finance monthly dashboard: "Revenue" tile.
-- Built for the month-end pack. Revenue before VAT, after discounts, minus
-- returns. Returns are put back on the month of the sale they belong to,
-- so each month shows what that month's sales were really worth.
--
-- Wrong today: returns count in the month they come back (DR-002). Here a
-- closed month keeps moving for weeks, and a return with no receipt has no
-- sale month, so it silently disappears.
--
-- Parameters: $month_start, $month_end (first and last day of the month).
with sales as (
    select sum(amount_excl_vat) as amount
    from marts.fct_sales
    where business_date between $month_start and $month_end
),

returns_of_these_sales as (
    select sum(refund_excl_vat) as amount
    from marts.fct_returns
    where sale_business_date between $month_start and $month_end
)

select coalesce(sales.amount, 0) - coalesce(returns_of_these_sales.amount, 0) as revenue
from sales, returns_of_these_sales
