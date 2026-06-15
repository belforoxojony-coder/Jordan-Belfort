import logging
import time
from typing import Dict, Any, Optional
from jordan_belfort.database import Database

logger = logging.getLogger("Auditor")

class Auditor:
    """
    Agente 8 (O Auditor) - Código Puro.
    Responsável pela contabilidade pós-trade.
    Calcula PnL real líquido de taxas, atualiza saldos no DB e gerencia métricas.
    """
    def __init__(self):
        self.db = Database()
        self.fee_rate = 0.0005 # 0.05% taxa padrão (futures taker fee na Binance)

    def audit_trade_close(self, trade_id: int, exit_price: float, 
                          exit_time: int, paper_trading: bool) -> Optional[Dict[str, Any]]:
        """
        Calcula o PnL bruto e líquido de um trade, atualiza o banco de dados
        e reajusta a banca se for Paper Trading.
        """
        trade = self.db.get_trade(trade_id)
        if not trade:
            logger.error(f"Tentativa de auditoria em trade inexistente: {trade_id}")
            return None

        entry_price = float(trade["entry_price"])
        size = float(trade["size"])
        direction = trade["direction"]

        # 1. Cálculo de PnL Bruto
        if direction == "LONG":
            pnl_gross = (exit_price - entry_price) * size
        else: # SHORT
            pnl_gross = (entry_price - exit_price) * size

        # 2. Cálculo de Taxas (Entrada + Saída)
        entry_fee = entry_price * size * self.fee_rate
        exit_fee = exit_price * size * self.fee_rate
        total_fees = entry_fee + exit_fee

        # 3. PnL Líquido
        pnl_net = pnl_gross - total_fees

        # 4. Atualiza o registro do trade no Banco de Dados
        self.db.update_trade(
            trade_id=trade_id,
            status="closed",
            exit_time=exit_time,
            exit_price=exit_price,
            pnl_gross=round(pnl_gross, 4),
            pnl_net=round(pnl_net, 4)
        )

        # 5. Se for Paper Trading, reajusta o saldo simulado
        if paper_trading:
            current_balance = float(self.db.get_config("paper_balance", 10000.0))
            new_balance = current_balance + pnl_net
            self.db.set_config("paper_balance", round(new_balance, 2))
            logger.info(f"[Paper Trading] Auditor atualizou saldo fictício de {current_balance:.2f} para {new_balance:.2f}")

        # Registrar log no Auditor
        msg = f"Auditoria Concluída - Trade #{trade_id} ({trade['pair']}): PnL Bruto={pnl_gross:.2f} USD, Taxas={total_fees:.2f} USD, PnL Líquido={pnl_net:.2f} USD"
        logger.info(msg)
        
        self.db.log_audit(
            level="TRADE",
            message=msg,
            details={
                "trade_id": trade_id,
                "pair": trade["pair"],
                "direction": direction,
                "pnl_gross": pnl_gross,
                "fees": total_fees,
                "pnl_net": pnl_net
            }
        )

        return {
            "pnl_gross": pnl_gross,
            "fees": total_fees,
            "pnl_net": pnl_net
        }
