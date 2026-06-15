import os
import json
import logging
from typing import Any, Dict, List, Optional
from supabase import create_client, Client
from dotenv import load_dotenv

# Configura logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Database")

load_dotenv()

class Database:
    """
    Abstração do Banco de Dados apenas com Supabase (PostgreSQL).
    """
    def __init__(self, client: Optional[Client] = None):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        self.client: Optional[Client] = client

        if self.client is not None:
            logger.info("Conectado com sucesso ao Supabase via client injetado.")
            return

        if self.supabase_url and self.supabase_key:
            try:
                self.client = create_client(self.supabase_url, self.supabase_key)
                logger.info("Conectado com sucesso ao Supabase.")
            except Exception as e:
                logger.error(f"Erro ao conectar ao Supabase: {e}.")
                raise RuntimeError("Falha na conexão com Supabase; o banco local não será usado.")
        else:
            raise RuntimeError("SUPABASE_URL e SUPABASE_KEY devem estar configurados para usar apenas Supabase.")

    # --- Config Methods ---
    def get_config(self, key: str, default: Any = None) -> Any:
        if self.client:
            try:
                res = self.client.table("config").select("value").eq("key", key).execute()
                if res.data:
                    return res.data[0]["value"]
            except Exception as e:
                logger.error(f"Erro ao obter config do Supabase: {e}")
                raise
        raise RuntimeError("Conexão com Supabase indisponível para obter config.")

    def set_config(self, key: str, value: Any) -> bool:
        if self.client:
            try:
                self.client.table("config").upsert({"key": key, "value": value}).execute()
                return True
            except Exception as e:
                logger.error(f"Erro ao salvar config no Supabase: {e}")
                raise
        raise RuntimeError("Conexão com Supabase indisponível para salvar config.")

    # --- Signals Methods ---
    def save_signal(self, timestamp: int, pair: str, technical_indicators: Dict, 
                    market_structure: Dict, social_sentiment: Dict, on_chain_flow: Dict) -> Optional[int]:
        if self.client:
            try:
                payload = {
                    "timestamp": timestamp,
                    "pair": pair,
                    "technical_indicators": technical_indicators,
                    "market_structure": market_structure,
                    "social_sentiment": social_sentiment,
                    "on_chain_flow": on_chain_flow
                }
                res = self.client.table("signals").insert(payload).execute()
                if res.data:
                    return res.data[0]["id"]
            except Exception as e:
                logger.error(f"Erro ao salvar sinal no Supabase: {e}")
                raise
        raise RuntimeError("Conexão com Supabase indisponível para salvar signal.")

    # --- Decisions Methods ---
    def save_decision(self, timestamp: int, pair: str, signal_id: Optional[int], decision: str, 
                      entry_price: Optional[float], stop_loss: Optional[float], take_profit: Optional[float], 
                      confidence: Optional[float], thesis: Optional[str]) -> Optional[int]:
        if self.client:
            try:
                payload = {
                    "timestamp": timestamp,
                    "pair": pair,
                    "signal_id": signal_id,
                    "decision": decision,
                    "entry_price": entry_price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "confidence": confidence,
                    "thesis": thesis
                }
                res = self.client.table("decisions").insert(payload).execute()
                if res.data:
                    return res.data[0]["id"]
            except Exception as e:
                logger.error(f"Erro ao salvar decisao no Supabase: {e}")
                raise
        raise RuntimeError("Conexão com Supabase indisponível para salvar decisão.")

    # --- Trades Methods ---
    def create_trade(self, pair: str, direction: str, entry_price: float, size: float, 
                     stop_loss: float, take_profit: float, binance_order_id: Optional[str], 
                     entry_time: int) -> Optional[int]:
        if self.client:
            try:
                payload = {
                    "pair": pair,
                    "direction": direction,
                    "entry_price": entry_price,
                    "size": size,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "status": "open",
                    "binance_order_id": binance_order_id,
                    "entry_time": entry_time
                }
                res = self.client.table("trades").insert(payload).execute()
                if res.data:
                    return res.data[0]["id"]
            except Exception as e:
                logger.error(f"Erro ao criar trade no Supabase: {e}")
                raise
        raise RuntimeError("Conexão com Supabase indisponível para criar trade.")

    def update_trade(self, trade_id: int, status: str, exit_time: Optional[int] = None, 
                     exit_price: Optional[float] = None, pnl_gross: Optional[float] = None, 
                     pnl_net: Optional[float] = None) -> bool:
        if self.client:
            try:
                payload = {
                    "status": status,
                    "updated_at": "now()"
                }
                if exit_time is not None:
                    payload["exit_time"] = exit_time
                if exit_price is not None:
                    payload["exit_price"] = exit_price
                if pnl_gross is not None:
                    payload["pnl_gross"] = pnl_gross
                if pnl_net is not None:
                    payload["pnl_net"] = pnl_net
                    
                self.client.table("trades").update(payload).eq("id", trade_id).execute()
                return True
            except Exception as e:
                logger.error(f"Erro ao atualizar trade no Supabase: {e}")
                raise
        raise RuntimeError("Conexão com Supabase indisponível para atualizar trade.")

    def get_active_trades(self) -> List[Dict]:
        if self.client:
            try:
                res = self.client.table("trades").select("*").eq("status", "open").execute()
                return res.data
            except Exception as e:
                logger.error(f"Erro ao obter trades ativos do Supabase: {e}")
                raise
        raise RuntimeError("Conexão com Supabase indisponível para obter trades ativos.")

    def get_trade(self, trade_id: int) -> Optional[Dict]:
        if self.client:
            try:
                res = self.client.table("trades").select("*").eq("id", trade_id).execute()
                if res.data:
                    return res.data[0]
            except Exception as e:
                logger.error(f"Erro ao obter trade do Supabase: {e}")
                raise
        raise RuntimeError("Conexão com Supabase indisponível para obter trade.")

    # --- Notifications Methods ---
    def save_notification(self, channel: str, message: str, metadata: Optional[Dict] = None) -> Optional[int]:
        if self.client:
            payload = {
                "timestamp": int(__import__("time").time() * 1000),
                "channel": channel,
                "message": message,
                "metadata": metadata or {}
            }
            try:
                res = self.client.table("notifications").insert(payload).execute()
                if res.data:
                    return res.data[0]["id"]
            except Exception as e:
                error_text = str(e)
                if isinstance(e, dict):
                    error_text = str(e)
                if "Could not find the table 'public.notifications'" in error_text or "PGRST205" in error_text:
                    logger.warning("Tabela notifications não encontrada no Supabase. Salvando notificação em audit_logs como fallback.")
                    self.log_audit(
                        level="NOTIFICATION",
                        message=message,
                        details={"channel": channel, "metadata": metadata or {}}
                    )
                    return None
                logger.error(f"Erro ao salvar notificação no Supabase: {e}")
                raise
        raise RuntimeError("Conexão com Supabase indisponível para salvar notificação.")

    def get_recent_notifications(self, limit: int = 10) -> List[Dict]:
        if self.client:
            try:
                res = self.client.table("notifications").select("*").order("timestamp", {"ascending": False}).limit(limit).execute()
                return res.data or []
            except Exception as e:
                error_text = str(e)
                if isinstance(e, dict):
                    error_text = str(e)
                if "Could not find the table 'public.notifications'" in error_text or "PGRST205" in error_text:
                    logger.warning("Tabela notifications não encontrada no Supabase. Lendo notificações de audit_logs como fallback.")
                    res = self.client.table("audit_logs").select("id,timestamp,message,details").eq("level", "NOTIFICATION").order("timestamp", {"ascending": False}).limit(limit).execute()
                    notifications = []
                    if res.data:
                        for row in res.data:
                            notifications.append({
                                "id": row.get("id"),
                                "timestamp": row.get("timestamp"),
                                "message": row.get("message"),
                                "channel": row.get("details", {}).get("channel", "notification"),
                                "metadata": row.get("details", {}).get("metadata", {})
                            })
                    return notifications
                logger.error(f"Erro ao obter notificações do Supabase: {e}")
                raise
        raise RuntimeError("Conexão com Supabase indisponível para obter notificações.")

    # --- Audit Logs Methods ---
    def log_audit(self, level: str, message: str, details: Optional[Dict] = None) -> bool:
        import time
        timestamp = int(os.environ.get("MOCK_TIME", 0)) or int(time.time() * 1000)
        
        # Tenta escrever no console também
        print(f"[{level}] {message}")
        
        if self.client:
            try:
                payload = {
                    "timestamp": timestamp,
                    "level": level,
                    "message": message,
                    "details": details or {}
                }
                self.client.table("audit_logs").insert(payload).execute()
                return True
            except Exception as e:
                logger.error(f"Erro ao logar auditoria no Supabase: {e}")
                raise
        raise RuntimeError("Conexão com Supabase indisponível para logar auditoria.")
