-- Stores in scope whose POS data does not reach the day before $as_of
-- (DR-004), with the last day their data covers.
select d.store, d.data_through
from ref_pos_data_through d
where d.data_through < $as_of::date - 1
  and d.store in (from in_scope_store($store, $district))
order by d.store
