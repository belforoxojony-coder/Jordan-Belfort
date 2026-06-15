import logging
import asyncio
from typing import Optional
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
from jordan_belfort.config import bot_config
from jordan_belfort.database import Database

logger = logging.getLogger("JordanBelfortInterface")

class JordanBelfort:
    """
    Agente 9 (Jordan Belfort) - Híbrido.
    Interface humana via Telegram.
    Controla o Kill Switch (/pausar, /resumir) e formata relatórios
    com a persona do "Lobo de Wall Street" via LLM.
    """
    def __init__(self, executor_agent=None):
        self.db = Database()
        self.executor = executor_agent
        self.app: Optional[Application] = None
        self.chat_id = bot_config.telegram_chat_id
        
        # Cliente LLM para a Persona do Lobo
        has_openai = bot_config.openai_api_key and bot_config.openai_api_key != "your_openai_api_key_here"
        has_groq = bot_config.groq_api_key and bot_config.groq_api_key != "your_groq_api_key_here"
        
        if bot_config.llm_provider == "openai" and has_openai:
            self.llm_client = OpenAI(api_key=bot_config.openai_api_key)
        elif bot_config.llm_provider == "groq" and has_groq:
            self.llm_client = OpenAI(
                api_key=bot_config.groq_api_key,
                base_url="https://api.groq.com/openai/v1"
            )
        else:
            self.llm_client = None

    def format_with_wolf_persona(self, message: str) -> str:
        """
        Interpreta a mensagem e a reescreve na persona do Lobo de Wall Street (Jordan Belfort).
        """
        if not self.llm_client:
            # Fallback determinístico enérgico
            return f"🔥 ESCUTA AQUI, CAMPEÃO! 🔥\n\n{message}\n\nA gente vai dominar essa banca! Rumo ao topo! 🚀📈"

        try:
            prompt = (
                "Você é Jordan Belfort, o próprio Lobo de Wall Street.\n"
                "Sua personalidade é extremamente enérgica, persuasiva, focada em lucros gigantescos, "
                "usando jargões do mercado financeiro, emojis de dinheiro/foguetes e chamando o leitor de 'campeão' ou 'parceiro'.\n"
                "Reescreva a seguinte notificação técnica de trading para deixá-la incrivelmente emocionante, "
                "agressiva e motivadora. Mantenha os valores numéricos, preços de stop loss, take profit e o par do ativo exatamente iguais.\n\n"
                f"Mensagem original: {message}"
            )
            response = self.llm_client.chat.completions.create(
                model=bot_config.llm_model,
                messages=[
                    {"role": "system", "content": "Você é Jordan Belfort. Responda em português com muita energia e jargões."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=350,
                temperature=0.8
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Erro ao formatar mensagem na persona de Jordan: {e}")
            return f"🔥 ESCUTA AQUI, CAMPEÃO! 🔥\n\n{message}\n\nRumo ao topo! 🚀📈"

    async def send_notification(self, text: str, format_wolf: bool = True):
        """Envia uma mensagem para o chat do Telegram configurado."""
        formatted_text = self.format_with_wolf_persona(text) if format_wolf else text
        
        # Loga no terminal
        try:
            print(f"\n[NOTIFICAÇÃO TELEGRAM]\n{formatted_text}\n")
        except UnicodeEncodeError:
            try:
                safe_text = formatted_text.encode('ascii', errors='replace').decode('ascii')
                print(f"\n[NOTIFICAÇÃO TELEGRAM (SAFE PRINT)]\n{safe_text}\n")
            except:
                pass
        
        if not self.app or not self.chat_id:
            logger.debug("Envio de notificação pulado (Telegram desativado).")
            return
            
        try:
            # Envia via HTTP
            await self.app.bot.send_message(chat_id=self.chat_id, text=formatted_text)
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem no Telegram: {e}")

    # --- Comandos do Telegram ---
    def _is_authorized(self, update: Update) -> bool:
        """Verifica se a mensagem provém do Chat ID do proprietário."""
        if not self.chat_id:
            return True
        authorized = str(update.effective_chat.id) == str(self.chat_id)
        if not authorized:
            logger.warning(f"Mensagem não autorizada recebida. Remetente Chat ID: {update.effective_chat.id} (username: @{update.effective_user.username if update.effective_user else ''})")
        return authorized

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            await update.message.reply_text("Acesso não autorizado.")
            return
            
        msg = (
            "Seja bem-vindo ao Jordan Belfort Multiagent System! 🐺💰\n"
            "Eu sou o Lobo de Wall Street e estou operando na Binance 24/7.\n"
            "Pode me mandar qualquer mensagem e eu respondo!\n\n"
            "Comandos Disponíveis:\n"
            "/status - Verifica o status do bot\n"
            "/pausar - Ativa o Kill Switch global\n"
            "/resumir - Retoma as operações de trading\n"
            "/posicoes - Lista posições ativas\n"
            "/saldo - Consulta saldo disponível\n"
            "/relatorio - Resumo completo de performance\n"
            "/ajuda - Mostra esta mensagem\n\n"
            "❓ Ou simplesmente me mande uma mensagem e o Lobo te responde!"
        )
        await update.message.reply_text(msg)

    async def cmd_pausar(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return
            
        bot_config.status = "paused"
        logger.info("Kill Switch ativado via Telegram.")
        await update.message.reply_text(
            self.format_with_wolf_persona(
                "BOT PAUSADO! Kill Switch ativado! Nenhuma nova posição será aberta até segunda ordem. "
                "Segurança e controle de capital em primeiro lugar!"
            )
        )

    async def cmd_resumir(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return
            
        bot_config.status = "active"
        logger.info("Sistema retomado via Telegram.")
        await update.message.reply_text(
            self.format_with_wolf_persona(
                "SISTEMA ATIVADO! Soltem os cães! Voltamos ao jogo e vamos pegar o mercado pelo pescoço!"
            )
        )

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return
            
        status = "OPERANDO A TODO VAPOR (Ativo)" if bot_config.status == "active" else "PAUSADO (Inativo)"
        trades = self.db.get_active_trades()
        trades_desc = ""
        if trades:
            for t in trades:
                trades_desc += f"- #{t['id']} {t['pair']} {t['direction']} {t['size']} @ {t['entry_price']}\n"
        else:
            trades_desc = "Nenhuma posição aberta no momento.\n"
            
        msg = (
            f"--- Jordan Belfort Status ---\n"
            f"Status Global: {status}\n"
            f"Parâmetros: Risco={bot_config.risk_percentage}%, Exposição={bot_config.max_exposure_percentage}%\n"
            f"Alavancagem: {bot_config.leverage}x\n"
            f"Posições Ativas:\n{trades_desc}"
        )
        await update.message.reply_text(msg)

    async def cmd_posicoes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return
        await self.cmd_status(update, context)

    async def cmd_saldo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return
            
        if self.executor:
            balance = self.executor.get_balance()
            paper_tag = " [Simulado/Paper]" if self.executor.paper_trading else " [Real/Binance]"
            msg = f"Saldo Atual da Conta{paper_tag}: {balance:.2f} USDT"
        else:
            msg = "Agente Executor indisponível para consulta de saldo."
            
        await update.message.reply_text(self.format_with_wolf_persona(msg))

    async def cmd_relatorio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Envia um relatório resumido de performance do bot."""
        if not self._is_authorized(update):
            return

        trades_all = []
        try:
            # Pega todos os trades fechados para calcular métricas
            if not self.db.use_sqlite and self.db.client:
                res = self.db.client.table("trades").select("*").eq("status", "closed").execute()
                trades_all = res.data or []
            else:
                import sqlite3
                conn = sqlite3.connect(self.db.sqlite_path)
                conn.row_factory = sqlite3.Row
                trades_all = [dict(r) for r in conn.execute("SELECT * FROM trades WHERE status='closed'").fetchall()]
                conn.close()
        except Exception as e:
            logger.error(f"Erro ao buscar trades para relatório: {e}")

        active = self.db.get_active_trades()

        total = len(trades_all)
        if total > 0:
            pnl_total = sum(t.get("pnl_net") or 0 for t in trades_all)
            wins = sum(1 for t in trades_all if (t.get("pnl_net") or 0) > 0)
            win_rate = (wins / total) * 100
            best = max((t.get("pnl_net") or 0) for t in trades_all)
            worst = min((t.get("pnl_net") or 0) for t in trades_all)
            stats = (
                f"Trades Fechados: {total}\n"
                f"Vitórias: {wins} ({win_rate:.1f}% win rate)\n"
                f"PnL Líquido Total: {pnl_total:+.4f} USDT\n"
                f"Melhor Trade: +{best:.4f} USDT\n"
                f"Pior Trade: {worst:.4f} USDT\n"
                f"Posições Abertas: {len(active)}"
            )
        else:
            stats = f"Nenhum trade fechado ainda.\nPosições Abertas: {len(active)}"

        await update.message.reply_text(
            self.format_with_wolf_persona(f"Relatório de Performance Jordan Belfort:\n{stats}")
        )

    async def cmd_ajuda(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Alias para /start mostrando todos os comandos."""
        await self.cmd_start(update, context)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Responde a qualquer mensagem de texto livre enviada pelo usuário
        usando a persona do Jordan Belfort (LLM) ou um fallback determinístico.
        """
        if not self._is_authorized(update):
            return

        user_text = update.message.text or ""
        if not user_text.strip():
            return

        logger.info(f"Mensagem livre recebida do Telegram: '{user_text}'")

        # Responde com a persona do Lobo via LLM
        if self.llm_client:
            try:
                prompt = (
                    "Você é Jordan Belfort, o Lobo de Wall Street, gerenciando um bot de trading de criptomoedas.\n"
                    "Responda à seguinte mensagem do seu sócio/usuário de forma energética, motivadora e com jargões do mercado financeiro.\n"
                    "Se for uma pergunta sobre mercado, trading, or criptos, dê uma resposta didática mas com a energia do Lobo.\n"
                    "Se for um pedido de status, oriente o usuário a usar os comandos /status, /posicoes ou /relatorio.\n"
                    "Seja conciso (máximo 3 parágrafos). Responda em português.\n\n"
                    f"Mensagem do usuário: {user_text}"
                )
                response = self.llm_client.chat.completions.create(
                    model=bot_config.llm_model,
                    messages=[
                        {"role": "system", "content": "Você é Jordan Belfort, o Lobo de Wall Street. Responda em português."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=400,
                    temperature=0.85
                )
                reply = response.choices[0].message.content.strip()
            except Exception as e:
                logger.error(f"Erro ao chamar LLM para resposta de mensagem livre: {e}")
                reply = f"🔥 Ei, parceiro! {user_text}? Isso é a pergunta certa! O mercado não espera - o Lobo está de olho em tudo! 🚀💰"
        else:
            reply = f"🔥 ESCUTA, CAMPÃO! 🔥\n\nVocê perguntou: '{user_text}'\n\nO Lobo está analisando o mercado 24/7! Use /status para ver as operações ativas ou /relatorio para ver a performance! Vamos dominar esse mercado! 🚀📈"

        await update.message.reply_text(reply)

    async def start_bot(self):
        """Inicializa o bot de Telegram assincronamente."""
        if not bot_config.telegram_bot_token or bot_config.telegram_bot_token == "your_telegram_bot_token_here":
            logger.warning("Token do Telegram ausente ou padrão. Bot de chat desativado. Notificações apenas no console.")
            return

        try:
            logger.info("Inicializando Bot de Telegram...")
            # Cria aplicação
            self.app = Application.builder().token(bot_config.telegram_bot_token).build()
            
            # Adiciona handlers
            self.app.add_handler(CommandHandler("start", self.cmd_start))
            self.app.add_handler(CommandHandler("pausar", self.cmd_pausar))
            self.app.add_handler(CommandHandler("resumir", self.cmd_resumir))
            self.app.add_handler(CommandHandler("status", self.cmd_status))
            self.app.add_handler(CommandHandler("posicoes", self.cmd_posicoes))
            self.app.add_handler(CommandHandler("saldo", self.cmd_saldo))
            self.app.add_handler(CommandHandler("relatorio", self.cmd_relatorio))
            self.app.add_handler(CommandHandler("ajuda", self.cmd_ajuda))
            # Responde qualquer mensagem de texto livre
            self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
            
            # Inicializa a aplicação
            await self.app.initialize()
            await self.app.start()
            
            # Executa o polling assincronamente em background
            # Usando custom update fetcher para não travar a thread principal
            asyncio.create_task(self._run_polling())
            logger.info("Bot de Telegram operando em background.")
            
            await self.send_notification("Sistema Jordan Belfort inicializado! O Lobo está na área!", format_wolf=True)
        except Exception as e:
            logger.error(f"Erro ao inicializar Telegram Bot: {e}. Desativando interface Telegram.")
            self.app = None

    async def _run_polling(self):
        """Roda o loop de polling de mensagens sem bloquear o executor."""
        offset = 0
        while self.app and self.app.running:
            try:
                updates = await self.app.bot.get_updates(offset=offset, timeout=10)
                for update in updates:
                    await self.app.process_update(update)
                    offset = update.update_id + 1
            except Exception as e:
                logger.error(f"Erro no polling do Telegram: {e}")
                await asyncio.sleep(5)

    async def stop(self):
        """Para o bot do Telegram de forma limpa."""
        if self.app:
            logger.info("Parando Bot do Telegram...")
            try:
                await self.app.stop()
                await self.app.shutdown()
            except Exception as e:
                logger.error(f"Erro ao parar o Telegram: {e}")
