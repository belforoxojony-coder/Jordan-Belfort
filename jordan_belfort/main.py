import asyncio
import logging
import time
from typing import Dict, Any, List
from jordan_belfort.config import bot_config
from jordan_belfort.database import Database
from jordan_belfort.agents.antenado import Antenado
from jordan_belfort.agents.grafista import Grafista
from jordan_belfort.agents.sentinela import Sentinela
from jordan_belfort.agents.onchain import OnChainDetector
from jordan_belfort.agents.estrategista import EstrategistaChefe
from jordan_belfort.agents.gerente_risco import GerenteRisco
from jordan_belfort.agents.executor import Executor
from jordan_belfort.agents.auditor import Auditor
from jordan_belfort.agents.jordan import JordanBelfort

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MainOrchestrator")

# ── Top 15 pares USDT com maior liquidez na Binance (spot) ─────────────────
TOP_PAIRS = [
    "BTCUSDT",   # Bitcoin
    "ETHUSDT",   # Ethereum
    "BNBUSDT",   # BNB
    "SOLUSDT",   # Solana
    "XRPUSDT",   # XRP
    "DOGEUSDT",  # Dogecoin
    "ADAUSDT",   # Cardano
    "AVAXUSDT",  # Avalanche
    "LINKUSDT",  # Chainlink
    "DOTUSDT",   # Polkadot
    "MATICUSDT", # Polygon
    "UNIUSDT",   # Uniswap
    "LTCUSDT",   # Litecoin
    "ATOMUSDT",  # Cosmos
    "FILUSDT",   # Filecoin
]

