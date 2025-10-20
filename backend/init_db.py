#!/usr/bin/env python
"""
Database initialization script.
Runs the schema creation and optionally seeds demo data.
"""
import psycopg2
import sys
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:1234@localhost:5432/quiz_competition')

def run_sql_file(cursor, filepath):
    """Execute SQL file."""
    print(f"Running {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        sql = f.read()
        cursor.execute(sql)
    print(f"✓ {filepath} completed")

def main():
    """Initialize database."""
    print("=" * 60)
    print("Quiz Competition - Database Initialization")
    print("=" * 60)
    print(f"Database: {DATABASE_URL}\n")
    
    try:
        # Connect to database
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # Run schema creation
        schema_file = os.path.join(os.path.dirname(__file__), 'db', 'create_db.sql')
        if os.path.exists(schema_file):
            run_sql_file(cursor, schema_file)
        else:
            print(f"ERROR: Schema file not found: {schema_file}")
            sys.exit(1)
        
        # Ask about seed data
        if len(sys.argv) > 1 and sys.argv[1] == '--seed':
            seed_file = os.path.join(os.path.dirname(__file__), 'db', 'seed.sql')
            if os.path.exists(seed_file):
                run_sql_file(cursor, seed_file)
            else:
                print(f"WARNING: Seed file not found: {seed_file}")
        
        # Commit changes
        conn.commit()
        
        print("\n" + "=" * 60)
        print("✓ Database initialization completed successfully!")
        print("=" * 60)
        
        # Show demo credentials if seeded
        if len(sys.argv) > 1 and sys.argv[1] == '--seed':
            print("\nDemo Teacher Account:")
            print("  Email: teacher@demo.com")
            print("  Password: demo123")
            print("\nDemo Quiz: 'Demo Quiz - General Knowledge' with 5 questions")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
