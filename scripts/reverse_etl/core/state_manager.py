import json
import os
from datetime import datetime

STATE_FILE = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'sync_state.json')

class StateManager:
    """
    Manages the last sync timestamp for incremental syncing.
    In a production system, this would be stored in Postgres or DuckDB.
    """
    def __init__(self):
        self.state = {}
        self._load_state()

    def _load_state(self):
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                self.state = json.load(f)

    def _save_state(self):
        with open(STATE_FILE, 'w') as f:
            json.dump(self.state, f, indent=4)

    def get_last_sync(self, destination, sync_type):
        """Returns the last sync ISO timestamp, or a very old date if none."""
        key = f"{destination}_{sync_type}"
        return self.state.get(key, '1970-01-01T00:00:00Z')

    def update_last_sync(self, destination, sync_type):
        """Updates the sync timestamp to now."""
        key = f"{destination}_{sync_type}"
        self.state[key] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        self._save_state()
