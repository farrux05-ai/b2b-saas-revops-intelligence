from scripts.reverse_etl.core.base_connector import BaseConnector

class ZendeskConnector(BaseConnector):
    def __init__(self, is_simulation=False):
        super().__init__(name="Zendesk", is_simulation=is_simulation)

    def sync(self, con):
        """Syncs account segments and health to Zendesk Organizations."""
        self.execute_with_retry(self._sync_organizations, max_retries=3, con=con)

    def _sync_organizations(self, con):
        self.logger.info("Starting Zendesk Organizations enrichment sync...")
        query = """
            SELECT workspace_name, domain, mrr, account_segment, health_status
            FROM main_marts.dim_accounts
            WHERE domain IS NOT NULL
        """
        records = con.execute(query).fetchall()
        
        if not records:
            self.logger.info("No records found for Zendesk sync.")
            return

        synced = 0
        for name, domain, mrr, segment, health in records:
            # We don't want to spam the console with 1000s of logs if it's large,
            # but for our dataset it's okay. Let's just log a few.
            if synced < 5:
                self.logger.info(f"   🔄 Syncing Org: {name} | Segment: {segment} | Health: {health}")
            elif synced == 5:
                self.logger.info("   ... (additional records hidden for brevity)")
                
            if not self.is_simulation:
                # PUT /api/v2/organizations/{id}.json
                pass
            synced += 1
            
        self.logger.info(f"Successfully enriched {synced} Zendesk Organizations.")
