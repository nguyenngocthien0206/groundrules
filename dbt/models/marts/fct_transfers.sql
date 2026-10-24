-- Transfers with quantities in base units. A shipped transfer stays in the
-- sender's on-hand until it is delivered; a cancelled one never left.
with transfers as (
    select * from {{ ref('stg_erp__transfers') }}
),

units as (
    select sku_code, uom_code, factor_to_base from {{ ref('stg_erp__sku_uoms') }}
)

select
    transfers.transfer_no,
    transfers.sku_code,
    transfers.lot_no,
    transfers.from_store_code,
    transfers.to_store_code,
    transfers.qty * units.factor_to_base as qty_base,
    transfers.transfer_status,
    transfers.created_on,
    transfers.shipped_on,
    transfers.received_on,
    transfers.updated_on
from transfers
inner join units
    on transfers.sku_code = units.sku_code
    and transfers.uom_code = units.uom_code
