import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from config import Config

class Database:
    def __init__(self):
        self.connection_string = Config.DATABASE_URL
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = psycopg2.connect(self.connection_string)
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    @contextmanager
    def get_cursor(self, dict_cursor=True):
        """Context manager for database cursors."""
        with self.get_connection() as conn:
            cursor_factory = RealDictCursor if dict_cursor else None
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
            finally:
                cursor.close()

db = Database()
