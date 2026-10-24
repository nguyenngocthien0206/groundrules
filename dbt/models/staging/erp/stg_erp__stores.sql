select
    "STORE_CD" as store_code,
    "STORE_NAME" as store_name,
    "DISTRICT_CD" as district_code,
    "DISTRICT_NAME" as district_name,
    {{ parse_ymd('"OPENED_ON"') }} as opened_on,
    "OPEN_24H" = 'Y' as is_open_24h,
    "POS_SYSTEM" as pos_vendor,
    "STATUS" as store_status_code
from {{ source('erp', 'stores') }}
