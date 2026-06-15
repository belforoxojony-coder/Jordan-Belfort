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
        """
        if not self.client:
            return self._get_fallback_decision("LLM não configurado no arquivo .env")

        pair = payload.get("pair", "BTCUSDT")
        current_price = payload.get("current_price", 0.0)

        # Monta prompt estruturado
        system_instruction = (
            "Você é o Estrategista-Chefe de um fundo quantitativo de alta performance operando cripto.\n"
            "Sua tarefa é analisar o payload JSON de entrada que consolida dados técnicos, livro de ofertas, "
            "fluxo on-chain e sentimento social para deliberar a direção do trade.\n"
            "Você deve responder OBRIGATORIAMENTE com um objeto JSON estruturado contendo a decisão de viabilidade.\n"
            "REGRAS CRÍTICAS:\n"
            "1. Os únicos valores permitidos para 'decision' são 'LONG', 'SHORT' ou 'NEUTRAL'.\n"
            "2. Se decision for LONG ou SHORT, você deve definir 'entry_price', 'stop_loss' e 'take_profit' baseados nos dados fornecidos.\n"
            "3. O Stop Loss deve ser coerente com a volatilidade (ATR) e direção:\n"
            "   - Para LONG: stop_loss < entry_price\n"
            "   - Para SHORT: stop_loss > entry_price\n"
            "4. O Take Profit deve respeitar uma relação risco-retorno mínima de 1.5x (ex: se arriscar R$ 100, deve buscar ganhar R$ 150).\n"
            "5. Se os dados forem conflitantes ou indefinidos, defina decision como 'NEUTRAL'.\n"
            "6. Retorne APENAS o JSON válido. Não adicione markdown, blocos de código (ex: ```json) ou qualquer outro texto explicativo fora do JSON.\n"
        )

        user_prompt = (
            f"Preço de Mercado Atual: {current_price}\n"
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
            # Invoca o LLM
            response = self.client.chat.completions.create(
                model=bot_config.llm_model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}, # Força formato JSON nativamente se suportado
                temperature=0.2, # Baixa temperatura para decisões mais consistentes
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
            return self._get_fallback_decision("Falha ao ler o formato JSON da resposta da IA")
        except Exception as e:
            logger.error(f"Erro geral durante deliberação do Estrategista-Chefe: {e}")
            return self._get_fallback_decision(f"Erro interno de processamento do LLM: {e}")
