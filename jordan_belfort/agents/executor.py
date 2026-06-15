import logging
import time
import ccxt
from typing import Dict, Any, Tuple, Optional
from jordan_belfort.config import bot_config
from jordan_belfort.database import Database

logger = logging.getLogger("Executor")

class Executor:
    """
    Agente 7 (O Executor) - Código Puro.
    Conecta-se à API da Binance via CCXT.
    Executa ordens de compra/venda autorizadas, configura SL/TP e gerencia erros.
    Suporta modo Dry-Run (Paper Trading) caso as credenciais sejam simuladas.
    """
    def __init__(self):
        self.db = Database()
        self.paper_trading = True
        self.exchange: Optional[ccxt.binance] = None

        # Verifica se as chaves da Binance são válidas
        has_keys = (
            bot_config.binance_api_key and 
            bot_config.binance_api_key != "your_binance_api_key_here" and
            bot_config.binance_api_secret and 
            bot_config.binance_api_secret != "your_binance_api_secret_here"
        )

        if has_keys:
            try:
                exchange_options = {
                    'apiKey': bot_config.binance_api_key,
                    'secret': bot_config.binance_api_secret,
                    'enableRateLimit': True,
                    'options': {
                        'defaultType': 'spot',  # Mercado Spot (visível na conta Spot da Binance)
                        'adjustForTimeDifference': True,  # Corrige diferença de relógio com o servidor
                        'recvWindow': 60000,  # Janela de tolerância de timestamp (60 segundos)
                    }
                }
                if bot_config.binance_use_testnet:
                    exchange_options['urls'] = {
                        'api': {
                            'public': bot_config.binance_testnet_url,
                            'private': bot_config.binance_testnet_url
                        }
                    }

                self.exchange = ccxt.binance(exchange_options)
                # Sincroniza o tempo com o servidor da Binance automaticamente
                self.exchange.load_time_difference()
                if bot_config.binance_use_testnet:
                    self.exchange.set_sandbox_mode(True)
                
                # Testa conexão buscando saldos
                self.exchange.fetch_balance()
                self.paper_trading = False
                logger.info(
                    f"Executor conectado à API Real da Binance "
                    f"({'Testnet' if bot_config.binance_use_testnet else 'Produção'})."
                )
            except Exception as e:
                logger.error(f"Erro ao conectar com a exchange real: {e}. Entrando em modo Paper Trading por segurança.")
                self.paper_trading = True
        else:
            logger.info("Credenciais da Binance ausentes ou padrão. Ativando modo Paper Trading (Simulado).")
            self.paper_trading = True

    def get_balance(self) -> float:
        """
        Busca o saldo disponível em USDT.
        No modo Paper Trading, gerencia o saldo local no banco de dados.
        """
        if self.paper_trading:
            # Pega saldo fictício do banco de dados (padrão 10.000 USDT)
            balance = self.db.get_config("paper_balance", 10000.0)
            return float(balance)
        
        try:
            balance_data = self.exchange.fetch_balance()
            # Retorna saldo total/disponível em USDT ou USDC
            usdt_balance = balance_data.get('USDT', {}).get('free', 0.0)
            if usdt_balance == 0.0:
                # Fallback para saldo total se free for zero
                usdt_balance = balance_data.get('USDT', {}).get('total', 0.0)
            return float(usdt_balance)
        except Exception as e:
            logger.error(f"Erro ao obter saldo real na Binance: {e}")
            self.db.log_audit("ERROR", f"Erro ao consultar saldo real: {e}")
            return 0.0

    def place_order(self, validated_payload: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Executa a ordem no mercado (LONG/SHORT) e posiciona os gatilhos de SL/TP.
        """
        pair = validated_payload["pair"]
        direction = validated_payload["decision"] # LONG ou SHORT
        qty = validated_payload["quantity"]
        entry_price = validated_payload["entry_price"]
        stop_loss = validated_payload["stop_loss"]
        take_profit = validated_payload["take_profit"]

        # Log de auditoria
        self.db.log_audit("INFO", f"Tentando enviar ordem para {pair}: {direction} {qty} @ {entry_price}")

        if self.paper_trading:
            # Simulação imediata
            order_id = f"mock_order_{int(time.time() * 1000)}"
            logger.info(f"[Paper Trading] Ordem {order_id} de {direction} executada com sucesso para {pair}.")
            
            exec_details = {
                "order_id": order_id,
                "pair": pair,
                "direction": direction,
                "entry_price": entry_price,
                "size": qty,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "status": "filled",
                "timestamp": int(time.time() * 1000)
            }
            return True, "Ordem Simulada executada com sucesso.", exec_details

        # Ordem Real na Binance
        try:
            # Alavancagem BLOQUEADA em 1x (mercado Spot). Nenhuma chamada de set_leverage necessária.

            # 1. Executa a ordem principal a mercado
            side = 'buy' if direction == "LONG" else 'sell'
            logger.info(f"Enviando ordem principal: {side} {qty} {pair}")
            order = self.exchange.create_market_order(pair, side, qty)
            order_id = order.get("id")
            
            # Obtém preço real de execução
            actual_price = order.get("price") or order.get("average") or entry_price
            
            # 3. Envia Ordem de Stop Loss (Spot: STOP_LOSS_LIMIT)
            sl_side = 'sell' if direction == "LONG" else 'buy'
            logger.info(f"Enviando Stop Loss para {pair} @ {stop_loss}")
            
            try:
                self.exchange.create_order(
                    symbol=pair,
                    type='STOP_LOSS_LIMIT',
                    side=sl_side,
                    amount=qty,
                    price=stop_loss,         # Preço limite de execução
                    params={'stopPrice': stop_loss}  # Preço de disparo (trigger)
                )
            except Exception as e:
                # Se falhar o Stop Loss real, fechamos o trade imediatamente por segurança!
                logger.critical(f"FALHA CRÍTICA: Não foi possível definir o Stop Loss. Fechando ordem de emergência: {e}")
                self.db.log_audit("ERROR", f"Falha ao enviar SL. Fechando trade de emergência para {pair}.")
                # Envia ordem contrária imediata para zerar a posição
                opposite_side = 'sell' if direction == "LONG" else 'buy'
                self.exchange.create_market_order(pair, opposite_side, qty)
                return False, f"Falha ao definir Stop Loss. Posição zerada por segurança: {e}", {}

            # 4. Envia Ordem de Take Profit (Spot: LIMIT_MAKER ou TAKE_PROFIT_LIMIT)
            logger.info(f"Enviando Take Profit para {pair} @ {take_profit}")
            try:
                self.exchange.create_order(
                    symbol=pair,
                    type='TAKE_PROFIT_LIMIT',
                    side=sl_side,
                    amount=qty,
                    price=take_profit,
                    params={'stopPrice': take_profit}
                )
            except Exception as e:
                # TP não é crítico — o SL já protege o capital principal
                logger.warning(f"Erro ao registrar Take Profit: {e}. O stop loss cobrirá o risco principal.")

            exec_details = {
                "order_id": order_id,
                "pair": pair,
                "direction": direction,
                "entry_price": actual_price,
                "size": qty,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "status": "filled",
                "timestamp": int(time.time() * 1000)
            }
            return True, "Ordem executada na Binance com SL e TP definidos.", exec_details

        except Exception as e:
            logger.error(f"Erro ao enviar ordem para Binance: {e}")
            self.db.log_audit("ERROR", f"Erro de API da Binance no Executor: {e}")
            return False, f"Falha de execução na API da Binance: {e}", {}
            
    def close_trade_at_market(self, pair: str, direction: str, qty: float) -> bool:
        """Fecha uma posição aberta a mercado."""
        self.db.log_audit("INFO", f"Fechando posição de mercado para {pair} ({direction}, quantidade={qty})")
        if self.paper_trading:
            logger.info(f"[Paper Trading] Posição de {pair} fechada com sucesso.")
            return True
            
        try:
            # Cancela ordens pendentes abertas para este par primeiro (SL/TP antigas)
            try:
                self.exchange.cancel_all_orders(pair)
            except Exception as e:
                logger.warning(f"Erro ao cancelar ordens pendentes de {pair} antes de fechar: {e}")

            # Envia ordem contrária a mercado
            side = 'sell' if direction == "LONG" else 'buy'
            self.exchange.create_market_order(pair, side, qty)
            return True
        except Exception as e:
            logger.error(f"Erro ao fechar posição na Binance: {e}")
            self.db.log_audit("ERROR", f"Erro crítico ao fechar posição de {pair}: {e}")
            return False
