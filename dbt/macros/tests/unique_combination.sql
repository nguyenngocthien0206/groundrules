{#- Fails when two rows share the same values in `columns`. A small stand-in
    for dbt_utils.unique_combination_of_columns, so the demo needs no
    package downloads. -#}
{% test unique_combination(model, columns) %}
select {{ columns | join(', ') }}, count(*) as n
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}
