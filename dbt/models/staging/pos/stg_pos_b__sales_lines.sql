-- Vendor B: Vietnamese headers, local dd/mm/yyyy dates, and unit names in
-- Vietnamese. TenHang (item name on the receipt) is dropped: it is the name
-- valid on the day of sale, so it disagrees with the ERP after a rename.
-- The ERP item number is the only reliable key.
select
    'B' as pos_vendor,
    "SoHoaDon" as receipt_no,
    cast("Dong" as integer) as line_no,
    "MaCuaHang" as store_code,
    "MaHang" as sku_code,
    case "DVT"
        when 'Viên' then 'TAB'
        when 'Vỉ' then 'STRIP'
        when 'Hộp' then 'BOX'
        when 'Chai' then 'BOTTLE'
        when 'Cái' then 'PIECE'
    end as uom_code,
    cast("SoLuong" as integer) as qty,
    cast("DonGia" as bigint) as unit_price_vnd,
    cast("ChietKhau" as bigint) as discount_vnd,
    cast("ThanhTien" as bigint) as line_amount_vnd,
    {{ dbt.dateadd('hour', -7, parse_dmy_hms('"NgayBan"', '"GioBan"')) }} as sold_at_utc,
    {{ parse_dmy_hms('"NgayBan"', '"GioBan"') }} as sold_at,
    cast({{ parse_dmy_hms('"NgayBan"', '"GioBan"') }} as date) as business_date,
    filename as source_file
from {{ source('pos_b', 'sales_lines') }}
