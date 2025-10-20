#!/usr/bin/env python
"""
Development server runner with auto-reload and HTTPS support.
"""
import os
import sys

if __name__ == '__main__':
    # Set development environment
    os.environ['FLASK_ENV'] = 'development'
    
    # Import and run the app
    from app import socketio, app
    
    print("=" * 60)
    print("Quiz Competition Backend Server")
    print("=" * 60)
    print(f"Environment: {os.environ.get('FLASK_ENV', 'production')}")
    print(f"Database: {app.config.get('DATABASE_URL', 'Not configured')}")
    print(f"Public URL: {app.config.get('PUBLIC_BASE_URL', 'Not configured')}")
    print("=" * 60)
    print("\nServer starting on http://localhost:5000")
    print("Press CTRL+C to stop\n")
    
    # Run with HTTP (no SSL for development to avoid certificate issues)
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=True
    )
