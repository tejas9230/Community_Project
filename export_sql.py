import sqlite3

def export_sql():
    conn = sqlite3.connect("complaints.db")
    with open("mysql_dataset.sql", "w", encoding="utf-8") as f:
        for line in conn.iterdump():
            f.write(f"{line}\n")
    conn.close()
    print("Exported mysql_dataset.sql successfully!")

if __name__ == "__main__":
    export_sql()
