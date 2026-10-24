select
    store_code,
    pos_vendor,
    -- Local time. A sync at 05:30 brings in the previous business day.
    cast(last_success_at as timestamp) as last_success_at,
    cast(last_attempt_at as timestamp) as last_attempt_at,
    nullif(last_error, '') as last_error
from {{ source('pos', 'sync_log') }}
