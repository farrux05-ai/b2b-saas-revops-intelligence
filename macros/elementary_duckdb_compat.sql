{# 
  elementary_duckdb_compat.sql
  ----------------------------
  This file provides DuckDB compatibility overrides for the Elementary dbt package.
  Since DuckDB shares a syntax family with PostgreSQL but handles transactions 
  differently (not allowing nested transactions/commits inside dbt runner contexts),
  we override these key macros to use standard query sequences and disable explicit commits.
#}

{% macro duckdb__edr_timeadd(date_part, number, timestamp_expression) %}
    {{ return(elementary.postgres__edr_timeadd(date_part, number, timestamp_expression)) }}
{% endmacro %}

{% macro duckdb__escape_special_chars(string_value) %}
    {{ return(elementary.postgres__escape_special_chars(string_value)) }}
{% endmacro %}

{% macro duckdb__get_delete_and_insert_queries(relation, insert_relation, delete_relation, delete_column_key) %}
    {{ return(elementary.trino__get_delete_and_insert_queries(relation, insert_relation, delete_relation, delete_column_key)) }}
{% endmacro %}

{% macro duckdb__insert_rows(table_relation, rows, should_commit=false, chunk_size=5000, on_query_exceed=none) %}
    {{ return(elementary.default__insert_rows(table_relation, rows, should_commit, chunk_size, on_query_exceed)) }}
{% endmacro %}

{% macro duckdb__create_or_replace(temporary, relation, sql_query) %}
    {{ return(elementary.trino__create_or_replace(temporary, relation, sql_query)) }}
{% endmacro %}
