-- Reference views over the raw extracts.
--
-- This is the independent side of the golden questions. It reads the files
-- that `make data` writes, the way they arrive from the source systems, and
-- never the dbt marts or the semantic layer. It was written from the
-- extract formats and the decision records' text, not from the dbt models.
-- On a warehouse, replace each read_csv / read_json with your raw tables.
--
-- Each one is a table in an in-memory database, so the raw files are read
-- once per run instead of once per question. {data_dir} is filled in by
-- reference.py.

create or replace table raw_stores as
select
    "STORE_CD" as store,
    "DISTRICT_CD" as district,
    strptime("OPENED_ON", '%Y%m%d')::date as opened_on
from read_csv('{data_dir}/erp/stores.csv', all_varchar = true);

create or replace table raw_skus as
select
    "ITEM_NO" as sku,
    "CATEGORY_CD" as category,
    "VAT_RATE"::integer as vat_pct,
    "PURCH_UOM" as purchase_unit  -- the unit stock is bought and moved in
from read_csv('{data_dir}/erp/skus.csv', all_varchar = true);

-- Size of every unit in base units (DR-007).
create or replace table raw_units as
select
    "ITEM_NO" as sku,
    "UOM_CD" as unit,
    "FACTOR_TO_BASE"::integer as factor
from read_csv('{data_dir}/erp/sku_uom.csv', all_varchar = true);

-- ERP batches: received in the purchase unit, on hand in the base unit.
create or replace table raw_batches as
select
    "STORE_CD" as store,
    "ITEM_NO" as sku,
    strptime("EXP_DATE", '%Y%m%d')::date as expires,
    strptime("RCV_DATE", '%Y%m%d')::date as received,
    "RCV_QTY"::integer as received_qty,
    "RCV_UOM" as received_unit,
    "UNIT_COST"::bigint as cost_per_received_unit,
    "ONHAND_QTY"::integer as on_hand_base
from read_csv('{data_dir}/erp/batches.csv', all_varchar = true);

create or replace table raw_transfers as
select
    "FROM_STORE" as from_store,
    "ITEM_NO" as sku,
    "QTY"::integer as qty,
    "UOM" as unit,
    "STATUS" as status,  -- TR in transit, DL delivered, CX cancelled
    try_strptime("RECEIVED_AT", '%Y%m%d')::date as delivered
from read_csv('{data_dir}/erp/transfers.csv', all_varchar = true);

-- Sales from both POS vendors, one row per real receipt line, in the local
-- business day (DR-004) and in ERP unit codes.
create or replace table raw_sales as
with vendor_a as (
    -- Upload retries resend a line; the first upload counts.
    select *
    from read_csv('{data_dir}/pos_a/*.csv', all_varchar = true)
    qualify row_number() over (partition by txn_id, line_no order by exported_at) = 1
)
select
    store_code as store,
    item_code as sku,
    case uom when 'BTL' then 'BOTTLE' when 'PCS' then 'PIECE' else uom end as unit,
    qty::integer as qty,
    line_amount::bigint as paid_incl_vat,
    -- UTC + 7 hours = Asia/Ho_Chi_Minh, which has no daylight saving.
    (strptime(txn_ts, '%Y-%m-%dT%H:%M:%SZ') + interval 7 hour)::date as business_day
from vendor_a
union all
select
    "MaCuaHang",
    "MaHang",
    case "DVT" when 'Viên' then 'TAB' when 'Vỉ' then 'STRIP' when 'Hộp' then 'BOX'
               when 'Chai' then 'BOTTLE' when 'Cái' then 'PIECE' end,
    "SoLuong"::integer,
    "ThanhTien"::bigint,
    strptime("NgayBan", '%d/%m/%Y')::date
from read_csv('{data_dir}/pos_b/*.csv', delim = ';', all_varchar = true);

-- Sales in base units and before VAT (DR-006, DR-007). Money is a decimal
-- with 6 places per line: sums of decimals do not depend on the order the
-- rows are added in, so every run gives the same digits.
create or replace table ref_sales as
select
    s.store,
    s.sku,
    s.business_day,
    s.qty * u.factor as units,
    (s.paid_incl_vat * 100.0 / (100 + k.vat_pct))::decimal(38, 6) as paid_excl_vat
from raw_sales s
join raw_units u on u.sku = s.sku and u.unit = s.unit
join raw_skus k on k.sku = s.sku;

-- Returned items in base units and before VAT, on the local return day.
create or replace table ref_returns as
with records as (
    select
        store.code as store,
        strptime(left(returned_at, 19), '%Y-%m-%dT%H:%M:%S')::date as return_day,
        unnest(lines) as line
    from read_json(
        '{data_dir}/returns/returns.jsonl',
        format = 'newline_delimited',
        columns = {
            'store': 'STRUCT(code VARCHAR)',
            'returned_at': 'VARCHAR',
            'lines': 'STRUCT(sku VARCHAR, uom VARCHAR, qty INTEGER, refund_vnd BIGINT)[]'
        }
    )
)
select
    r.store,
    r.line.sku as sku,
    r.return_day,
    r.line.qty * u.factor as units,
    (r.line.refund_vnd * 100.0 / (100 + k.vat_pct))::decimal(38, 6) as refund_excl_vat
from records r
join raw_units u on u.sku = r.line.sku and u.unit = r.line.uom
join raw_skus k on k.sku = r.line.sku;

-- The last business day whose sales reached the extract, per store. The
-- sync runs in the early morning and brings in the day before.
create or replace table ref_pos_data_through as
select
    store_code as store,
    (strptime(last_success_at, '%Y-%m-%d %H:%M:%S') - interval 1 day)::date as data_through
from read_csv('{data_dir}/pos_sync_log.csv', all_varchar = true);

-- The logistics provider's drive times between stores. A pair it re-sent
-- appears twice; the latest computed_at wins.
create or replace table raw_routes as
select
    origin_code as origin,
    destination_code as destination,
    duration_s::integer as drive_seconds
from read_csv('{data_dir}/logistics/store_routes.csv', all_varchar = true)
qualify row_number() over (partition by origin_code, destination_code order by computed_at desc) = 1;

-- Which stores and SKUs a question covers. Null means "all".
create or replace macro in_scope_store(p_store, p_district) as table
    select store from raw_stores
    where (p_store is null or store = p_store) and (p_district is null or district = p_district);

create or replace macro in_scope_sku(p_sku, p_category) as table
    select sku from raw_skus
    where (p_sku is null or sku = p_sku) and (p_category is null or category = p_category);
