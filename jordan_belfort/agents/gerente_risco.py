import logging
from typing import Dict, Any, Tuple
from jordan_belfort.config import bot_config

logger = logging.getLogger("GerenteRisco")

class GerenteRisco:
    """
    Agente 6 (Gerente de Risco) - Código Puro.
    Validador matemático e compliance do sistema.
    Aplica regras rígidas de controle de capital e possui poder de veto absoluto.
    """
    def __init__(self):
        pass

    def validate_and_calculate(self, decision_payload: Dict[str, Any], 
                               account_balance: float) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Recebe a decisão do Estrategista-Chefe, valida as regras e calcula
        dinamicamente o tamanho da posição.
        
        Retorna:
          - (is_approved, reason, updated_payload)
        """
        # Sincroniza configurações dinâmicas mais recentes do DB
        bot_config.sync_configs()

        # 1. Verifica Kill Switch global (/pausar)
        if bot_config.is_paused:
            return False, "VETO: O sistema de trading está PAUSADO globalmente no banco de dados.", {}

        decision = decision_payload.get("decision", "NEUTRAL").upper()
        if decision == "NEUTRAL":
            return False, "NEUTRAL: Nenhuma ação recomendada pelo Estrategista-Chefe.", {}

        entry_price = decision_payload.get("entry_price")
        stop_loss = decision_payload.get("stop_loss")
        take_profit = decision_payload.get("take_profit")
        pair = decision_payload.get("pair", "BTCUSDT")

        # Validações estruturais básicas
        if not entry_price or not stop_loss or not take_profit:
            return False, "VETO: Preço de entrada, Stop Loss ou Take Profit estão vazios.", {}

        try:
            entry_price = float(entry_price)
            stop_loss = float(stop_loss)
            take_profit = float(take_profit)
        except ValueError:
            return False, "VETO: Valores de preços não puderam ser convertidos para float.", {}

        if entry_price <= 0 or stop_loss <= 0 or take_profit <= 0:
            return False, "VETO: Preços devem ser maiores que zero.", {}

        # 2. Validações direcionais
        if decision == "LONG":
            if stop_loss >= entry_price:
                return False, f"VETO: LONG com Stop Loss ({stop_loss}) acima ou igual à entrada ({entry_price}).", {}
            if take_profit <= entry_price:
                return False, f"VETO: LONG com Take Profit ({take_profit}) abaixo ou igual à entrada ({entry_price}).", {}
        elif decision == "SHORT":
            if stop_loss <= entry_price:
                return False, f"VETO: SHORT com Stop Loss ({stop_loss}) abaixo ou igual à entrada ({entry_price}).", {}
            if take_profit >= entry_price:
                return False, f"VETO: SHORT com Take Profit ({take_profit}) acima ou igual à entrada ({entry_price}).", {}
        else:
            return False, f"VETO: Decisão inválida: {decision}", {}

        # 3. Cálculo dinâmico do Stop Loss Percentage
        stop_loss_pct = abs(entry_price - stop_loss) / entry_price
        
        # Filtro de Stop Loss irrealista (evita ruído de decimais ou gaps extremos)
        if stop_loss_pct < 0.001:  # Menos de 0.1%
            return False, f"VETO: Stop Loss muito curto ({stop_loss_pct * 100:.3f}%). Distância mínima aceita é 0.1%.", {}
        if stop_loss_pct > 0.20:   # Mais de 20%
            return False, f"VETO: Stop Loss muito longo ({stop_loss_pct * 100:.1f}%). Risco excessivo por operação.", {}

        # 4. Cálculo do Tamanho da Posição (Position Size Formula)
        # Position_Size_USD = (Balance * Risk_Percentage) / Stop_Loss_Percentage
        risk_fraction = bot_config.risk_percentage / 100.0
        risk_amount_usd = account_balance * risk_fraction
        
        position_size_usd = risk_amount_usd / stop_loss_pct
        
        # Quantidade do ativo para executar na corretora
        qty = position_size_usd / entry_price

        # 5. Validação da Exposição Máxima por Operação
        # A posição total nominal (Position Size) não pode ultrapassar o limite máximo configurado (ex: 5.0% da banca)
        max_exposure_usd = account_balance * (bot_config.max_exposure_percentage / 100.0)
        
        logger.info(
            f"Análise de Risco: Banca={account_balance:.2f} USD, Risco={bot_config.risk_percentage}%, "
            f"Valor em Risco={risk_amount_usd:.2f} USD, Tamanho da Posição Sugerido={position_size_usd:.2f} USD, "
            f"Exposição Máxima Permitida={max_exposure_usd:.2f} USD"
        )

        if position_size_usd > max_exposure_usd:
            # Em vez de apenas vetar, podemos recalcular a posição para se adequar ao limite de exposição por segurança
            # Ou abortar, como solicita o PRD: "Se violar a exposição máxima, o trade deve ser abortado imediatamente."
            # Seguiremos o PRD estritamente: Abortar imediatamente.
            return False, f"VETO: O tamanho da posição calculado ({position_size_usd:.2f} USD) viola a exposição máxima permitida ({max_exposure_usd:.2f} USD). Trade abortado.", {}

        # Tudo aprovado, prepara payload atualizado com dados calculados
        validated_payload = {
            "pair": pair,
            "decision": decision,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "position_size_usd": round(position_size_usd, 2),
            "quantity": round(qty, 6),
            "risk_amount_usd": round(risk_amount_usd, 2),
            "stop_loss_pct": round(stop_loss_pct * 100, 2),
            "thesis": decision_payload.get("thesis", "Tese não informada.")
        }

        return True, "APROVADO: Regras de risco validadas com sucesso.", validated_payload
