-- Road distance and drive time between stores, one row per direction, as
-- the logistics provider last computed them. Drive time, not the district,
-- decides whether a store can send stock to another the same day.
select
    origin_store_code,
    destination_store_code,
    distance_km,
    drive_minutes,
    computed_at_utc
from {{ ref('stg_logistics__store_routes') }}
