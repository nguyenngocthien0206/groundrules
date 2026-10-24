-- Lists every store whose POS sales have not fully reached the warehouse.
--
-- Source freshness only looks at the newest row of a whole source, so it
-- passes while a single store is days behind. This test looks per store.
-- It warns instead of failing: lagging stores stay in every number, and
-- answers that include them must carry a caveat (DR-004). A warning on every
-- build is the reminder.
{{ config(severity = 'warn') }}

select
    store_code,
    store_name,
    pos_vendor,
    pos_data_through,
    pos_lag_days,
    last_synced_at,
    last_sync_error
from {{ ref('dim_store') }}
where is_pos_sync_lagging
