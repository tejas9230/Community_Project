import os
from dotenv import load_dotenv
load_dotenv()
import psycopg2

conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur  = conn.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
tables = [r[0] for r in cur.fetchall()]
print('Tables in Supabase:', tables)
cur.execute('SELECT username, role FROM users ORDER BY role')
users = cur.fetchall()
print('Users:', [(u[0], u[1]) for u in users])
conn.close()
print('Supabase ready!')
