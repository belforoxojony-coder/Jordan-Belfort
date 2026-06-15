import asyncio
import logging
import pandas as pd
import numpy as np
import ccxt.pro as ccxtpro
import ccxt
from typing import Dict, List, Optional
from jordan_belfort.config import bot_config

logger = logging.getLogger("Grafista")

class Grafista:
    """
    Agente 2 (O Grafista) - Código Puro.
    Consome dados de velas (Klines/Candles) da Binance via WebSocket (ou REST polling).
    Calcula indicadores técnicos em tempo real (RSI, MACD, Médias Móveis, ATR).
    """
    def __init__(self, pairs: List[str] = ["BTCUSDT"]):
        self.pairs = pairs
        self.candles_history: Dict[str, pd.DataFrame] = {}
        self.limit = 100  # quantidade de velas para histórico
        self.timeframe = "15m"
        
        # Inicializa o cliente Binance (CCXT)
        exchange_options = {
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot'  # Opera no mercado Spot
            }
        }
        # Como o testnet de Futures da Binance foi desativado/depreciado e é instável,
        # forçamos o uso dos feeds públicos de produção da Binance para obter dados reais de mercado 24/7.
        use_sandbox = False

        self.exchange = ccxtpro.binance(exchange_options)
        self.rest_exchange = ccxt.binance(exchange_options)
        
        if use_sandbox:
            self.exchange.set_sandbox_mode(True)
            self.rest_exchange.set_sandbox_mode(True)
            logger.info("Grafista operando em Sandbox Mode (Testnet).")
        else:
            logger.info("Grafista operando com dados de Produção da Binance.")

    async def initialize_history(self):
        """Carrega dados históricos iniciais via REST para cada par."""
        for pair in self.pairs:
            try:
                logger.info(f"Carregando histórico de candles para {pair} ({self.timeframe})...")
                # CCXT fetch_ohlcv retorna [timestamp, open, high, low, close, volume]
                ohlcv = await asyncio.to_thread(
                    self.rest_exchange.fetch_ohlcv, pair, self.timeframe, limit=self.limit
                )
                self._update_candles_dataframe(pair, ohlcv)
                logger.info(f"Histórico inicial de {pair} carregado: {len(self.candles_history[pair])} velas.")
            except Exception as e:
                logger.error(f"Erro ao carregar histórico inicial para {pair}: {e}")
                # Cria DataFrame vazio para evitar crash
                self.candles_history[pair] = pd.DataFrame(
                    columns=["timestamp", "open", "high", "low", "close", "volume"]
                )

    def _update_candles_dataframe(self, pair: str, ohlcv_list: List[List]):
        """Converte dados brutos de velas do CCXT em um DataFrame pandas estruturado."""
        df = pd.DataFrame(ohlcv_list, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        self.candles_history[pair] = df.sort_values("timestamp").tail(self.limit).reset_index(drop=True)

    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calcula o RSI (Relative Strength Index)."""
        if len(df) < period + 1:
            return 50.0
        close = df["close"]
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        
        # Média móvel exponencial modificada de gain e loss
        avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
        avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
        
        # Evita divisão por zero
        avg_loss = avg_loss.replace(0, 1e-9)
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1])

    def calculate_macd(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calcula o MACD (12, 26, 9) e determina a tendência / cruzamento.
        """
        if len(df) < 26:
            return {"macd": 0.0, "signal": 0.0, "hist": 0.0, "trend": "neutral"}
            
        close = df["close"]
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist = macd_line - signal_line
        
        # Determina tendência e cruzamentos recentes
        curr_macd, prev_macd = macd_line.iloc[-1], macd_line.iloc[-2]
        curr_sig, prev_sig = signal_line.iloc[-1], signal_line.iloc[-2]
        
        trend = "neutral"
        if prev_macd < prev_sig and curr_macd >= curr_sig:
            trend = "bullish_crossover"
        elif prev_macd > prev_sig and curr_macd <= curr_sig:
            trend = "bearish_crossover"
        elif curr_macd > curr_sig:
            # Divergência/direção de alta
            trend = "bullish" if macd_hist.iloc[-1] > macd_hist.iloc[-2] else "bullish_weakening"
        elif curr_macd < curr_sig:
            # Divergência/direção de baixa
            trend = "bearish" if macd_hist.iloc[-1] < macd_hist.iloc[-2] else "bearish_weakening"
            
        return {
            "macd": float(curr_macd),
            "signal": float(curr_sig),
            "hist": float(macd_hist.iloc[-1]),
            "trend": trend
        }

    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calcula o ATR (Average True Range)."""
        if len(df) < period + 1:
            return 0.0
            
        high = df["high"]
        low = df["low"]
        close_prev = df["close"].shift(1)
        
        tr1 = high - low
        tr2 = (high - close_prev).abs()
        tr3 = (low - close_prev).abs()
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return float(atr.iloc[-1])

    def get_indicators(self, pair: str) -> Dict[str, Any]:
        """Calcula e retorna os indicadores atuais para um par específico."""
        df = self.candles_history.get(pair)
        if df is None or df.empty or len(df) < 30:
            return {
                "rsi_15m": 50.0,
                "macd_trend": "neutral",
                "atr_volatility": 0.0
            }
            
        rsi = self.calculate_rsi(df)
        macd_res = self.calculate_macd(df)
        atr = self.calculate_atr(df)
        
        return {
            "rsi_15m": round(rsi, 2),
            "macd_trend": macd_res["trend"],
            "atr_volatility": round(atr, 4)
        }

    async def watch_klines_ws(self):
        """Escuta atualizações de velas via WebSockets do CCXT Pro."""
        logger.info("Iniciando escuta de Klines da Binance via WebSocket...")
        while True:
            # Caso a flag global pausar esteja ativa, ainda atualizamos o histórico
            try:
                for pair in self.pairs:
                    # watchOHLCV assincronamente puxa dados reais de vela fechada/atual
                    # O retorno é do tipo: [ [timestamp, open, high, low, close, volume] ]
                    ohlcv = await self.exchange.watch_ohlcv(pair, self.timeframe)
                    if ohlcv:
                        # Pega o histórico atual
                        df_current = self.candles_history.get(pair)
                        if df_current is not None:
                            # Mescla com novas velas
                            new_data = [[c[0], c[1], c[2], c[3], c[4], c[5]] for c in ohlcv]
                            new_df = pd.DataFrame(new_data, columns=["timestamp", "open", "high", "low", "close", "volume"])
                            new_df["timestamp"] = pd.to_datetime(new_df["timestamp"], unit="ms")
                            
                            # Atualiza as linhas correspondentes ou concatena
                            combined = pd.concat([df_current, new_df]).drop_duplicates(subset=["timestamp"], keep="last")
                            self.candles_history[pair] = combined.sort_values("timestamp").tail(self.limit).reset_index(drop=True)
            except Exception as e:
                logger.error(f"Erro na conexao WebSocket do Grafista: {e}. Tentando se reconectar em 5 segundos...")
                await asyncio.sleep(5)
                # Tenta inicializar novamente
                try:
                    await self.exchange.close()
                except:
                    pass
                await self.initialize_history()

    async def stop(self):
        try:
            await self.exchange.close()
        except Exception as e:
            logger.error(f"Erro ao fechar conexao do Grafista: {e}")
