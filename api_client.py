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
        
        # Simplified check for Virtuals. In a real scenario, this would involve
        # checking if the token was deployed by a known Virtuals factory contract
        # or if it's part of the Virtuals ecosystem via other on-chain data.
        # For now, we'll assume if it's not Clanker/Bankr, it's 'Unknown' or 'Virtuals' if we have a specific list.
        # For this task, we'll just return 'Unknown' if not Clanker/Bankr.
        return "Unknown", None

    async def get_social_media_links(self, dex_data, platform_data):
        social_links = []
        # From DexScreener
        if dex_data and dex_data.get("info"):
            for link_type in ["websites", "socials"]:
                for link in dex_data["info"].get(link_type, []):
                    social_links.append({"platform": link.get("type", "Website"), "url": link.get("url")})
        
        # From Clanker data
        if platform_data and platform_data.get("metadata", {}).get("socialMediaUrls"):
            for link in platform_data["metadata"]["socialMediaUrls"]:
                social_links.append({"platform": link.get("platform", "Website"), "url": link.get("url")})
        
        return social_links

    async def get_creator_info(self, platform_data):
        creator_address = None
        fee_recipient_address = None

        if platform_data and platform_data.get("msg_sender"):
            creator_address = platform_data["msg_sender"]
        
        if platform_data and platform_data.get("locker_address"):
            fee_recipient_address = platform_data["locker_address"]

        return creator_address, fee_recipient_address
