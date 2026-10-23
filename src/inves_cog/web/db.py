"""Read-only connections for the page API."""

import psycopg
from psycopg.rows import dict_row


def open_reader(dsn):
    """Open a session whose transactions cannot write."""
    connection = psycopg.connect(dsn, row_factory=dict_row)
    connection.execute("SET default_transaction_read_only TO on")
    connection.commit()
    return connection
