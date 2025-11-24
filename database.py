import sqlite3
import datetime
import pandas as pd

DB_FILE = "zaptrack.db"

def init_db():
    """Initializes the SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            short_id INTEGER PRIMARY KEY AUTOINCREMENT,
            fbclid TEXT,
            ip_address TEXT,
            user_agent TEXT,
            timestamp DATETIME,
            status TEXT DEFAULT 'CLICKED', -- CLICKED, SOLD, ARCHIVED
            sale_value REAL
        )
    ''')
    conn.commit()
    conn.close()

def create_lead(fbclid, ip_address, user_agent):
    """Creates a new lead and returns the short_id."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    timestamp = datetime.datetime.now()
    c.execute('''
        INSERT INTO leads (fbclid, ip_address, user_agent, timestamp, status)
        VALUES (?, ?, ?, ?, 'CLICKED')
    ''', (fbclid, ip_address, user_agent, timestamp))
    short_id = c.lastrowid
    conn.commit()
    conn.close()
    return short_id

def get_lead(short_id):
    """Retrieves a lead by short_id."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM leads WHERE short_id = ?', (short_id,))
    lead = c.fetchone()
    conn.close()
    return lead

def get_active_leads():
    """Retrieves all active leads (status = CLICKED) ordered by time desc."""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM leads WHERE status = 'CLICKED' ORDER BY timestamp DESC", conn)
    conn.close()
    return df

def update_lead_status(short_id, status, sale_value=None):
    """Updates the status and sale value of a lead."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    if sale_value is not None:
        c.execute('UPDATE leads SET status = ?, sale_value = ? WHERE short_id = ?', (status, sale_value, short_id))
    else:
        c.execute('UPDATE leads SET status = ? WHERE short_id = ?', (status, short_id))
    conn.commit()
    conn.close()

def get_all_leads():
    """Retrieves all leads for admin view."""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM leads ORDER BY timestamp DESC", conn)
    conn.close()
    return df

# Initialize DB on import
init_db()
