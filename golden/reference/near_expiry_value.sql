-- near_expiry_value at $as_of, VND before VAT.
-- DR-001: cost value of every batch with fewer than 90 days left to expiry,
--         stock that has already expired but is still on hand included.
select coalesce(sum((b.on_hand_base * b.cost_per_received_unit * 1.0 / u.factor)::decimal(38, 6)), 0) as value
from raw_batches b
join raw_units u on u.sku = b.sku and u.unit = b.received_unit
where b.expires - $as_of::date < 90
  and b.store in (from in_scope_store($store, $district))
  and b.sku in (from in_scope_sku($sku, $category))
