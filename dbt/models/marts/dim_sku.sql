with skus as (
    select * from {{ ref('stg_erp__skus') }}
),

purchase_units as (
    select sku_code, uom_code, factor_to_base
    from {{ ref('stg_erp__sku_uoms') }}
)

select
    skus.sku_code,
    skus.sku_name,
    skus.category_code,
    skus.category_name,
    skus.base_uom,
    skus.purchase_uom,
    purchase_units.factor_to_base as purchase_uom_factor,
    cast(skus.vat_rate as decimal(5, 4)) as vat_rate,
    skus.list_price_vnd as list_price_incl_vat,
    skus.shelf_life_days,
    skus.created_on,
    skus.updated_on
from skus
inner join purchase_units
    on skus.sku_code = purchase_units.sku_code
    and skus.purchase_uom = purchase_units.uom_code
