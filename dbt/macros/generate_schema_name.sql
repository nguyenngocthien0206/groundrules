{#- Use the folder's schema name as is (staging, intermediate, marts) instead
    of prefixing it with the target schema, so every environment reads the
    same names. -#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name if custom_schema_name else target.schema }}
{%- endmacro %}
