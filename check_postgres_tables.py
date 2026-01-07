# check_postgres_tables.py
import psycopg2
from app.config import settings
import sys

def check_postgres_tables():
    print("Checking PostgreSQL database...")
    print("=" * 60)
    
    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            user=settings.postgres_user,
            password=settings.postgres_password,
            dbname=settings.postgres_db
        )
        
        cursor = conn.cursor()
        print("✅ Connected to PostgreSQL")
        print(f"Host: {settings.postgres_host}:{settings.postgres_port}")
        print(f"Database: {settings.postgres_db}")
        
        # Get all tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = cursor.fetchall()
        
        print(f"\nFound {len(tables)} tables in database:")
        for table in tables:
            table_name = table[0]
            print(f"\nTable: {table_name}")
            
            # Get column info
            cursor.execute(f"""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = '{table_name}'
                ORDER BY ordinal_position
            """)
            columns = cursor.fetchall()
            
            print(f"  Columns ({len(columns)}):")
            for col in columns:
                col_name, data_type, nullable = col
                print(f"    - {col_name} ({data_type}) {'NULL' if nullable == 'YES' else 'NOT NULL'}")
            
            # Count rows for order table
            if table_name == 'order':
                cursor.execute('SELECT COUNT(*) FROM "order"')
                count = cursor.fetchone()[0]
                print(f"  Rows: {count}")
                
                # Check for specific columns
                column_names = [col[0] for col in columns]
                print(f"\n  Checking for required columns in 'order' table:")
                required_columns = ['shipped_at', 'delivered_at', 'tracking_id', 'tracking_url']
                for req_col in required_columns:
                    if req_col in column_names:
                        print(f"    ✓ {req_col}")
                    else:
                        print(f"    ✗ {req_col} (MISSING)")
        
        cursor.close()
        conn.close()
        
        print("\n" + "="*60)
        print("✅ PostgreSQL database check complete")
        
    except Exception as e:
        print(f"❌ Error connecting to PostgreSQL: {e}")
        print(f"Connection details:")
        print(f"  Host: {settings.postgres_host}")
        print(f"  Port: {settings.postgres_port}")
        print(f"  User: {settings.postgres_user}")
        print(f"  Database: {settings.postgres_db}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_postgres_tables()
    