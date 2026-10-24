-- One row per returned item, with both the return date and (when known) the
-- original sale date. Which month a return counts in is decided in the
-- semantic layer (DR-002), so both dates are kept here.
select
    return_line_id,
    return_id,
    line_no,
    store_code,
    sku_code,
    return_date,
    returned_at,
    original_receipt_no,
    sale_business_date,
    has_matching_sale,
    uom_code,
    qty,
    qty_base,
    vat_rate,
    refund_incl_vat,
    refund_excl_vat,
    return_reason
from {{ ref('int_return_lines') }}
