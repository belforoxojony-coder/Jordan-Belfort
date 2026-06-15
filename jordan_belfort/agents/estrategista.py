import json
import logging
from typing import Dict, Any, Optional
from openai import OpenAI
from jordan_belfort.config import bot_config

logger = logging.getLogger("Estrategista")

class EstrategistaChefe:
    """
    Agente 5 (Estrategista-Chefe) - IA Generativa (LLM).
    O cérebro do sistema. Recebe o payload JSON consolidado dos informantes (1, 2, 3, 4).
    Analisa os dados cognitivamente e retorna uma decisão estruturada de trade.
    """
    def __init__(self):
        # Só inicializa se houver chaves reais configuradas
        has_openai = bot_config.openai_api_key and bot_config.openai_api_key != "your_openai_api_key_here"
        has_groq = bot_config.groq_api_key and bot_config.groq_api_key != "your_groq_api_key_here"

        if bot_config.llm_provider == "openai" and has_openai:
            self.client = OpenAI(api_key=bot_config.openai_api_key)
        elif bot_config.llm_provider == "groq" and has_groq:
            self.client = OpenAI(
                api_key=bot_config.groq_api_key,
                base_url="https://api.groq.com/openai/v1"
            )
        else:
            self.client = None
            logger.warning("Nenhum cliente LLM configurado. O Estrategista-Chefe operará com fallback Neutro.")

    def _get_fallback_decision(self, reason: str) -> Dict[str, Any]:
        """Retorna uma decisão Neutra de fallback em caso de erros ou ausência de LLM."""
        return {
            "decision": "NEUTRAL",
            "entry_price": None,
            "stop_loss": None,
            "take_profit": None,
            "confidence_score": 0.0,
            "thesis": f"Decisão Neutra por Fallback: {reason}"
        }

    def deliberate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Consome os dados consolidados e consulta o LLM para obter a decisão de trade.
        Se não houver LLM, usa lógica determinística baseada em confluência.
        """
        # Se não houver LLM, usa fallback determinístico baseado em indicadores
        if not self.client:
            return self._deliberate_fallback_deterministic(payload)

        pair = payload.get("pair", "BTCUSDT")
        current_price = payload.get("current_price", 0.0)
        confluence_detected = payload.get("confluence_detected", False)
        confluence_summary = payload.get("confluence_summary", {})

        # Monta prompt estruturado COM ÉNFASE EM CONFLUÊNCIA
        system_instruction = (
            "Você é o Estrategista-Chefe de um fundo quantitativo de alta performance operando cripto.\n"
            "Sua tarefa é analisar o payload JSON de entrada que consolida dados técnicos, livro de ofertas, "
            "fluxo on-chain e sentimento social para deliberar a direção do trade.\n"
            "Você deve responder OBRIGATORIAMENTE com um objeto JSON estruturado contendo a decisão de viabilidade.\n"
            "\n"
            "INSTRUÇÃO CRÍTICA: SE CONFLUENCE_DETECTED FOR TRUE, VOCÊ DEVE TOMAR UMA DECISÃO DIRETIVA (LONG OU SHORT).\n"
            "Confluência significa alinhamento de múltiplos indicadores - NÃO retorne NEUTRAL quando houver confluência.\n"
            "\n"
            "REGRAS DE DECISÃO:\n"
            "1. Os únicos valores permitidos para 'decision' são 'LONG', 'SHORT' ou 'NEUTRAL'.\n"
            "2. Se confluence_detected = true e RSI estiver em sobrevenda (<=32): RETORNE 'LONG' com confidence >= 0.5\n"
            "3. Se confluence_detected = true e RSI estiver em sobrecompra (>=68): RETORNE 'SHORT' com confidence >= 0.5\n"
            "4. Se confluence_detected = true e MACD estiver em crossover bullish: RETORNE 'LONG' com confidence >= 0.4\n"
            "5. Se confluence_detected = true e MACD estiver em crossover bearish: RETORNE 'SHORT' com confidence >= 0.4\n"
            "6. Se decision for LONG ou SHORT, defina entry_price, stop_loss e take_profit baseados em ATR:\n"
            "   - LONG: stop_loss < entry_price < take_profit\n"
            "   - SHORT: stop_loss > entry_price > take_profit\n"
            "7. O Stop Loss deve respeitar uma relação risco-retorno mínima de 1.5x (ex: se arriscar R$ 100, deve buscar ganhar R$ 150).\n"
            "8. Se os dados indicarem confluência mas você tiver dúvidas: FAVOR ERRAR PARA O LADO DA AÇÃO (LONG/SHORT).\n"
            "9. Retorne APENAS o JSON válido. Não adicione markdown, blocos de código (ex: ```json) ou qualquer outro texto.\n"
        )

        # Monta prompt do usuário com destaque para confluência
        confluence_note = ""
        if confluence_detected:
            confluence_note = f"\n⚠️ ATENÇÃO: CONFLUÊNCIA JÁ DETECTADA PELO SISTEMA:\n{json.dumps(confluence_summary, indent=2)}\n"

        user_prompt = (
            f"Preço de Mercado Atual: {current_price}\n"
            f"Confluência Detectada: {confluence_detected}\n"
            f"{confluence_note}"
            f"Consolidação de Sinais para análise:\n"
            f"{json.dumps(payload, indent=2)}\n\n"
            "Retorne a sua deliberação seguindo estritamente este formato JSON:\n"
            "{\n"
            "  \"decision\": \"LONG\" | \"SHORT\" | \"NEUTRAL\",\n"
            "  \"entry_price\": float,\n"
            "  \"stop_loss\": float,\n"
            "  \"take_profit\": float,\n"
            "  \"confidence_score\": float (de 0.0 a 1.0),\n"
            "  \"thesis\": \"Sua justificativa de trade curta e assertiva\"\n"
            "}"
        )

        try:
            # Invoca o LLM com temperature ligeiramente mais alta para criatividade
            response = self.client.chat.completions.create(
                model=bot_config.llm_model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}, # Força formato JSON nativamente se suportado
                temperature=0.3,  # Aumentado de 0.2 para permitir mais variabilidade
                max_tokens=400
            )

            response_content = response.choices[0].message.content.strip()
            logger.info(f"Resposta bruta do Estrategista: {response_content}")

            # Limpa qualquer resquício de markdown code block se gerado por engano
            if response_content.startswith("```"):
                lines = response_content.splitlines()
                # Remove primeira e última linha se forem ```
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                response_content = "\n".join(lines).strip()

            result = json.loads(response_content)
            
            # Validações básicas pós-parseamento
            decision = result.get("decision", "NEUTRAL").upper()
            if decision not in ["LONG", "SHORT", "NEUTRAL"]:
                result["decision"] = "NEUTRAL"
                
            # Verifica coerência matemática mínima de Stop Loss / Take Profit
            if decision in ["LONG", "SHORT"]:
                entry = float(result.get("entry_price") or current_price)
                sl = float(result.get("stop_loss", 0))
                tp = float(result.get("take_profit", 0))
                
                # Se faltar parâmetros de proteção, anula o trade por segurança
                if not sl or not tp or entry <= 0 or sl <= 0 or tp <= 0:
                    logger.warning(f"Sinal de {decision} veio com preços SL/TP inválidos ou ausentes.")
                    return self._get_fallback_decision("SL/TP ausentes no sinal de trading do LLM")
                    
                if decision == "LONG" and (sl >= entry or tp <= entry):
                    return self._get_fallback_decision("Incoerência matemática em LONG: SL acima ou TP abaixo da entrada")
                elif decision == "SHORT" and (sl <= entry or tp >= entry):
                    return self._get_fallback_decision("Incoerência matemática em SHORT: SL abaixo ou TP acima da entrada")
            
            return result

        except json.JSONDecodeError as jde:
            logger.error(f"Erro ao parsear JSON do Estrategista: {jde}. Resposta: {response_content}")
            # Se houver confluência detectada e o LLM falhar, usa determinístico agressivo
            if confluence_detected:
                return self._deliberate_fallback_deterministic(payload)
            else:
                return self._get_fallback_decision("Falha no parsing JSON da LLM")
        except Exception as e:
            logger.error(f"Erro geral durante deliberação do Estrategista-Chefe: {e}")
            # Se houver confluência detectada e o LLM falhar, usa determinístico
            if confluence_detected:
                return self._deliberate_fallback_deterministic(payload)
            else:
                return self._get_fallback_decision(f"Erro na chamada LLM: {str(e)}")

    def _deliberate_fallback_deterministic(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fallback determinístico baseado em análise técnica quando LLM não está disponível.
        Útil para testes e validação sem custos de API.
        """
        current_price = payload.get("current_price", 0.0)
        technical = payload.get("technical_indicators", {})
        market_struct = payload.get("market_structure", {})
        social = payload.get("social_sentiment", {})
        
        rsi = technical.get("rsi_15m", 50.0)
        macd_trend = technical.get("macd_trend", "neutral")
        atr = technical.get("atr_volatility", 0.0)
        polarity = social.get("sentiment_polarity", 0.5)
        
        # Garante um ATR mínimo realista (pelo menos 0.5% do preço) para evitar SL muito curto
        if atr <= 0 or (atr / current_price < 0.005):
            atr = current_price * 0.01  # Usa 1% do preço como volatilidade mínima
        
        # Calcula score de confiança baseado em confluência
        confidence = 0.0
        signals = []
        
        # Sinais técnicos
        if rsi >= 68:
            confidence += 0.25
            signals.append("RSI sobrecompra")
        elif rsi <= 32:
            confidence += 0.25
            signals.append("RSI sobrevenda")
            
        if "crossover" in macd_trend.lower():
            confidence += 0.35
            signals.append(f"MACD {macd_trend}")
        elif "bullish" in macd_trend.lower():
            confidence += 0.15
            signals.append(f"MACD {macd_trend}")
        elif "bearish" in macd_trend.lower():
            confidence -= 0.10
            
        # Sinais sociais
        if polarity > 0.65:
            confidence += 0.15
            signals.append("Sentimento muito positivo")
        elif polarity < 0.35:
            confidence += 0.15
            signals.append("Sentimento muito negativo")
        
        logger.info(f"Análise Determinística: Confiança={confidence:.2f}, Sinais={signals}, RSI={rsi:.2f}, MACD={macd_trend}, ATR={atr:.4f}, Polaridade={polarity:.2f}")
        
        # Decision LOGIC
        decision = "NEUTRAL"
        entry_price = current_price
        stop_loss = None
        take_profit = None
        
        # Limiar de confiança mais permissivo para testes (0.3 ao invés de 0.4)
        min_confidence = 0.3
        
        # LONG: RSI em sobrevenda OU MACD bullish + sentimento positivo
        if (rsi <= 32 or ("bullish" in macd_trend.lower() and polarity > 0.55)) and confidence >= min_confidence:
            decision = "LONG"
            entry_price = current_price
            stop_loss = current_price - (atr * 1.5)   # 1.5x ATR abaixo
            take_profit = current_price + (atr * 3.0)  # 3x ATR acima (risco/retorno ~1:2)
            
        # SHORT: RSI em sobrecompra OU MACD bearish + sentimento negativo
        elif (rsi >= 68 or ("bearish" in macd_trend.lower() and polarity < 0.45)) and confidence >= min_confidence:
            decision = "SHORT"
            entry_price = current_price
            stop_loss = current_price + (atr * 1.5)   # 1.5x ATR acima
            take_profit = current_price - (atr * 3.0)  # 3x ATR abaixo (risco/retorno ~1:2)
        
        result = {
            "decision": decision,
            "entry_price": entry_price if decision != "NEUTRAL" else None,
            "stop_loss": stop_loss if decision != "NEUTRAL" else None,
            "take_profit": take_profit if decision != "NEUTRAL" else None,
            "confidence_score": max(0, min(1.0, confidence)),  # Clamp entre 0 e 1
            "thesis": f"Análise Determinística: {', '.join(signals) if signals else 'Sem sinais claros'}"
        }
        
        logger.info(f"Decisão Final (Determinística): {result['decision']} @ {entry_price:.2f} (SL={stop_loss:.2f} TP={take_profit:.2f}, confiança={result['confidence_score']:.2f})")
        return result

