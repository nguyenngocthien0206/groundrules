{%- set snapshot_date = "cast('" ~ var('snapshot_date') ~ "' as date)" -%}

with stores as (
    select * from {{ ref('stg_erp__stores') }}
),

sync as (
    select * from {{ ref('stg_pos__sync_log') }}
),

joined as (
    select
        stores.*,
        sync.last_success_at,
        sync.last_attempt_at,
        sync.last_error,
        -- The sync runs in the early morning and brings in the day before.
        cast({{ dbt.dateadd('day', -1, 'sync.last_success_at') }} as date) as pos_data_through
    from stores
    left join sync
        on stores.store_code = sync.store_code
)

select
    store_code,
    store_name,
    district_code,
    district_name,
    opened_on,
    {{ dbt.datediff('opened_on', snapshot_date, 'day') }} as days_open,
    {{ dbt.datediff('opened_on', snapshot_date, 'day') }} <= 31 as is_newly_opened,
    is_open_24h,
    pos_vendor,
    last_success_at as last_synced_at,
    last_attempt_at as last_sync_attempt_at,
    last_error as last_sync_error,
    pos_data_through,
    -- Days of sales still missing: 0 when the store is synced through the
    -- day before the snapshot.
    {{ dbt.datediff('pos_data_through', dbt.dateadd('day', -1, snapshot_date), 'day') }} as pos_lag_days,
    {{ dbt.datediff('pos_data_through', dbt.dateadd('day', -1, snapshot_date), 'day') }} > 0 as is_pos_sync_lagging
from joined
