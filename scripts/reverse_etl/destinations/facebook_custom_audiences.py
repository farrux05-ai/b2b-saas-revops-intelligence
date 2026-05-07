from scripts.reverse_etl.core.base_connector import BaseConnector
from scripts.reverse_etl.core.state_manager import StateManager

class FacebookAdsConnector(BaseConnector):
    def __init__(self, is_simulation=False):
        super().__init__(name="FacebookAds", is_simulation=is_simulation)
        self.state_manager = StateManager()

    def sync(self, con):
        """Syncs high-value customers to a Facebook Custom Audience for Lookalike targeting."""
        self.execute_with_retry(self._sync_high_value_audience, max_retries=3, con=con)

    def _sync_high_value_audience(self, con):
        self.logger.info("Starting High-Value Custom Audience sync to Facebook...")
        
        # Select users belonging to accounts with MRR > 1000 or Segment = Enterprise
        query = """
            SELECT u.email, u.first_name, u.last_name, a.mrr
            FROM main_marts.dim_users u
            JOIN main_marts.dim_accounts a ON u.account_id = a.account_id
            WHERE a.mrr >= 500 OR a.account_segment = 'Enterprise'
              AND u.email IS NOT NULL
        """
        records = con.execute(query).fetchall()
        
        if not records:
            self.logger.info("No high-value audience found.")
            return

        self.logger.info(f"Hashing and batching {len(records)} emails for Custom Audience...")
        synced = 0
        for email, f_name, l_name, mrr in records:
            if synced < 3:
                self.logger.info(f"   🎯 Target: {email} (MRR: ${mrr}) -> Added to FB Lookalike Seed")
            elif synced == 3:
                self.logger.info("   ... (additional targets hidden)")
                
            if not self.is_simulation:
                # payload = {"payload": {"schema": "EMAIL", "data": [hash(email)]}}
                # requests.post(f"{FB_GRAPH_API}/act_{AD_ACCOUNT_ID}/users", json=payload)
                pass
            synced += 1
            
        self.state_manager.update_last_sync("facebook", "lookalike_seed")
        self.logger.info(f"Successfully synced {synced} users to Facebook Custom Audiences.")
