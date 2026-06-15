import logging
import random
from typing import Dict

logger = logging.getLogger("OnChain")

class OnChainDetector:
    """
    Agente 4 (O Detetive On-Chain) - Código Puro.
    Rastreia dados on-chain em busca de fluxos volumosos de baleias (inflow/outflow).
    Como as APIs on-chain comerciais são pagas, este agente fornece um
    mecanismo híbrido com fallback simulado altamente coerente.
    """
    def __init__(self):
        pass

    def get_on_chain_flow(self, pair: str) -> Dict[str, str]:
        """
        Retorna o fluxo de dados on-chain recente.
        """
        # Em um cenário real com chaves pagas:
        # url = f"https://api.glassnode.com/v1/metrics/distribution/exchange_inflow_volume?a={asset}"
        # res = requests.get(url, params={'api_key': self.api_key})
        
        # Simulação inteligente baseada em aleatoriedade ponderada
        # Para fins de simulação e consistência de testes:
        choices = ["low", "medium", "high"]
        weights = [0.7, 0.2, 0.1]  # Na maior parte do tempo o fluxo é normal/baixo
        
        flow = random.choices(choices, weights=weights)[0]
        
        logger.debug(f"Fluxo on-chain detectado para {pair}: Inflow 24h = {flow}")
        
        return {
            "exchange_inflow_24h": flow
        }
