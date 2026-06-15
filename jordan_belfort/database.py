import os
import json
import sqlite3
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
    Abstração do Banco de Dados com suporte híbrido:
    Supabase (PostgreSQL) com Fallback automático para SQLite local.
    """
    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        self.use_sqlite = os.getenv("USE_SQLITE_FALLBACK", "true").lower() == "true"
        
        self.client: Optional[Client] = None
        self.sqlite_path = "jordan_belfort.db"
        
        # Tenta conectar ao Supabase primeiro
        if self.supabase_url and self.supabase_key and not self.use_sqlite:
            try:
                self.client = create_client(self.supabase_url, self.supabase_key)
                logger.info("Conectado com sucesso ao Supabase.")
            except Exception as e:
                logger.error(f"Erro ao conectar ao Supabase: {e}. Usando fallback para SQLite.")
                self.use_sqlite = True
        else:
            self.use_sqlite = True
            logger.info(f"Usando banco de dados SQLite local ({self.sqlite_path}).")
            
        if self.use_sqlite:
            self._init_sqlite()

    def _get_sqlite_conn(self):
        """Retorna uma conexão com o banco SQLite local."""
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_sqlite(self):
        """Inicializa as tabelas no SQLite local se elas não existirem."""
        conn = self._get_sqlite_conn()
        cursor = conn.cursor()
        
        # 1. Config
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Inserir valores padrão no SQLite
        default_configs = {
            "status": "paused",
            "risk_percentage": 1.0,
            "max_exposure_percentage": 5.0,
            "leverage": 1
        }
        for k, v in default_configs.items():
            cursor.execute(
                "INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)", 
                (k, json.dumps(v))
            )
            
        # 2. Signals
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER NOT NULL,
            pair TEXT NOT NULL,
            technical_indicators TEXT NOT NULL,
            market_structure TEXT NOT NULL,
            social_sentiment TEXT NOT NULL,
            on_chain_flow TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # 3. Decisions
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER NOT NULL,
            pair TEXT NOT NULL,
            signal_id INTEGER,
            decision TEXT NOT NULL,
            entry_price REAL,
            stop_loss REAL,
            take_profit REAL,
            confidence REAL,
            thesis TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(signal_id) REFERENCES signals(id)
        )
        """)
        
        # 4. Trades
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair TEXT NOT NULL,
            direction TEXT NOT NULL,
            entry_price REAL NOT NULL,
            size REAL NOT NULL,
            stop_loss REAL NOT NULL,
            take_profit REAL NOT NULL,
            status TEXT NOT NULL,
            binance_order_id TEXT,
            entry_time INTEGER NOT NULL,
            exit_time INTEGER,
            exit_price REAL,
            pnl_gross REAL,
            pnl_net REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # 5. Audit Logs
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        conn.commit()
        conn.close()
        logger.info("Banco SQLite inicializado com sucesso.")

    # --- Config Methods ---
    def get_config(self, key: str, default: Any = None) -> Any:
        if not self.use_sqlite and self.client:
            try:
                res = self.client.table("config").select("value").eq("key", key).execute()
                if res.data:
                    return res.data[0]["value"]
            except Exception as e:
                logger.error(f"Erro ao obter config do Supabase: {e}")
        
        # Fallback para SQLite
        conn = self._get_sqlite_conn()
        try:
            row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
            if row:
                return json.loads(row["value"])
        except Exception as e:
            logger.error(f"Erro ao obter config do SQLite: {e}")
        finally:
            conn.close()
        return default

    def set_config(self, key: str, value: Any) -> bool:
        if not self.use_sqlite and self.client:
            try:
                self.client.table("config").upsert({"key": key, "value": value}).execute()
                return True
            except Exception as e:
                logger.error(f"Erro ao salvar config no Supabase: {e}")
        
        # Fallback para SQLite
        conn = self._get_sqlite_conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO config (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)", 
                (key, json.dumps(value))
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar config no SQLite: {e}")
            return False
        finally:
            conn.close()

    # --- Signals Methods ---
    def save_signal(self, timestamp: int, pair: str, technical_indicators: Dict, 
                    market_structure: Dict, social_sentiment: Dict, on_chain_flow: Dict) -> Optional[int]:
        if not self.use_sqlite and self.client:
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
                
        # Fallback para SQLite
        conn = self._get_sqlite_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO signals (timestamp, pair, technical_indicators, market_structure, social_sentiment, on_chain_flow)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                timestamp, pair, 
                json.dumps(technical_indicators), 
                json.dumps(market_structure), 
                json.dumps(social_sentiment), 
                json.dumps(on_chain_flow)
            ))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Erro ao salvar sinal no SQLite: {e}")
            return None
        finally:
            conn.close()

    # --- Decisions Methods ---
    def save_decision(self, timestamp: int, pair: str, signal_id: Optional[int], decision: str, 
                      entry_price: Optional[float], stop_loss: Optional[float], take_profit: Optional[float], 
                      confidence: Optional[float], thesis: Optional[str]) -> Optional[int]:
        if not self.use_sqlite and self.client:
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

        # Fallback para SQLite
        conn = self._get_sqlite_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO decisions (timestamp, pair, signal_id, decision, entry_price, stop_loss, take_profit, confidence, thesis)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp, pair, signal_id, decision, entry_price, stop_loss, take_profit, confidence, thesis
            ))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Erro ao salvar decisao no SQLite: {e}")
            return None
        finally:
            conn.close()

    # --- Trades Methods ---
    def create_trade(self, pair: str, direction: str, entry_price: float, size: float, 
                     stop_loss: float, take_profit: float, binance_order_id: Optional[str], 
                     entry_time: int) -> Optional[int]:
        if not self.use_sqlite and self.client:
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

        # Fallback para SQLite
        conn = self._get_sqlite_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO trades (pair, direction, entry_price, size, stop_loss, take_profit, status, binance_order_id, entry_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pair, direction, entry_price, size, stop_loss, take_profit, "open", binance_order_id, entry_time
            ))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Erro ao criar trade no SQLite: {e}")
            return None
        finally:
            conn.close()

    def update_trade(self, trade_id: int, status: str, exit_time: Optional[int] = None, 
                     exit_price: Optional[float] = None, pnl_gross: Optional[float] = None, 
                     pnl_net: Optional[float] = None) -> bool:
        if not self.use_sqlite and self.client:
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

        # Fallback para SQLite
        conn = self._get_sqlite_conn()
        try:
            conn.execute("""
                UPDATE trades 
                SET status = ?, exit_time = COALESCE(?, exit_time), exit_price = COALESCE(?, exit_price), 
                    pnl_gross = COALESCE(?, pnl_gross), pnl_net = COALESCE(?, pnl_net), updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, exit_time, exit_price, pnl_gross, pnl_net, trade_id))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Erro ao atualizar trade no SQLite: {e}")
            return False
        finally:
            conn.close()

    def get_active_trades(self) -> List[Dict]:
        if not self.use_sqlite and self.client:
            try:
                res = self.client.table("trades").select("*").eq("status", "open").execute()
                return res.data
            except Exception as e:
                logger.error(f"Erro ao obter trades ativos do Supabase: {e}")

        # Fallback para SQLite
        conn = self._get_sqlite_conn()
        try:
            rows = conn.execute("SELECT * FROM trades WHERE status = 'open'").fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Erro ao obter trades ativos do SQLite: {e}")
            return []
        finally:
            conn.close()

    def get_trade(self, trade_id: int) -> Optional[Dict]:
        if not self.use_sqlite and self.client:
            try:
                res = self.client.table("trades").select("*").eq("id", trade_id).execute()
                if res.data:
                    return res.data[0]
            except Exception as e:
                logger.error(f"Erro ao obter trade do Supabase: {e}")

        # Fallback para SQLite
        conn = self._get_sqlite_conn()
        try:
            row = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
            if row:
                return dict(row)
        except Exception as e:
            logger.error(f"Erro ao obter trade do SQLite: {e}")
        finally:
            conn.close()
        return None

    # --- Audit Logs Methods ---
    def log_audit(self, level: str, message: str, details: Optional[Dict] = None) -> bool:
        import time
        timestamp = int(os.environ.get("MOCK_TIME", 0)) or int(time.time() * 1000)
        
        # Tenta escrever no console também
        print(f"[{level}] {message}")
        
        if not self.use_sqlite and self.client:
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

        # Fallback para SQLite
        conn = self._get_sqlite_conn()
        try:
            conn.execute("""
                INSERT INTO audit_logs (timestamp, level, message, details)
                VALUES (?, ?, ?, ?)
            """, (timestamp, level, message, json.dumps(details or {})))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Erro ao logar auditoria no SQLite: {e}")
            return False
        finally:
            conn.close()
