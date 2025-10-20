#!/usr/bin/env python
"""
Quick setup verification script.
Tests database connection and basic API functionality.
"""
import sys
import os
from dotenv import load_dotenv

load_dotenv()

def test_imports():
    """Test if all required packages are installed."""
    print("Testing imports...")
    try:
        import flask
        import flask_socketio
        import flask_cors
        import flask_login
        import psycopg2
        import qrcode
        import eventlet
        print("✓ All required packages installed")
        return True
    except ImportError as e:
        print(f"✗ Missing package: {e}")
        print("Run: pip install -r requirements.txt")
        return False

def test_database():
    """Test database connection."""
    print("\nTesting database connection...")
    try:
        import psycopg2
        DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:1234@localhost:5432/quiz_competition')
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if result and result[0] == 1:
            print(f"✓ Database connection successful")
            print(f"  URL: {DATABASE_URL}")
            return True
        else:
            print("✗ Database query failed")
            return False
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        print("  Make sure PostgreSQL is running and database exists")
        print("  Run: createdb quiz_competition")
        return False

def test_schema():
    """Test if database schema exists."""
    print("\nTesting database schema...")
    try:
        import psycopg2
        DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/quiz_competition')
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # Check if key tables exist
        tables = ['app_user', 'course', 'question', 'class_session', 'students_answers']
        missing = []
        
        for table in tables:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, (table,))
            exists = cursor.fetchone()[0]
            if not exists:
                missing.append(table)
        
        cursor.close()
        conn.close()
        
        if not missing:
            print(f"✓ All required tables exist")
            return True
        else:
            print(f"✗ Missing tables: {', '.join(missing)}")
            print("  Run: python init_db.py")
            return False
    except Exception as e:
        print(f"✗ Schema check failed: {e}")
        return False

def test_config():
    """Test configuration."""
    print("\nTesting configuration...")
    try:
        from config import Config
        print(f"✓ Configuration loaded")
        print(f"  Database: {Config.DATABASE_URL}")
        print(f"  Public URL: {Config.PUBLIC_BASE_URL}")
        print(f"  QR Directory: {Config.QR_CODE_DIR}")
        
        # Check if QR directory exists
        if not os.path.exists(Config.QR_CODE_DIR):
            os.makedirs(Config.QR_CODE_DIR)
            print(f"  Created QR directory: {Config.QR_CODE_DIR}")
        
        return True
    except Exception as e:
        print(f"✗ Configuration failed: {e}")
        return False

def test_models():
    """Test if models can be imported."""
    print("\nTesting models...")
    try:
        from models.user import User
        from models.quiz import Quiz
        from models.question import Question
        from models.session import Session
        from models.participant import Participant
        from models.response import Response
        print("✓ All models imported successfully")
        return True
    except Exception as e:
        print(f"✗ Model import failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("Quiz Competition - Setup Verification")
    print("=" * 60)
    
    tests = [
        ("Imports", test_imports),
        ("Database Connection", test_database),
        ("Database Schema", test_schema),
        ("Configuration", test_config),
        ("Models", test_models)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name} test crashed: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print("\n" + "=" * 60)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)
    
    if passed == total:
        print("\n🎉 All tests passed! Your setup is ready.")
        print("\nNext steps:")
        print("  1. Run: python run.py")
        print("  2. Open PowerPoint and sideload the add-in")
        print("  3. Login with: teacher@demo.com / demo123")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please fix the issues above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
