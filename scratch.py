import duckdb

con = duckdb.connect('duckdb/revops_intelligence.duckdb')

print("--- stg_internal__users emails ---")
res = con.execute("SELECT email FROM stackflow_revops.main.stg_internal__users LIMIT 5").fetchall()
for r in res: print(r)

print("\n--- stg_hubspot__contacts emails ---")
res = con.execute("SELECT email FROM stackflow_revops.main.stg_hubspot__contacts LIMIT 5").fetchall()
for r in res: print(r)

print("\n--- Match Count ---")
res = con.execute("""
    SELECT count(*) 
    FROM stackflow_revops.main.stg_internal__users u
    JOIN stackflow_revops.main.stg_hubspot__contacts h ON lower(u.email) = lower(h.email)
""").fetchall()
print(res)
