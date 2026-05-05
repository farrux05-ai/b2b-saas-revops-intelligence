-- Macro to simplify reading from Postgres in DuckDB
{%- macro postgres_source(schema, table) -%}
postgres_scan(
  'dbname={{ env_var("DBT_POSTGRES_DBNAME", "revops_database") }} user={{ env_var("DBT_POSTGRES_USER") }} password={{ env_var("DBT_POSTGRES_PASSWORD") }} host={{ env_var("DBT_POSTGRES_HOST") }} port={{ env_var("DBT_POSTGRES_PORT", "5432") | int }}',
  '{{ schema }}',
  '{{ table }}'
)
{%- endmacro -%}

