{% macro calculate_mrr(unit_amount, quantity) %}
    case
        when {{ unit_amount }} > 0
        then ({{ unit_amount }} * coalesce({{ quantity }}, 1)) / 100.0
        else 0
    end
{% endmacro %}
