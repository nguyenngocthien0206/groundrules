-- Routes from the logistics provider, in km and minutes. A pair the provider
-- re-sent later appears twice; the latest computation wins. row_number in a
-- subquery rather than qualify, so this also runs on Postgres.
with typed as (
    select
        origin_code as origin_store_code,
        destination_code as destination_store_code,
        cast(cast(distance_m as integer) / 1000.0 as decimal(8, 3)) as distance_km,
        cast(cast(duration_s as integer) / 60.0 as decimal(8, 2)) as drive_minutes,
        {{ parse_iso_seconds('computed_at') }} as computed_at_utc
    from {{ source('logistics', 'store_routes') }}
),

ranked as (
    select
        *,
        row_number() over (
            partition by origin_store_code, destination_store_code
            order by computed_at_utc desc
        ) as recency
    from typed
)

select origin_store_code, destination_store_code, distance_km, drive_minutes, computed_at_utc
from ranked
where recency = 1
