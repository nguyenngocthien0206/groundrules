{#- Parsing for the date formats the source systems use. Raw extracts land as
    strings, the way a loader leaves them. These macros use only standard SQL
    and dbt's cross-database macros, so they run on any supported warehouse. -#}

{#- ERP dates: YYYYMMDD, empty when unknown. -#}
{% macro parse_ymd(expr) -%}
    case when {{ expr }} is null or {{ expr }} = '' then null else
        cast({{ dbt.concat(["substr(" ~ expr ~ ", 1, 4)", "'-'", "substr(" ~ expr ~ ", 5, 2)", "'-'", "substr(" ~ expr ~ ", 7, 2)"]) }} as date)
    end
{%- endmacro %}

{#- POS vendor B: date dd/mm/yyyy and time HH:MM:SS in separate columns. -#}
{% macro parse_dmy_hms(date_expr, time_expr) -%}
    cast({{ dbt.concat(["substr(" ~ date_expr ~ ", 7, 4)", "'-'", "substr(" ~ date_expr ~ ", 4, 2)", "'-'", "substr(" ~ date_expr ~ ", 1, 2)", "' '", time_expr]) }} as timestamp)
{%- endmacro %}

{#- ISO 8601 to the second, ignoring any suffix (Z or +07:00). The caller
    decides what time zone the value is in. -#}
{% macro parse_iso_seconds(expr) -%}
    cast(replace(substr({{ expr }}, 1, 19), 'T', ' ') as timestamp)
{%- endmacro %}

{#- UTC to Vietnam local time. Asia/Ho_Chi_Minh is UTC+7 all year (no
    daylight saving), so a fixed offset is exact and portable. -#}
{% macro utc_to_local(expr) -%}
    {{ dbt.dateadd('hour', 7, expr) }}
{%- endmacro %}
