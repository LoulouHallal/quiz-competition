#!/usr/bin/env python
"""Create demo teacher account."""
import psycopg2
from config import Config

conn = psycopg2.connect(Config.DATABASE_URL)
cur = conn.cursor()

# Insert user roles
cur.execute("""
    INSERT INTO user_role (userrole_name) VALUES 
        ('student'),
        ('teacher'),
        ('admin')
    ON CONFLICT (userrole_name) DO NOTHING
""")

# Insert demo teacher
cur.execute("""
    INSERT INTO app_user (user_fname, user_lname, user_email, userrole_id)
    VALUES ('Demo', 'Teacher', 'teacher@demo.com', 2)
    ON CONFLICT (user_email) DO NOTHING
""")

# Insert question types
cur.execute("""
    INSERT INTO question_type (questiontype_name) VALUES 
        ('mcq_single'),
        ('mcq_multi'),
        ('true_false')
    ON CONFLICT (questiontype_name) DO NOTHING
""")

conn.commit()
cur.close()
conn.close()

print("✓ Demo teacher account created successfully!")
print("\nLogin credentials:")
print("  Email: teacher@demo.com")
print("  Password: demo123")
print("\nNote: This is a simple demo setup. In production, implement proper password hashing.")
