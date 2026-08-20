from pathlib import Path
import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver

_DB_PATH = Path(__file__).parent.parent / "dbs" / "chatbot_langgraph.db"
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_checkpointer():
    """Return an initialised SqliteSaver backed by dbs/chatbot_langgraph.db."""
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver, conn
