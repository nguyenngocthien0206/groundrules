-- Store sales dashboard: "Monthly sales" tile.
-- Built for store managers and their monthly targets. What the stores sold,
-- before VAT and after discounts. Returns are a customer service matter and
-- are kept out of the sales number.
--
-- Wrong today: revenue is sales minus refunds (DR-002). Leaving returns out
-- overstates revenue by every refund given in the month.
--
-- Parameters: $month_start, $month_end (first and last day of the month).
select coalesce(sum(amount_excl_vat), 0) as revenue
from marts.fct_sales
where business_date between $month_start and $month_end
