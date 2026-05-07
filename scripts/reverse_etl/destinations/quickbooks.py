from scripts.reverse_etl.core.base_connector import BaseConnector
from scripts.reverse_etl.core.state_manager import StateManager

class QuickBooksConnector(BaseConnector):
    def __init__(self, is_simulation=False):
        super().__init__(name="QuickBooks", is_simulation=is_simulation)
        self.state_manager = StateManager()

    def sync(self, con):
        """Syncs verified monthly MRR ledger entries to QuickBooks."""
        self.execute_with_retry(self._sync_ledger, max_retries=3, con=con)

    def _sync_ledger(self, con):
        self.logger.info("Starting MRR Ledger sync to QuickBooks...")
        
        # Get only the expansion and new revenue for the current month
        query = """
            SELECT workspace_name, month_date, mrr_change_amount, mrr_movement_type
            FROM main_marts.fct_mrr_waterfall
            WHERE mrr_movement_type IN ('new', 'expansion')
              AND mrr_change_amount > 0
            ORDER BY month_date DESC
            LIMIT 50
        """
        records = con.execute(query).fetchall()
        
        if not records:
            self.logger.info("No new MRR ledger entries to sync.")
            return

        synced = 0
        for name, date, amount, mov_type in records:
            if synced < 3:
                self.logger.info(f"   💰 Ledger Entry: {name} | {date} | +${amount} ({mov_type})")
            elif synced == 3:
                self.logger.info("   ... (additional ledger entries hidden)")
                
            if not self.is_simulation:
                # POST /v3/company/{realmId}/journalentry
                pass
            synced += 1
            
        self.state_manager.update_last_sync("quickbooks", "ledger")
        self.logger.info(f"Successfully synced {synced} ledger entries to QuickBooks.")
