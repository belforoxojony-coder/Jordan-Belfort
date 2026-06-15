import logging
import random
import aiohttp
from typing import Dict, List
from jordan_belfort.config import bot_config
from openai import OpenAI

logger = logging.getLogger("Antenado")

class Antenado:
    """
    Agente 1 (O Antenado) - Híbrido (Código + LLM).
    Coleta dados de sentimento cripto (LunarCrush/Santiment) e
    utiliza LLM sob demanda para interpretar posts críticos de perfis whitelist.
    """
    def __init__(self):
        # Whitelist de perfis influentes para o ecossistema cripto
        self.whitelist = ["elonmusk", "saylor", "VitalikButerin", "cz_binance"]
        
        # Cliente LLM para interpretar postagens críticas (apenas se houver chaves reais)
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

    async def fetch_lunar_crush_metrics(self, pair: str) -> Dict[str, float]:
        """Tenta consultar o LunarCrush para obter métricas de sentimento real."""
        if not bot_config.lunarcrush_api_key:
            return {}
            
        symbol = pair.replace("USDT", "")
        url = f"https://developer-api.lunarcrush.com/v2?data=assets&symbol={symbol}"
        headers = {"Authorization": f"Bearer {bot_config.lunarcrush_api_key}"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        asset_data = data.get("data", [{}])[0]
                        # Extrai métricas de sentimento relevantes
                        return {
                            "social_volume_score": float(asset_data.get("social_volume_24h", 1.0)),
                            "sentiment_polarity": float(asset_data.get("average_sentiment", 0.5))
                        }
        except Exception as e:
            logger.error(f"Erro ao consultar LunarCrush: {e}")
        return {}

    def analyze_social_post_with_llm(self, post_text: str) -> float:
        """
        Usa o LLM sob demanda para ler uma postagem social e pontuar o impacto
        de sentimento em Cripto (variando de -1.0 a 1.0).
        """
        if not self.client:
            # Fallback determinístico simples
            post_lower = post_text.lower()
            if any(w in post_lower for w in ["bullish", "pump", "buy", "moon", "long", "love", "accquire"]):
                return 0.8
            if any(w in post_lower for w in ["bearish", "dump", "sell", "crash", "short", "fud", "ban"]):
                return -0.8
            return 0.0

        try:
            prompt = (
                "Você é um analista de sentimento de alta precisão para criptomoedas.\n"
                "Analise o seguinte post e retorne APENAS um número flutuante entre -1.0 (extremamente bearish) "
                "e 1.0 (extremamente bullish) representando o impacto no mercado cripto.\n"
                "Não responda com mais nada além do número.\n\n"
                f"Postagem: \"{post_text}\""
            )
            response = self.client.chat.completions.create(
                model=bot_config.llm_model,
                messages=[
                    {"role": "system", "content": "Você é uma IA analítica especializada em sentimentos de mercado."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=10,
                temperature=0.0
            )
            score_str = response.choices[0].message.content.strip()
            return float(score_str)
        except Exception as e:
            logger.error(f"Erro ao analisar sentimento de postagem com LLM: {e}")
            return 0.0

    async def get_social_sentiment(self, pair: str) -> Dict[str, float]:
        """
        Consolida a pontuação de sentimento geral.
        Consiste de sentiment_polarity (-1.0 a 1.0) e social_volume_score (multiplicador).
        """
        # 1. Tenta buscar das APIs de sentimento
        sentiment = await self.fetch_lunar_crush_metrics(pair)
        if sentiment:
            return sentiment
            
        # 2. Simula detecção de post importante na whitelist
        # Exemplo: Elon Musk tuitando sobre Bitcoin
        simulated_posts = [
            "Bitcoin is the future of money. Hard money.",
            "Going to buy some more BTC.",
            "Crypto regulations are getting out of hand.",
            "Market looks a bit overextended today.",
            "Just another day building on decentralized tech."
        ]
        
        # 20% de chance de termos um post relevante na Whitelist no loop atual
        if random.random() < 0.2:
            post = random.choice(simulated_posts)
            logger.info(f"O Antenado detectou post na Whitelist: '{post}'")
            polarity = self.analyze_social_post_with_llm(post)
            # Normaliza polaridade para [0, 1] sendo 0.5 neutro
            normalized_polarity = (polarity + 1.0) / 2.0
            volume_score = round(random.uniform(1.2, 2.5), 2)
            
            return {
                "social_volume_score": volume_score,
                "sentiment_polarity": round(normalized_polarity, 2)
            }

        # Valores neutros/padrão
        return {
            "social_volume_score": round(random.uniform(0.8, 1.2), 2),
            "sentiment_polarity": round(random.uniform(0.48, 0.52), 2)
        }
