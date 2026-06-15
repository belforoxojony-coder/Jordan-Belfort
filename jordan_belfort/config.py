import os
import logging
from typing import Any
from dotenv import load_dotenv
from jordan_belfort.database import Database

logger = logging.getLogger("Config")
load_dotenv()

class BotConfig:
    """
    Carrega as variáveis de ambiente e gerencia as configurações dinâmicas
    persistidas no banco de dados (ex: status ativo/pausado, alavancagem, etc.).
    """
    def __init__(self):
        self.db = Database()
        
        # Chaves de API e Variáveis Estáticas (obtidas apenas do .env)
        self.binance_api_key = os.getenv("BINANCE_API_KEY", "").strip()
        self.binance_api_secret = os.getenv("BINANCE_API_SECRET", "").strip()
        raw_use_testnet = os.getenv("BINANCE_USE_TESTNET", "true").lower().strip()
        self.binance_use_testnet = raw_use_testnet != "false"
        if raw_use_testnet == "false":
            logger.warning(
                "BINANCE_USE_TESTNET definido como false, mas o modo real da conta NÃO será usado. "
                "O bot permanece em modo Testnet por segurança."
            )
        self.binance_testnet_url = os.getenv("BINANCE_TESTNET_URL", "https://testnet.binance.vision/api").strip()
        
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        
        self.llm_provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
        self.llm_model = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()
        
        # APIs de Sentimento
        self.lunarcrush_api_key = os.getenv("LUNARCRUSH_API_KEY", "").strip()
        self.santiment_api_key = os.getenv("SANTIMENT_API_KEY", "").strip()
        
        # Cache de Configurações Dinâmicas (para evitar leituras frequentes ao banco)
        self._status = "active"  # Inicia em ATIVO para começar a fazer trades imediatamente
        self._risk_percentage = 1.0
        self._max_exposure_percentage = 5.0
        self._leverage = 1  # BLOQUEADO EM 1x – alavancagem zero
        
        # Sincroniza imediatamente no início
        self.sync_configs()

    def sync_configs(self):
        """Lê os parâmetros do banco de dados e atualiza o cache local."""
        try:
            self._status = self.db.get_config("status", "paused")
            self._risk_percentage = float(self.db.get_config("risk_percentage", 1.0))
            self._max_exposure_percentage = float(self.db.get_config("max_exposure_percentage", 5.0))
            # Alavancagem SEMPRE é mantida em 1x. Grava no banco para garantir consistência.
            self._leverage = 1
            self.db.set_config("leverage", 1)
            logger.info(
                f"Configurações dinâmicas sincronizadas: status={self._status}, "
                f"risco={self._risk_percentage}%, exposicao={self._max_exposure_percentage}%, "
                f"alavancagem=1x (BLOQUEADO)"
            )
        except Exception as e:
            logger.error(f"Erro ao sincronizar configurações com o banco: {e}")

    @property
    def is_paused(self) -> bool:
        """Retorna True se o bot estiver pausado ou inativo."""
        return self._status != "active"

    @property
    def status(self) -> str:
        return self._status

    @status.setter
    def status(self, new_status: str):
        if new_status in ["active", "paused"]:
            if self.db.set_config("status", new_status):
                self._status = new_status
                logger.info(f"Status global alterado para: {new_status}")
            else:
                logger.error(f"Falha ao persistir mudança de status para: {new_status}")

    @property
    def risk_percentage(self) -> float:
        return self._risk_percentage

    @risk_percentage.setter
    def risk_percentage(self, val: float):
        if val > 0:
            if self.db.set_config("risk_percentage", val):
                self._risk_percentage = val
                logger.info(f"Percentual de risco alterado para: {val}%")

    @property
    def max_exposure_percentage(self) -> float:
        return self._max_exposure_percentage

    @max_exposure_percentage.setter
    def max_exposure_percentage(self, val: float):
        if val > 0:
            if self.db.set_config("max_exposure_percentage", val):
                self._max_exposure_percentage = val
                logger.info(f"Máxima exposição de capital alterada para: {val}%")

    @property
    def leverage(self) -> int:
        """Alavancagem SEMPRE retorna 1x. Zero alavancagem – protege o capital."""
        return 1

    @leverage.setter
    def leverage(self, val: int):
        """BLOQUEADO: alavancagem está travada em 1x e não pode ser alterada."""
        logger.warning(
            f"Tentativa de mudar alavancagem para {val}x foi BLOQUEADA. "
            "A alavancagem está permanentemente travada em 1x para proteção do capital."
        )

# Instância única global de configuração
bot_config = BotConfig()
