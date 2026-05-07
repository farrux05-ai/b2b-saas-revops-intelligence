import duckdb

try:
    con = duckdb.connect('duckdb/revops_intelligence.duckdb')

    print("--- stg_internal__users emails ---")
    res = con.execute("SELECT email FROM main.stg_internal__users LIMIT 5").fetchall()
    for r in res: print(r)

    print("\n--- stg_hubspot__contacts emails ---")
    res = con.execute("SELECT email FROM main.stg_hubspot__contacts LIMIT 5").fetchall()
    for r in res: print(r)

    print("\n--- Match Count ---")
    res = con.execute("""
        SELECT count(*) 
        FROM main.stg_internal__users u
        JOIN main.stg_hubspot__contacts h ON lower(u.email) = lower(h.email)
    """).fetchall()
    print(res)

    print("\n--- Check exact matches with rn ---")
    res = con.execute("""
        WITH hs AS (
            SELECT email, row_number() over(partition by lower(email) order by updated_at desc nulls last) as rn
            FROM main.stg_hubspot__contacts
        )
        SELECT count(*) 
        FROM main.stg_internal__users u
        JOIN hs h ON lower(u.email) = lower(h.email) AND h.rn = 1
    """).fetchall()
    print(res)

except Exception as e:
    print(f"Error: {e}")

except Exception as e:
    print(f"Error: {e}")
