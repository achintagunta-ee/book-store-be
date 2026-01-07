# check_actual_columns.py
import psycopg2
from app.config import settings

def check_columns():
    try:
        conn = psycopg2.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            user=settings.postgres_user,
            password=settings.postgres_password,
            dbname=settings.postgres_db
        )
        
        cursor = conn.cursor()
        
        print("Checking what columns ACTUALLY exist in 'order' table:")
        print("=" * 60)
        
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'order'
            AND table_schema = 'public'
            ORDER BY column_name
        """)
        
        columns = cursor.fetchall()
        
        for col_name, data_type, nullable in columns:
            print(f"  {col_name}: {data_type} ({'NULL' if nullable == 'YES' else 'NOT NULL'})")
        
        # Check specifically for our columns
        target_cols = ['shipped_at', 'delivered_at', 'tracking_id', 'tracking_url']
        print(f"\nChecking for target columns:")
        
        existing_cols = {col[0] for col in columns}
        for col in target_cols:
            if col in existing_cols:
                print(f"  ✓ {col} - EXISTS")
            else:
                print(f"  ✗ {col} - MISSING")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_columns()