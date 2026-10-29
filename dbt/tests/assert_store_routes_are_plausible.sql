-- A route from a store to itself, or a drive under a minute or over four
-- hours across one city, means the provider's export is broken.
select origin_store_code, destination_store_code, drive_minutes
from {{ ref('fct_store_routes') }}
where origin_store_code = destination_store_code
   or drive_minutes < 1
   or drive_minutes > 240
