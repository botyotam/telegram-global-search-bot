import httpx
import logging

logger = logging.getLogger(__name__)

class APIClient:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)

    async def get_dex_data(self, ca):
        url = f"https://api.dexscreener.com/latest/dex/tokens/{ca}"
        try:
            response = await self.client.get(url)
            if response.status_code == 200:
                data = response.json()
                pairs = data.get("pairs", [])
                if not pairs:
                    return None
                # Filter for Base chain and highest liquidity
                base_pairs = [p for p in pairs if p.get("chainId") == "base"]
                if not base_pairs:
                    return None
                return sorted(base_pairs, key=lambda x: float(x.get("liquidity", {}).get("usd", 0)), reverse=True)[0]
        except Exception as e:
            logger.error(f"Error fetching DexScreener data: {e}")
        return None

    async def get_clanker_data(self, ca):
        url = f"https://www.clanker.world/api/get-clanker-by-address?address={ca}"
        try:
            response = await self.client.get(url)
            if response.status_code == 200:
                return response.json().get("data")
        except Exception as e:
            logger.error(f"Error fetching Clanker data: {e}")
        return None

    async def get_bankr_data(self, ca):
        # Bankr usually uses Clanker API for deployment info, but has its own list
        # For now, we can check if it's a Bankr token via Clanker metadata or common patterns
        # If there's a specific Bankr API for token info, we'd add it here.
        return None

    async def get_virtuals_data(self, ca):
        # Virtuals might need a subgraph or specific API. 
        # For basic info, DexScreener is often enough, but platform-specific info 
        # like graduation status might need more.
        return None

    async def identify_platform(self, ca):
        clanker = await self.get_clanker_data(ca)
        if clanker:
            if clanker.get("social_context", {}).get("interface") == "Bankr":
                return "Bankr", clanker
            return "Clanker", clanker
        
        # Check for Virtuals (simplified check, can be improved with on-chain or specific API)
        # Often Virtuals tokens have specific factory or patterns.
        return "Unknown", None
