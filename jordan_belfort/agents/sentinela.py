import asyncio
import logging
import ccxt.pro as ccxtpro
import ccxt
from typing import Dict, List, Optional, Tuple
from jordan_belfort.config import bot_config

logger = logging.getLogger("Sentinela")

class Sentinela:
    """
    Agente 3 (O Sentinela) - Código Puro.
    Monitora o livro de ordens (order book) e o ticker da Binance via WebSockets.
    Busca anomalias de volume, desequilíbrio do book e paredes de liquidez.
    """
    def __init__(self, pairs: List[str] = ["BTCUSDT"]):
        self.pairs = pairs
        self.order_books: Dict[str, Dict] = {}
        self.tickers: Dict[str, Dict] = {}
        
        exchange_options = {
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot'
            }
        }
        use_sandbox = bot_config.binance_use_testnet

        if use_sandbox:
            exchange_options['urls'] = {
                'api': {
                    'public': bot_config.binance_testnet_url,
                    'private': bot_config.binance_testnet_url
                }
            }

        self.exchange = ccxtpro.binance(exchange_options)
        self.rest_exchange = ccxt.binance(exchange_options)
        
        if use_sandbox:
            self.exchange.set_sandbox_mode(True)
            self.rest_exchange.set_sandbox_mode(True)
            logger.info("Sentinela operando com dados de Testnet da Binance.")
        else:
            logger.info("Sentinela operando com dados de Produção da Binance.")

    async def initialize_data(self):
        """Carrega os dados iniciais do ticker e livro de ordens de forma síncrona/REST."""
        for pair in self.pairs:
            try:
                logger.info(f"Carregando order book e ticker iniciais para {pair}...")
                order_book = await asyncio.to_thread(self.rest_exchange.fetch_order_book, pair, 20)
                ticker = await asyncio.to_thread(self.rest_exchange.fetch_ticker, pair)
                self.order_books[pair] = order_book
                self.tickers[pair] = ticker
                logger.info(f"Dados iniciais de {pair} carregados (Bids: {len(order_book['bids'])}, Asks: {len(order_book['asks'])}).")
            except Exception as e:
                logger.error(f"Erro ao carregar dados iniciais de {pair}: {e}")

    def analyze_order_book(self, pair: str) -> Tuple[str, str]:
        """
        Analisa o livro de ordens procurando paredes (walls) significativas
        e define a tendência imediata baseado em desequilíbrio (imbalance).
        """
        ob = self.order_books.get(pair)
        if not ob or not ob.get("bids") or not ob.get("asks"):
            return "no_significant_walls", "consolidation"
            
        bids = ob["bids"][:20]  # [price, amount]
        asks = ob["asks"][:20]
        
        total_bid_vol = sum(b[1] for b in bids)
        total_ask_vol = sum(a[1] for a in asks)
        
        # 1. Detecta Paredes (Walls)
        # Calcula a média dos volumes dos bids/asks para encontrar outliers
        avg_bid_vol = total_bid_vol / len(bids)
        avg_ask_vol = total_ask_vol / len(asks)
        
        strong_bid_wall_price = None
        strong_ask_wall_price = None
        
        for price, amount in bids:
            if amount > avg_bid_vol * 2.5: # 2.5x acima da média é uma parede
                strong_bid_wall_price = price
                break
                
        for price, amount in asks:
            if amount > avg_ask_vol * 2.5:
                strong_ask_wall_price = price
                break
                
        # Classifica a parede de liquidez encontrada
        wall_desc = "neutral"
        if strong_bid_wall_price and strong_ask_wall_price:
            wall_desc = f"bids_wall_at_{strong_bid_wall_price}_asks_wall_at_{strong_ask_wall_price}"
        elif strong_bid_wall_price:
            wall_desc = f"strong_support_at_{strong_bid_wall_price}"
        elif strong_ask_wall_price:
            wall_desc = f"strong_resistance_at_{strong_ask_wall_price}"
            
        # 2. Tendência Imediata (Imbalance Ratio)
        imbalance = total_bid_vol / (total_ask_vol if total_ask_vol > 0 else 1e-9)
        
        # Ticker para checar variação de preço recente
        ticker = self.tickers.get(pair)
        price_change = ticker.get("percentage", 0.0) if ticker else 0.0
        
        immediate_trend = "consolidation"
        if imbalance > 1.5:
            immediate_trend = "momentum_up" if price_change > 0 else "reversal_up"
        elif imbalance < 0.67:
            immediate_trend = "momentum_down" if price_change < 0 else "reversal_down"
        elif abs(price_change) > 1.0:
            immediate_trend = "momentum"
            
        return wall_desc, immediate_trend

    def get_market_structure(self, pair: str) -> Dict[str, str]:
        """Retorna o payload de market structure formatado para o par."""
        wall, trend = self.analyze_order_book(pair)
        return {
            "order_book_wall": wall,
            "immediate_trend": trend
        }

    async def watch_order_book_ws(self):
        """Escuta atualizações do livro de ordens via WebSockets (CCXT Pro)."""
        logger.info("Iniciando escuta do Order Book via WebSocket...")
        while True:
            try:
                for pair in self.pairs:
                    # watch_order_book do CCXT Pro mantém o livro de ordens sincronizado
                    ob = await self.exchange.watch_order_book(pair, 20)
                    self.order_books[pair] = ob
            except Exception as e:
                logger.error(f"Erro na conexao WebSocket do Sentinela (Order Book): {e}. Reconectando em 5 segundos...")
                await asyncio.sleep(5)

    async def watch_ticker_ws(self):
        """Escuta atualizações do ticker via WebSockets (CCXT Pro)."""
        logger.info("Iniciando escuta do Ticker via WebSocket...")
        while True:
            try:
                for pair in self.pairs:
                    ticker = await self.exchange.watch_ticker(pair)
                    self.tickers[pair] = ticker
            except Exception as e:
                logger.error(f"Erro na conexao WebSocket do Sentinela (Ticker): {e}. Reconectando em 5 segundos...")
                await asyncio.sleep(5)

    async def stop(self):
        try:
            await self.exchange.close()
        except Exception as e:
            logger.error(f"Erro ao fechar conexao do Sentinela: {e}")
