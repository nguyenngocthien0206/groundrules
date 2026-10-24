select
    return_id,
    store.code as store_code,
    -- The API sends local time with a +07:00 offset.
    {{ parse_iso_seconds('returned_at') }} as returned_at,
    cast({{ parse_iso_seconds('returned_at') }} as date) as return_date,
    original_receipt as original_receipt_no,
    reason as return_reason
from {{ source('returns', 'returns') }}
