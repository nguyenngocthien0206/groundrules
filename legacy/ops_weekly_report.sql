-- Operations weekly report: "Revenue" line, rolled up to the month.
-- Built for the Monday operations review. Matches what the tills show:
-- what customers paid, minus what was refunded at the counter, both as the
-- customer saw them.
--
-- Wrong today: revenue is reported before VAT (DR-006). Till amounts include
-- VAT, which is collected for the state and changes with the product mix.
--
-- Parameters: $month_start, $month_end (first and last day of the month).
with paid as (
    select sum(amount_incl_vat) as amount
    from marts.fct_sales
    where business_date between $month_start and $month_end
),

refunded as (
    select sum(refund_incl_vat) as amount
    from marts.fct_returns
    where return_date between $month_start and $month_end
)

select coalesce(paid.amount, 0) - coalesce(refunded.amount, 0) as revenue
from paid, refunded
