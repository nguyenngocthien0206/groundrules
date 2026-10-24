-- One row per day, which MetricFlow needs for cumulative windows and time
-- offsets. Covers the opening stock (received up to 180 days before the
-- sales window) through the end of 2027.
with days as (
    {{ dbt.date_spine('day', "cast('2025-01-01' as date)", "cast('2028-01-01' as date)") }}
)

select cast(date_day as date) as date_day
from days