class JordanBelfortSystem:
    def __init__(self, pairs: List[str] = TOP_PAIRS):
        self.pairs = pairs
        self.db = Database()
        
        # Inicialização dos Agentes
        self.antenado = Antenado()
        self.grafista = Grafista(pairs=self.pairs)
        self.sentinela = Sentinela(pairs=self.pairs)
        self.onchain = OnChainDetector()
        self.estrategista = EstrategistaChefe()
        self.gerente_risco = GerenteRisco()
        self.executor = Executor()
        self.auditor = Auditor()
        self.jordan = JordanBelfort(executor_agent=self.executor)

        self.running = False
        self.active_tasks = []

    async def startup_recovery(self):
        """
        FR-06 / NFR-02: Recuperação de Queda.
        Busca trades ativos no banco de dados e reassume o gerenciamento deles.
        """
        logger.info("=" * 80)
        logger.info("INICIALIZAÇÃO DO SISTEMA JORDAN BELFORT")
        logger.info("=" * 80)
        
        # Health check do executor
        logger.info("VERIFICAÇÃO DE CONECTIVIDADE")
        logger.info("-" * 80)
        
        if self.executor.paper_trading:
            logger.warning("⚠️  EXECUTOR EM MODO PAPER TRADING (SIMULADO)")
            if self.executor.last_balance_fetch_error:
                logger.error(f"   Motivo do erro: {self.executor.last_balance_fetch_error}")
            logger.warning(f"   Saldo fictício: {self.executor.get_balance():.2f} USDT")
        else:
            logger.info("✅ EXECUTOR CONECTADO À API REAL DA BINANCE")
            logger.info(f"   Modo: {'TESTNET' if bot_config.binance_use_testnet else 'PRODUÇÃO'}")
            logger.info(f"   Saldo Real: {self.executor.get_balance():.2f} USDT")
        
        logger.info(f"STATUS DO BOT: {'🟢 ATIVO - FAZENDO TRADES!' if bot_config.status == 'active' else '🔴 PAUSADO - Nenhuma operação será realizada'}")
        logger.info("=" * 80)
        
        logger.info(f"Iniciando verificação de recuperação pós-queda (Crash Recovery)...")
        active_trades = self.db.get_active_trades()
        if not active_trades:
            logger.info("Nenhum trade órfão encontrado. Sistema pronto para operar.")
            return

        logger.warning(f"Encontrado(s) {len(active_trades)} trade(s) órfão(s) no banco de dados! Reassumindo gerenciamento...")
        for trade in active_trades:
            msg = f"Detectado trade órfão #{trade['id']} de {trade['pair']} ({trade['direction']}). Retomando monitoramento de Stop Loss."
            logger.warning(msg)
            # Notifica via Telegram
            await self.jordan.send_notification(msg, format_wolf=True)

    async def check_confluence(self, pair: str) -> bool:
        """
        Avalia se há confluência técnica/social para acionar o Estrategista-Chefe (LLM),
        minimizando custos de API e latência desnecessários.
        """
        # Obter indicadores do Grafista e Sentinela
        indicators = self.grafista.get_indicators(pair)
        rsi = indicators.get("rsi_15m", 50.0)
        macd = indicators.get("macd_trend", "neutral")
        
        # Confluência técnica básica: sobrevenda/sobrecompra no RSI ou cruzamento do MACD
        tech_confluence = (rsi <= 32) or (rsi >= 68) or ("crossover" in macd)

        # Confluência social básica: variação no sentimento do Antenado
        sentiment_data = await self.antenado.get_social_sentiment(pair)
        polarity = sentiment_data.get("sentiment_polarity", 0.5)
        social_confluence = (polarity > 0.65) or (polarity < 0.35)

        if tech_confluence or social_confluence:
            logger.info(
                f"CONFLUÊNCIA DETECTADA para {pair}! "
                f"RSI={rsi}, MACD={macd}, Polador={polarity}. Disparando diretoria..."
            )
            return True
            
        return False

    async def compile_signals_payload(self, pair: str) -> Dict[str, Any]:
        """
        Reúne os inputs estruturados de todos os informantes (Agentes 1, 2, 3, 4)
        no formato JSON padrão exigido pela arquitetura.
        """
        # 1. Antenado (Sentimento)
        social_sentiment = await self.antenado.get_social_sentiment(pair)
        
        # 2. Grafista (Indicadores Técnicos)
        technical_indicators = self.grafista.get_indicators(pair)
        
        # 3. Sentinela (Order Book e Ticker)
        market_structure = self.sentinela.get_market_structure(pair)
        
        # 4. Detetive On-Chain (Fluxos)
        on_chain_flow = self.onchain.get_on_chain_flow(pair)

        # Preço de ticker mais recente
        ticker = self.sentinela.tickers.get(pair, {})
        current_price = ticker.get("last", ticker.get("close", 0.0))
        if not current_price:
            # Fallback para o preço do último candle do Grafista
            df = self.grafista.candles_history.get(pair)
            if df is not None and not df.empty:
                current_price = float(df["close"].iloc[-1])

        # Detecta confluência explícita para passar ao LLM
        rsi = technical_indicators.get("rsi_15m", 50.0)
        macd_trend = technical_indicators.get("macd_trend", "neutral")
        polarity = social_sentiment.get("sentiment_polarity", 0.5)
        
        confluence_detected = (rsi <= 32 or rsi >= 68) or ("crossover" in macd_trend or "bullish" in macd_trend or "bearish" in macd_trend) or (polarity > 0.65 or polarity < 0.35)

        payload = {
            "timestamp": int(time.time() * 1000),
            "pair": pair,
            "current_price": current_price,
            "technical_indicators": technical_indicators,
            "market_structure": market_structure,
            "social_sentiment": social_sentiment,
            "on_chain_flow": on_chain_flow,
            "confluence_detected": confluence_detected,
            "confluence_summary": {
                "rsi_level": "sobrecompra" if rsi >= 68 else ("sobrevenda" if rsi <= 32 else "neutral"),
                "rsi_value": rsi,
                "macd_status": macd_trend,
                "sentiment_polarity": polarity
            }
        }
        
        # Salva o sinal recebido no banco de dados para auditoria histórica
        signal_id = self.db.save_signal(
            timestamp=payload["timestamp"],
            pair=payload["pair"],
            technical_indicators=payload["technical_indicators"],
            market_structure=payload["market_structure"],
            social_sentiment=payload["social_sentiment"],
            on_chain_flow=payload["on_chain_flow"]
        )
        payload["signal_id"] = signal_id
        
        return payload

    async def evaluate_trading_opportunities(self):
        """Loop contínuo de verificação de sinais e oportunidades de trading."""
        logger.info("Iniciando loop de oportunidades de trading...")
        while self.running:
            # Se o bot estiver pausado globalmente, não analisa novas posições
            if bot_config.is_paused:
                await asyncio.sleep(5)
                continue

            for pair in self.pairs:
                try:
                    # Verifica se já temos uma posição aberta para este par
                    active_trades = self.db.get_active_trades()
                    has_open_position = any(t["pair"] == pair for t in active_trades)
                    
                    if has_open_position:
                        continue # Apenas um trade ativo por par por vez

                    # Verifica se há confluência técnica/social
                    if await self.check_confluence(pair):
                        await self.jordan.send_notification(
                            f"CONFLUÊNCIA DETECTADA para {pair}! RSI={self.grafista.get_indicators(pair).get('rsi_15m', 0.0):.2f}, MACD={self.grafista.get_indicators(pair).get('macd_trend', 'neutral')}. Avaliando possibilidade de trade agora...",
                            format_wolf=True
                        )
                        # Compila o payload unificado
                        payload = await self.compile_signals_payload(pair)
                        
                        # Aciona Estrategista-Chefe (LLM)
                        start_time = time.time()
                        decision = self.estrategista.deliberate(payload)
                        elapsed = time.time() - start_time
                        
                        logger.info(f"Deliberação concluída em {elapsed:.2f}s.")

                        # Salva decisão no banco
                        self.db.save_decision(
                            timestamp=int(time.time() * 1000),
                            pair=pair,
                            signal_id=payload.get("signal_id"),
                            decision=decision["decision"],
                            entry_price=decision.get("entry_price"),
                            stop_loss=decision.get("stop_loss"),
                            take_profit=decision.get("take_profit"),
                            confidence=decision.get("confidence_score"),
                            thesis=decision.get("thesis")
                        )

                        if decision["decision"] == "NEUTRAL":
                            await self.jordan.send_notification(
                                f"DECISÃO FINAL para {pair}: NEUTRAL. Nenhuma nova posição será aberta.",
                                format_wolf=True
                            )

                        if decision["decision"] in ["LONG", "SHORT"]:
                            # Consulta saldo disponível
                            balance = self.executor.get_balance()
                            
                            # Validação matemática do Gerente de Risco
                            is_approved, reason, risk_payload = self.gerente_risco.validate_and_calculate(
                                decision_payload=decision,
                                account_balance=balance
                            )
                            
                            if is_approved:
                                # Notifica aprovação imediata do trade
                                logger.info(f"Risco aprovado para {pair}: {reason}")
                                
                                # Envia ordem via Executor
                                success, exec_msg, exec_details = self.executor.place_order(risk_payload)
                                
                                if success:
                                    # Cria trade no banco de dados
                                    trade_id = self.db.create_trade(
                                        pair=pair,
                                        direction=risk_payload["decision"],
                                        entry_price=exec_details["entry_price"],
                                        size=exec_details["size"],
                                        stop_loss=exec_details["stop_loss"],
                                        take_profit=exec_details["take_profit"],
                                        binance_order_id=exec_details["order_id"],
                                        entry_time=exec_details["timestamp"]
                                    )
                                    
                                    # Notificação do Lobo de Wall Street
                                    alert = (
                                        f"ORDEM EXECUTADA! Posição de {risk_payload['decision']} aberta no par {pair}.\n"
                                        f"Preço de Entrada: {exec_details['entry_price']:.2f}\n"
                                        f"Tamanho da Posição: {exec_details['size']} ({risk_payload['position_size_usd']:.2f} USD)\n"
                                        f"Stop Loss definido em: {exec_details['stop_loss']:.2f}\n"
                                        f"Take Profit definido em: {exec_details['take_profit']:.2f}\n"
                                        f"Tese do Trade: {risk_payload['thesis']}"
                                    )
                                    await self.jordan.send_notification(alert, format_wolf=True)
                                else:
                                    logger.error(f"Executor falhou ao abrir ordem: {exec_msg}")
                                    self.db.log_audit("ERROR", f"Falha na execução da ordem: {exec_msg}")
                                    await self.jordan.send_notification(
                                        f"Falha ao abrir ordem para {pair}: {exec_msg}",
                                        format_wolf=True
                                    )
                            else:
                                logger.warning(f"Risco vetou a operação sugerida pelo Estrategista: {reason}")
                                self.db.log_audit("WARNING", f"Operação vetada pelo Gerente de Risco: {reason}")
                                await self.jordan.send_notification(
                                    f"Operação para {pair} vetada pelo Gerente de Risco: {reason}",
                                    format_wolf=True
                                )
                except Exception as e:
                    logger.error(f"Erro no loop de análise de oportunidades para {pair}: {e}")

            await asyncio.sleep(5)

    async def monitor_active_trades(self):
        """
        Monitora trades ativos. Se for Paper Trading, simula saídas quando os limites
        de SL/TP forem atingidos. Se for real, rastreia e confirma saídas na corretora.
        """
        logger.info("Iniciando loop de monitoramento de trades ativos...")
        while self.running:
            try:
                active_trades = self.db.get_active_trades()
                for trade in active_trades:
                    pair = trade["pair"]
                    trade_id = trade["id"]
                    direction = trade["direction"]
                    sl = float(trade["stop_loss"])
                    tp = float(trade["take_profit"])
                    size = float(trade["size"])

                    # Obtém preço atual
                    ticker = self.sentinela.tickers.get(pair, {})
                    current_price = ticker.get("last", ticker.get("close", 0.0))
                    
                    if not current_price:
                        # Fallback para candles do Grafista
                        df = self.grafista.candles_history.get(pair)
                        if df is not None and not df.empty:
                            current_price = float(df["close"].iloc[-1])
                            
                    if not current_price:
                        continue # Aguarda carregamento de dados de mercado

                    # 1. Simulação para Paper Trading
                    if self.executor.paper_trading:
                        triggered = False
                        exit_price = current_price
                        trigger_reason = ""
                        
                        if direction == "LONG":
                            if current_price <= sl:
                                triggered = True
                                exit_price = sl
                                trigger_reason = "STOP LOSS ATINGIDO"
                            elif current_price >= tp:
                                triggered = True
                                exit_price = tp
                                trigger_reason = "TAKE PROFIT ATINGIDO"
                        elif direction == "SHORT":
                            if current_price >= sl:
                                triggered = True
                                exit_price = sl
                                trigger_reason = "STOP LOSS ATINGIDO"
                            elif current_price <= tp:
                                triggered = True
                                exit_price = tp
                                trigger_reason = "TAKE PROFIT ATINGIDO"

                        if triggered:
                            logger.info(f"[Paper Trading] Trigger disparado para Trade #{trade_id} ({pair}): {trigger_reason} @ {exit_price}")
                            
                            # Auditoria e fechamento
                            audit_res = self.auditor.audit_trade_close(
                                trade_id=trade_id,
                                exit_price=exit_price,
                                exit_time=int(time.time() * 1000),
                                paper_trading=True
                            )
                            
                            pnl_net = audit_res["pnl_net"] if audit_res else 0.0
                            status_emoji = "💰" if pnl_net > 0 else "❌"
                            
                            # Notificação de encerramento do Lobo
                            report = (
                                f"{status_emoji} POSIÇÃO ENCERRADA ({trigger_reason})!\n"
                                f"Par: {pair} | Direção: {direction}\n"
                                f"Preço de Saída: {exit_price:.2f} (Entrada: {trade['entry_price']:.2f})\n"
                                f"Lucro/Prejuízo Líquido Realizado: {pnl_net:.2f} USD\n"
                                f"A banca atualizada agradece. Vamos buscar a próxima presa!"
                            )
                            await self.jordan.send_notification(report, format_wolf=True)
                            
                    # 2. Rastreamento Real (Binance)
                    else:
                        try:
                            # Verifica ordens pendentes do par na Binance para ver se SL ou TP executou
                            orders = self.executor.exchange.fetch_open_orders(pair)
                            # Se não houver ordens abertas, significa que ou SL ou TP executou
                            if len(orders) == 0:
                                # Encontra o histórico recente de trades para saber o preço exato de saída
                                user_trades = self.executor.exchange.fetch_my_trades(pair, limit=5)
                                # Filtra trades ocorridos após a entrada
                                recent_exits = [t for t in user_trades if t['timestamp'] > trade['entry_time']]
                                
                                exit_price = current_price
                                if recent_exits:
                                    # Pega o preço de saída real
                                    exit_price = sum(t['price'] for t in recent_exits) / len(recent_exits)
                                
                                logger.info(f"Detecção real: Posição do trade #{trade_id} foi encerrada na Binance.")
                                
                                # Auditoria
                                audit_res = self.auditor.audit_trade_close(
                                    trade_id=trade_id,
                                    exit_price=exit_price,
                                    exit_time=int(time.time() * 1000),
                                    paper_trading=False
                                )
                                
                                pnl_net = audit_res["pnl_net"] if audit_res else 0.0
                                status_emoji = "💰" if pnl_net > 0 else "❌"
                                
                                report = (
                                    f"{status_emoji} POSIÇÃO ENCERRADA NA BINANCE!\n"
                                    f"Par: {pair} | Direção: {direction}\n"
                                    f"Preço de Saída Real: {exit_price:.2f} (Entrada: {trade['entry_price']:.2f})\n"
                                    f"Lucro/Prejuízo Líquido: {pnl_net:.2f} USD"
                                )
                                await self.jordan.send_notification(report, format_wolf=True)
                        except Exception as e:
                            logger.error(f"Erro ao verificar status real de posições na Binance para {pair}: {e}")
            except Exception as e:
                logger.error(f"Erro no loop de monitoramento de trades: {e}")

            await asyncio.sleep(2)

    async def start(self):
        """Inicia todos os agentes e threads de monitoramento em paralelo."""
        self.running = True
        
        # 1. Carrega dados históricos iniciais (REST)
        await self.grafista.initialize_history()
        await self.sentinela.initialize_data()
        
        # 2. Inicializa o canal do Telegram
        await self.jordan.start_bot()

        # 3. Crash Recovery imediato após inicializar Telegram
        await self.startup_recovery()

        # 4. Inicia WebSockets e loops de processamento assíncronos
        self.active_tasks = [
            asyncio.create_task(self.grafista.watch_klines_ws()),
            asyncio.create_task(self.sentinela.watch_order_book_ws()),
            asyncio.create_task(self.sentinela.watch_ticker_ws()),
            asyncio.create_task(self.evaluate_trading_opportunities()),
            asyncio.create_task(self.monitor_active_trades())
        ]
        
        logger.info("Sistema Multiagente Híbrido Jordan Belfort ativado com sucesso!")
        
        # Aguarda indefinidamente a conclusão das tarefas
        await asyncio.gather(*self.active_tasks, return_exceptions=True)

    async def stop(self):
        """Finaliza todos os agentes de forma controlada."""
        logger.info("Encerrando sistema multiagente...")
        self.running = False
        
        for task in self.active_tasks:
            task.cancel()
            
        await self.grafista.stop()
        await self.sentinela.stop()
        await self.jordan.stop()
        logger.info("Sistema multiagente encerrado.")

if __name__ == "__main__":
    # Ponto de entrada padrão — opera todas as principais criptos em simultâneo
    system = JordanBelfortSystem(pairs=TOP_PAIRS)
    try:
        asyncio.run(system.start())
    except KeyboardInterrupt:
        logger.info("Encerrando via terminal...")
        asyncio.run(system.stop())
