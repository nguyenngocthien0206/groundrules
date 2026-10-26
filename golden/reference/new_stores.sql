-- Stores in scope that opened after $start and no more than 7 days after
-- $end (DR-011): their opening stock, delivered in the week before they
-- open, counts as received in the period while their sales cover only part
-- of it, or none.
select s.store, s.opened_on
from raw_stores s
where s.opened_on > $start::date
  and s.opened_on <= $end::date + 7
  and s.store in (from in_scope_store($store, $district))
order by s.store
