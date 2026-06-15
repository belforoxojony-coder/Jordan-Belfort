-- Esquema de Banco de Dados para o Jordan Belfort Trading Bot
-- Compatível com Supabase (PostgreSQL)

-- 1. Tabela de Configurações Globais
CREATE TABLE IF NOT EXISTS config (
    key VARCHAR(255) PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Inserir valores padrões de configuração se não existirem
INSERT INTO config (key, value) VALUES
('status', '"paused"') -- active ou paused
ON CONFLICT (key) DO NOTHING;

INSERT INTO config (key, value) VALUES
('risk_percentage', '1.0') -- percentual de risco por operação (ex: 1.0%)
ON CONFLICT (key) DO NOTHING;

INSERT INTO config (key, value) VALUES
('max_exposure_percentage', '5.0') -- percentual máximo de exposição global da banca
ON CONFLICT (key) DO NOTHING;

INSERT INTO config (key, value) VALUES
('leverage', '1') -- alavancagem padrão (ex: 1x, 2x, 5x, etc.)
ON CONFLICT (key) DO NOTHING;

-- 2. Tabela de Sinais Brutos dos Agentes de Entrada
CREATE TABLE IF NOT EXISTS signals (
    id SERIAL PRIMARY KEY,
    timestamp BIGINT NOT NULL,
    pair VARCHAR(50) NOT NULL,
    technical_indicators JSONB NOT NULL,
    market_structure JSONB NOT NULL,
    social_sentiment JSONB NOT NULL,
    on_chain_flow JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Tabela de Decisões do Estrategista-Chefe (LLM)
CREATE TABLE IF NOT EXISTS decisions (
    id SERIAL PRIMARY KEY,
    timestamp BIGINT NOT NULL,
    pair VARCHAR(50) NOT NULL,
    signal_id INTEGER REFERENCES signals(id),
    decision VARCHAR(20) NOT NULL, -- LONG, SHORT, NEUTRAL
    entry_price NUMERIC,
    stop_loss NUMERIC,
    take_profit NUMERIC,
    confidence NUMERIC,
    thesis TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Tabela de Trades/Posições
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    pair VARCHAR(50) NOT NULL,
    direction VARCHAR(10) NOT NULL, -- LONG, SHORT
    entry_price NUMERIC NOT NULL,
    size NUMERIC NOT NULL,
    stop_loss NUMERIC NOT NULL,
    take_profit NUMERIC NOT NULL,
    status VARCHAR(20) NOT NULL, -- open, closed, cancelled
    binance_order_id VARCHAR(255),
    entry_time BIGINT NOT NULL,
    exit_time BIGINT,
    exit_price NUMERIC,
    pnl_gross NUMERIC,
    pnl_net NUMERIC,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. Tabela de Auditoria e Histórico de Saldo (Audit Logs)
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    timestamp BIGINT NOT NULL,
    level VARCHAR(20) NOT NULL, -- INFO, WARNING, ERROR, TRADE
    message TEXT NOT NULL,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para otimização de consultas
CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals(timestamp);
CREATE INDEX IF NOT EXISTS idx_decisions_timestamp ON decisions(timestamp);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_pair ON trades(pair);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);
