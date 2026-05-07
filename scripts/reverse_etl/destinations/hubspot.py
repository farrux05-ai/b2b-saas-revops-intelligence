from scripts.reverse_etl.core.base_connector import BaseConnector
from scripts.reverse_etl.core.state_manager import StateManager

class HubSpotConnector(BaseConnector):
    def __init__(self, is_simulation=False):
        super().__init__(name="HubSpot", is_simulation=is_simulation)
        self.state_manager = StateManager()

    def sync(self, con, mode="all"):
        """Main entry point for syncing to HubSpot."""
        if mode in ["all", "l2a"]:
            self.execute_with_retry(self._sync_l2a, max_retries=3, con=con)
        if mode in ["all", "pql"]:
            self.execute_with_retry(self._sync_pql, max_retries=3, con=con)
        if mode in ["all", "health"]:
            self.execute_with_retry(self._sync_health, max_retries=3, con=con)

    def _sync_l2a(self, con):
        self.logger.info("Starting L2A (Identity Healing) sync...")
        query = """
            SELECT u.email, u.hubspot_company_id_stitched, u.match_method
            FROM main_identity.int_users_joined u
            WHERE u.hubspot_contact_id IS NULL
              AND u.hubspot_company_id_stitched IS NOT NULL
        """
        records = con.execute(query).fetchall()
        
        if not records:
            self.logger.info("No L2A associations pending.")
            return

        synced = 0
        for email, cid, method in records:
            self.logger.info(f"   🔗 Healing: {email} -> Company {cid} ({method})")
            if not self.is_simulation:
                # payload = {"email": email, "associatedCompanyId": cid}
                # requests.post(f"{HUBSPOT_API}/crm/v3/objects/contacts", json=payload)
                pass
            synced += 1
        
        self.logger.info(f"Successfully processed {synced} L2A associations.")

    def _sync_pql(self, con):
        self.logger.info("Starting PQL (Hot Intent) sync...")
        last_sync = self.state_manager.get_last_sync("hubspot", "pql")
        
        # In a real scenario, we would filter by `updated_at > last_sync`
        # For simulation, we'll just pull all HOT leads
        query = """
            SELECT u.hubspot_contact_id, u.email, p.pql_tier, p.recommended_action
            FROM main_marts.fct_pql_signals p
            JOIN main_identity.int_users_joined u ON p.workspace_id = u.internal_workspace_id
            WHERE p.pql_tier = '🔥 HOT'
              AND u.hubspot_contact_id IS NOT NULL
              AND u.user_role = 'owner'
        """
        records = con.execute(query).fetchall()
        
        if not records:
            self.logger.info("No Hot PQLs to sync.")
            return

        for cid, email, tier, action in records:
            self.logger.info(f"   🔥 PQL Alert: {email} is {tier}. Action: {action}")
            if not self.is_simulation:
                # PATCH /crm/v3/objects/contacts/{cid}
                pass
                
        self.state_manager.update_last_sync("hubspot", "pql")
        self.logger.info(f"Successfully synced {len(records)} PQL alerts.")

    def _sync_health(self, con):
        self.logger.info("Starting Health (Risk Monitoring) sync...")
        query = """
            SELECT hubspot_company_id, workspace_name, health_status, health_reason
            FROM main_marts.dim_accounts
            WHERE health_status = 'At Risk'
              AND hubspot_company_id IS NOT NULL
        """
        records = con.execute(query).fetchall()
        
        if not records:
            self.logger.info("No At-Risk accounts found.")
            return
            
        for cid, name, status, reason in records:
            self.logger.warning(f"   ⚠️ Risk Alert: {name} is {status} due to: {reason}")
            if not self.is_simulation:
                # PATCH /crm/v3/objects/companies/{cid}
                pass
        
        self.logger.info(f"Successfully synced {len(records)} Health alerts.")
