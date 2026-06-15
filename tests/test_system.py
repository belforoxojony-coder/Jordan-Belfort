import pytest
import pandas as pd
import numpy as np
import time
from jordan_belfort.database import Database
from jordan_belfort.agents.grafista import Grafista
from jordan_belfort.agents.gerente_risco import GerenteRisco
from jordan_belfort.agents.estrategista import EstrategistaChefe
from jordan_belfort.agents.executor import Executor
from jordan_belfort.agents.auditor import Auditor

@pytest.fixture
def mock_candles_df():
    """Gera um DataFrame de teste contendo dados simulados de candles."""
    np.random.seed(42)
    dates = pd.date_range(end=pd.Timestamp.now(), periods=100, freq='15min')
    
    # Simula um passeio aleatório para gerar preços coerentes
    close_prices = 60000.0 + np.cumsum(np.random.normal(0, 150, 100))
    high_prices = close_prices + np.random.uniform(50, 200, 100)
    low_prices = close_prices - np.random.uniform(50, 200, 100)
    open_prices = close_prices + np.random.normal(0, 50, 100)
    volumes = np.random.uniform(1, 10, 100)
    
    df = pd.DataFrame({
        "timestamp": dates,
        "open": open_prices,
        "high": high_prices,
        "low": low_prices,
        "close": close_prices,
        "volume": volumes
    })
    return df

def test_database_sqlite_fallback():
    """Valida se o SQLite local funciona corretamente para configs e logs."""
    db = Database()
    # Força uso de SQLite para teste isolado
    db.use_sqlite = True
    db._init_sqlite()
    
    # Teste de config
    db.set_config("test_key", "test_value")
    val = db.get_config("test_key")
    assert val == "test_value"
    
    # Teste de logs de auditoria
    success = db.log_audit("INFO", "Log de teste unitário")
    assert success is True

def test_grafista_indicators(mock_candles_df):
    """Valida se as contas matemáticas de RSI, MACD e ATR estão corretas no Grafista."""
    graf = Grafista(pairs=["BTCUSDT"])
    
    # Força injeção do DataFrame mockado
    graf.candles_history["BTCUSDT"] = mock_candles_df
    
    rsi = graf.calculate_rsi(mock_candles_df)
    assert 0 <= rsi <= 100
    
    macd_res = graf.calculate_macd(mock_candles_df)
    assert "macd" in macd_res
    assert "signal" in macd_res
    assert "trend" in macd_res
    
    atr = graf.calculate_atr(mock_candles_df)
    assert atr > 0

def test_gerente_risco_veto_and_calculation():
    """Valida o cálculo do tamanho da posição e as regras de veto/compliance do Gerente de Risco."""
    from jordan_belfort.config import bot_config
    bot_config.status = "active"
    bot_config.max_exposure_percentage = 100.0
    
    gr = GerenteRisco()
    
    # Cenário 1: Tudo Aprovado (LONG em BTCUSDT)
    decision = {
        "pair": "BTCUSDT",
        "decision": "LONG",
        "entry_price": 60000.0,
        "stop_loss": 59000.0, # 1.66% stop loss
        "take_profit": 62000.0,
        "thesis": "Suporte testado"
    }
    
    # Banca = $10.000, Risco = 1% ($100 arriscado)
    # SL = 1.6667% (0.016667)
    # Position size = 100 / 0.016667 = $6.000 USD
    is_approved, reason, risk_payload = gr.validate_and_calculate(decision, 10000.0)
    assert is_approved is True, f"Veto reason: {reason}"
    assert risk_payload["position_size_usd"] == 6000.0
    assert risk_payload["quantity"] > 0
    
    # Cenário 2: VETO - Stop Loss acima da entrada em LONG
    decision_invalid_sl = decision.copy()
    decision_invalid_sl["stop_loss"] = 61000.0
    is_approved, reason, _ = gr.validate_and_calculate(decision_invalid_sl, 10000.0)
    assert is_approved is False
    assert "VETO" in reason

    # Cenário 3: VETO - Exposição violada (banca muito pequena ou risco excessivo)
    # Risco de 1% em banca de $10.000 com Stop Loss de 0.2% (muito apertado)
    # Position size = 100 / 0.002 = $50.000 USD (excede 5% da banca = $500 max)
    decision_tight_sl = decision.copy()
    decision_tight_sl["stop_loss"] = 59880.0 # 0.2% de SL
    is_approved, reason, _ = gr.validate_and_calculate(decision_tight_sl, 10000.0)
    assert is_approved is False
    assert "viola a exposição máxima" in reason

def test_auditor_accounting():
    """Valida a precisão da auditoria pós-trade e o reajuste de banca."""
    db = Database()
    db.use_sqlite = True
    db._init_sqlite()
    aud = Auditor()
    
    # Registra trade inicial
    trade_id = db.create_trade(
        pair="BTCUSDT",
        direction="LONG",
        entry_price=60000.0,
        size=0.1, # total = $6000 USD
        stop_loss=59000.0,
        take_profit=62000.0,
        binance_order_id="mock_test_123",
        entry_time=int(time.time() * 1000)
    )
    
    db.set_config("paper_balance", 10000.0)
    
    # Fecha trade com lucro (Exit Price = 61000.0)
    # PnL Bruto = (61000 - 60000) * 0.1 = $100 USD
    # Taxas = (60000 * 0.1 * 0.0005) + (61000 * 0.1 * 0.0005) = 3.0 + 3.05 = $6.05
    # PnL Líquido = 100 - 6.05 = $93.95 USD
    audit_res = aud.audit_trade_close(
        trade_id=trade_id,
        exit_price=61000.0,
        exit_time=int(time.time() * 1000),
        paper_trading=True
    )
    
    assert audit_res is not None
    assert abs(audit_res["pnl_gross"] - 100.0) < 1e-4
    assert abs(audit_res["fees"] - 6.05) < 1e-4
    assert abs(audit_res["pnl_net"] - 93.95) < 1e-4
    
    # Saldo final da banca deve ser 10000 + 93.95 = 10093.95
    new_balance = float(db.get_config("paper_balance"))
    assert abs(new_balance - 10093.95) < 1e-4
