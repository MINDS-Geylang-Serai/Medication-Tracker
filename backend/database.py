import os
import sqlite3
from datetime import date, time, datetime
from types import SimpleNamespace

from dotenv import load_dotenv

load_dotenv()

# Where the database file lives. Set DB_PATH in .env to change it.
DB_PATH = os.getenv("DB_PATH", "data/minds_medication.db")


# ---------------------------------------------------------
# Store dates and times as text, read them back as
# Python date/time objects (same as the Azure version).
# ---------------------------------------------------------

sqlite3.register_adapter(date, lambda value: value.isoformat())
sqlite3.register_adapter(time, lambda value: value.isoformat())
sqlite3.register_adapter(datetime, lambda value: value.isoformat(sep=" "))


def _to_date(raw):
    text = raw.decode()
    try:
        return date.fromisoformat(text)
    except ValueError:
        return text


def _to_time(raw):
    text = raw.decode()
    try:
        return time.fromisoformat(text)
    except ValueError:
        return text


sqlite3.register_converter("DATE", _to_date)
sqlite3.register_converter("TIME", _to_time)


# ---------------------------------------------------------
# Let main.py use row.column_name, like pyodbc.
# ---------------------------------------------------------

def _row_factory(cursor, row):
    return SimpleNamespace(
        **{
            column[0]: value
            for column, value in zip(cursor.description, row)
        }
    )


# ---------------------------------------------------------
# Let main.py call cursor.execute(sql, a, b, c), like pyodbc.
# ---------------------------------------------------------

class _Cursor:

    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, *params):
        if len(params) == 1 and isinstance(params[0], (list, tuple)):
            params = params[0]
        self._cursor.execute(sql, params)
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def close(self):
        self._cursor.close()


class _Connection:

    def __init__(self, connection):
        self._connection = connection

    def cursor(self):
        return _Cursor(self._connection.cursor())

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()


def get_connection():

    folder = os.path.dirname(DB_PATH)

    if folder:
        os.makedirs(folder, exist_ok=True)

    connection = sqlite3.connect(
        DB_PATH,
        detect_types=sqlite3.PARSE_DECLTYPES,
        timeout=30
    )

    connection.row_factory = _row_factory

    # Lets several staff read and write at the same time safely.
    connection.execute("PRAGMA journal_mode = WAL")

    return _Connection(connection)