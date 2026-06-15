import { useEffect, useState, useCallback } from 'react';
import { supabase, isSupabaseConfigured } from '../lib/supabase';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts';
import { Activity, DollarSign, TrendingUp, AlertCircle, Percent, RefreshCw, CheckCircle, XCircle } from 'lucide-react';
import { format } from 'date-fns';

// ── Custom Tooltip for chart ─────────────────────────────────────────────────
const CustomTooltip = ({ active, payload }) => {
  if (active && payload && payload.length) {
    const value = payload[0].value;
    return (
      <div className="bg-slate-900 border border-slate-700 rounded-lg p-3 shadow-xl">
        <p className={`text-sm font-bold ${value >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
          {value >= 0 ? '+' : ''}{value?.toFixed(4)} USDT
        </p>
      </div>
    );
  }
  return null;
};

// ── Stat Card ────────────────────────────────────────────────────────────────
const StatCard = ({ title, value, subtitle, icon: Icon, iconColor }) => (
  <div className="rounded-xl border border-slate-800 bg-slate-900 p-5 shadow-sm hover:border-slate-700 transition-colors">
    <div className="flex items-center justify-between mb-3">
      <p className="text-sm font-medium text-slate-400">{title}</p>
      <div className={`p-2 rounded-lg bg-slate-800`}>
        <Icon className={`h-4 w-4 ${iconColor}`} />
      </div>
    </div>
    <p className="text-2xl font-bold text-slate-100">{value}</p>
    <p className="text-xs text-slate-500 mt-1">{subtitle}</p>
  </div>
);

// ── Direction badge ──────────────────────────────────────────────────────────
const DirectionBadge = ({ direction }) => (
  <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
    direction === 'LONG'
      ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20'
      : 'bg-red-500/15 text-red-400 border border-red-500/20'
  }`}>
    {direction}
  </span>
);

// ── Status badge ─────────────────────────────────────────────────────────────
const StatusBadge = ({ pnl }) => {
  if (pnl == null) return <span className="text-slate-500 text-xs">—</span>;
  const win = pnl > 0;
  return (
    <span className={`flex items-center gap-1 text-xs font-semibold ${win ? 'text-emerald-400' : 'text-red-400'}`}>
      {win ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
      {win ? '+' : ''}{pnl.toFixed(4)}
    </span>
  );
};


// ── Mock Trades fallback when Supabase is not configured ────────────────────
const MOCK_TRADES = [
  {
    id: 6,
    pair: 'BTCUSDT',
    direction: 'LONG',
    entry_price: 65461.15,
    size: 0.068443,
    stop_loss: 64000.0,
    take_profit: 66922.59,
    status: 'open',
    binance_order_id: '4870002',
    entry_time: 1781477083629,
    exit_time: null,
    exit_price: null,
    pnl_gross: null,
    pnl_net: null,
  },
  {
    id: 5,
    pair: 'BTCUSDT',
    direction: 'LONG',
    entry_price: 65403.9,
    size: 0.033313,
    stop_loss: 62373.9,
    take_profit: 68433.9,
    status: 'closed',
    binance_order_id: 'mock_order_1781474092256',
    entry_time: 1781474092256,
    exit_time: 1781476046691,
    exit_price: 65142.0,
    pnl_gross: -8.7247,
    pnl_net: -10.8991,
  },
  {
    id: 4,
    pair: 'BTCUSDT',
    direction: 'LONG',
    entry_price: 60000.0,
    size: 0.1,
    stop_loss: 59000.0,
    take_profit: 62000.0,
    status: 'closed',
    binance_order_id: 'mock_test_123',
    entry_time: 1781466880121,
    exit_time: 1781466880144,
    exit_price: 61000.0,
    pnl_gross: 100.0,
    pnl_net: 93.95,
  },
  {
    id: 3,
    pair: 'BTCUSDT',
    direction: 'LONG',
    entry_price: 60000.0,
    size: 0.1,
    stop_loss: 59000.0,
    take_profit: 62000.0,
    status: 'closed',
    binance_order_id: 'mock_test_123',
    entry_time: 1781466582200,
    exit_time: 1781466582228,
    exit_price: 61000.0,
    pnl_gross: 100.0,
    pnl_net: 93.95,
  },
  {
    id: 2,
    pair: 'BTCUSDT',
    direction: 'LONG',
    entry_price: 60000.0,
    size: 0.1,
    stop_loss: 59000.0,
    take_profit: 62000.0,
    status: 'closed',
    binance_order_id: 'mock_test_123',
    entry_time: 1781466013595,
    exit_time: 1781466013622,
    exit_price: 61000.0,
    pnl_gross: 100.0,
    pnl_net: 93.95,
  },
  {
    id: 1,
    pair: 'BTCUSDT',
    direction: 'LONG',
    entry_price: 60000.0,
    size: 0.1,
    stop_loss: 59000.0,
    take_profit: 62000.0,
    status: 'closed',
    binance_order_id: 'mock_test_123',
    entry_time: 1781465297934,
    exit_time: 1781465297959,
    exit_price: 61000.0,
    pnl_gross: 100.0,
    pnl_net: 93.95,
  }
];

// ── Main Dashboard ───────────────────────────────────────────────────────────
export default function Dashboard() {
  const [activeTrades, setActiveTrades] = useState([]);
  const [closedTrades, setClosedTrades] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [notificationsTableExists, setNotificationsTableExists] = useState(null);
  const [metrics, setMetrics] = useState({ totalPnl: 0, winRate: 0, totalTrades: 0, bestTrade: 0, worstTrade: 0 });

  const processData = useCallback((trades) => {
    const active = trades.filter(t => t.status === 'open');
    const closed = trades.filter(t => t.status === 'closed');
    setActiveTrades(active);
    setClosedTrades(closed);

    if (closed.length > 0) {
      const wins = closed.filter(t => t.pnl_net > 0).length;
      const totalPnl = closed.reduce((a, c) => a + (c.pnl_net || 0), 0);
      const pnls = closed.map(t => t.pnl_net || 0);
      setMetrics({
        totalPnl,
        winRate: (wins / closed.length) * 100,
        totalTrades: closed.length,
        bestTrade: Math.max(...pnls),
        worstTrade: Math.min(...pnls),
      });
    } else {
      setMetrics({ totalPnl: 0, winRate: 0, totalTrades: 0, bestTrade: 0, worstTrade: 0 });
    }
    setLastUpdate(new Date());
  }, []);

  const fetchNotifications = useCallback(async () => {
    try {
      const { data, error } = await supabase
        .from('notifications')
        .select('*')
        .order('timestamp', { ascending: false })
        .limit(10);

      if (error) {
        throw error;
      }

      setNotificationsTableExists(true);
      return data || [];
    } catch (err) {
      const message = err?.message || String(err);
      if (message.includes("Could not find the table 'public.notifications'") || message.includes('PGRST205')) {
        setNotificationsTableExists(false);
        const { data, error: fallbackError } = await supabase
          .from('audit_logs')
          .select('id,timestamp,message,details')
          .eq('level', 'NOTIFICATION')
          .order('timestamp', { ascending: false })
          .limit(10);

        if (fallbackError) {
          throw fallbackError;
        }

        return (data || []).map((row) => ({
          id: row.id,
          timestamp: row.timestamp,
          message: row.message,
          channel: row.details?.channel || 'notification',
          metadata: row.details?.metadata || {}
        }));
      }
      throw err;
    }
  }, []);

  const fetchData = useCallback(async () => {
    if (!isSupabaseConfigured || !supabase) {
      processData(MOCK_TRADES);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const [{ data: trades, error: tradesError }, notificationsData] = await Promise.all([
        supabase.from('trades').select('*').order('entry_time', { ascending: false }),
        fetchNotifications()
      ]);

      if (tradesError) throw tradesError;
      if (trades) processData(trades);
      if (notificationsData) setNotifications(notificationsData);
    } catch (err) {
      console.error('Supabase fetch error:', err);
      if (err?.message?.includes('Could not find the table') || String(err).includes('PGRST205')) {
        setNotificationsTableExists(false);
      }
    } finally {
      setLoading(false);
    }
  }, [fetchNotifications, processData]);

  useEffect(() => {
    fetchData();
    if (!isSupabaseConfigured || !supabase) return;

    const tradesChannel = supabase
      .channel('trades-realtime')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'trades' }, fetchData)
      .subscribe();

    let notificationsChannel = null;
    if (notificationsTableExists !== null) {
      notificationsChannel = supabase
        .channel('notifications-realtime')
        .on(
          'postgres_changes',
          { event: '*', schema: 'public', table: notificationsTableExists === false ? 'audit_logs' : 'notifications' },
          fetchData
        )
        .subscribe();
    }

    return () => {
      supabase.removeChannel(tradesChannel);
      if (notificationsChannel) {
        supabase.removeChannel(notificationsChannel);
      }
    };
  }, [fetchData, notificationsTableExists]);

  const chartData = [...closedTrades].reverse().reduce((acc, t, i) => {
    const prev = i === 0 ? 0 : acc[i - 1].cumPnl;
    acc.push({
      label: `#${i + 1}`,
      pnl: t.pnl_net || 0,
      cumPnl: parseFloat((prev + (t.pnl_net || 0)).toFixed(4)),
    });
    return acc;
  }, []);

  return (
    <div className="space-y-6">

      {/* Connection warning */}
      {!isSupabaseConfigured && (
        <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-4 flex items-start gap-3">
          <AlertCircle className="text-amber-400 w-5 h-5 mt-0.5 flex-shrink-0" />
          <div>
            <h3 className="font-semibold text-amber-400">Modo de Demonstração (Supabase não configurado)</h3>
            <p className="text-sm text-amber-400/70 mt-0.5">
              Exibindo dados de exemplo baseados no histórico do SQLite local. Para ver os trades reais do seu bot na nuvem 24/7,
              adicione <code className="bg-amber-500/10 px-1 rounded">VITE_SUPABASE_URL</code> e{' '}
              <code className="bg-amber-500/10 px-1 rounded">VITE_SUPABASE_ANON_KEY</code> nas
              variáveis de ambiente da Vercel e faça um novo deploy.
            </p>
          </div>
        </div>
      )}

      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-100">Painel de Controle</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            {lastUpdate ? `Atualizado às ${format(lastUpdate, 'HH:mm:ss')}` : 'Aguardando dados...'}
          </p>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-sm text-slate-300 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Atualizar
        </button>
      </div>

      {/* Stat cards */}
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="PnL Total"
          value={`${metrics.totalPnl >= 0 ? '+' : ''}${metrics.totalPnl.toFixed(4)} USDT`}
          subtitle="Operações fechadas"
          icon={DollarSign}
          iconColor="text-emerald-400"
        />
        <StatCard
          title="Taxa de Acerto"
          value={`${metrics.winRate.toFixed(1)}%`}
          subtitle={`${metrics.totalTrades} trades no total`}
          icon={Percent}
          iconColor="text-cyan-400"
        />
        <StatCard
          title="Posições Abertas"
          value={activeTrades.length}
          subtitle="Operações em andamento"
          icon={Activity}
          iconColor="text-amber-400"
        />
        <StatCard
          title="Melhor Trade"
          value={`+${metrics.bestTrade.toFixed(4)}`}
          subtitle={`Pior: ${metrics.worstTrade.toFixed(4)}`}
          icon={TrendingUp}
          iconColor="text-violet-400"
        />
      </div>

      {/* Cumulative PnL Chart */}
      <div className="rounded-xl border border-slate-800 bg-slate-900 p-5 shadow-sm">
        <div className="flex items-center gap-2 mb-5">
          <TrendingUp className="h-5 w-5 text-emerald-400" />
          <h2 className="text-base font-semibold text-slate-100">PnL Acumulado</h2>
          <span className="ml-auto text-xs text-slate-500">{closedTrades.length} trades</span>
        </div>
        {closedTrades.length === 0 ? (
          <div className="flex items-center justify-center h-52 text-slate-600 text-sm">
            Nenhum trade fechado ainda
          </div>
        ) : (
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                <XAxis dataKey="label" stroke="#475569" tick={{ fill: '#64748b', fontSize: 11 }} tickLine={false} />
                <YAxis stroke="#475569" tick={{ fill: '#64748b', fontSize: 11 }} tickLine={false} axisLine={false} />
                <ReferenceLine y={0} stroke="#334155" strokeDasharray="4 4" />
                <Tooltip content={<CustomTooltip />} />
                <Line
                  type="monotone"
                  dataKey="cumPnl"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 5, fill: '#10b981', stroke: '#064e3b', strokeWidth: 2 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Notification Events */}
      <div className="rounded-xl border border-slate-800 bg-slate-900 shadow-sm overflow-hidden">
        <div className="flex items-center gap-2 p-5 border-b border-slate-800">
          <AlertCircle className="w-5 h-5 text-slate-400" />
          <h2 className="text-base font-semibold text-slate-100">Notificações Recentes</h2>
          <span className="ml-auto text-xs text-slate-500">Últimas {notifications.length} mensagens</span>
        </div>
        <div className="p-5 space-y-3">
          {notifications.length === 0 ? (
            <div className="text-slate-500 text-sm">Nenhuma notificação disponível no momento.</div>
          ) : notifications.map((note) => (
            <div key={note.id} className="rounded-2xl border border-slate-800 bg-slate-950/80 p-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs uppercase tracking-[0.2em] text-slate-500">{note.channel}</span>
                <span className="text-xs text-slate-500">{note.timestamp ? format(new Date(note.timestamp), 'dd/MM HH:mm') : '—'}</span>
              </div>
              <p className="text-sm text-slate-200 whitespace-pre-wrap">{note.message}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Active Trades Table */}
      <div className="rounded-xl border border-slate-800 bg-slate-900 shadow-sm overflow-hidden">
        <div className="flex items-center gap-2 p-5 border-b border-slate-800">
          <Activity className="w-5 h-5 text-amber-400" />
          <h2 className="text-base font-semibold text-slate-100">Posições Abertas</h2>
          <span className="ml-auto text-xs text-slate-500">{activeTrades.length} posição(ões)</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-800">
                <th className="px-5 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Par</th>
                <th className="px-5 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Direção</th>
                <th className="px-5 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Entrada</th>
                <th className="px-5 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Tamanho</th>
                <th className="px-5 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">SL / TP</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {activeTrades.length === 0 ? (
                <tr>
                  <td colSpan="5" className="px-5 py-10 text-center text-slate-600 text-sm">
                    Nenhuma operação aberta no momento
                  </td>
                </tr>
              ) : activeTrades.map((t) => (
                <tr key={t.id} className="hover:bg-slate-800/40 transition-colors">
                  <td className="px-5 py-3 font-semibold text-slate-100">{t.pair}</td>
                  <td className="px-5 py-3"><DirectionBadge direction={t.direction} /></td>
                  <td className="px-5 py-3 text-slate-300">${t.entry_price}</td>
                  <td className="px-5 py-3 text-slate-300">{t.size}</td>
                  <td className="px-5 py-3">
                    <span className="text-red-400">${t.stop_loss}</span>
                    <span className="text-slate-600 mx-1">/</span>
                    <span className="text-emerald-400">${t.take_profit}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Closed Trades History */}
      <div className="rounded-xl border border-slate-800 bg-slate-900 shadow-sm overflow-hidden">
        <div className="flex items-center gap-2 p-5 border-b border-slate-800">
          <CheckCircle className="w-5 h-5 text-slate-400" />
          <h2 className="text-base font-semibold text-slate-100">Histórico de Trades</h2>
          <span className="ml-auto text-xs text-slate-500">{closedTrades.length} fechado(s)</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-800">
                <th className="px-5 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Par</th>
                <th className="px-5 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Direção</th>
                <th className="px-5 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Entrada</th>
                <th className="px-5 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Saída</th>
                <th className="px-5 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">PnL</th>
                <th className="px-5 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Data</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {closedTrades.length === 0 ? (
                <tr>
                  <td colSpan="6" className="px-5 py-10 text-center text-slate-600 text-sm">
                    Nenhum trade fechado ainda
                  </td>
                </tr>
              ) : closedTrades.map((t) => (
                <tr key={t.id} className="hover:bg-slate-800/40 transition-colors">
                  <td className="px-5 py-3 font-semibold text-slate-100">{t.pair}</td>
                  <td className="px-5 py-3"><DirectionBadge direction={t.direction} /></td>
                  <td className="px-5 py-3 text-slate-300">${t.entry_price}</td>
                  <td className="px-5 py-3 text-slate-300">{t.exit_price ? `$${t.exit_price}` : '—'}</td>
                  <td className="px-5 py-3"><StatusBadge pnl={t.pnl_net} /></td>
                  <td className="px-5 py-3 text-slate-500 text-xs">
                    {t.entry_time ? format(new Date(t.entry_time), 'dd/MM HH:mm') : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
}
