import { useState, useEffect } from 'react';
import Head from 'next/head';

// ─── Color palette ───────────────────────────────────────────────────────────
const COLORS = {
  bg: '#0f1117',
  surface: '#1a1d27',
  surfaceHover: '#222538',
  border: '#2a2d3e',
  primary: '#3b82f6',
  primaryDark: '#2563eb',
  danger: '#ef4444',
  warning: '#f59e0b',
  success: '#10b981',
  info: '#8b5cf6',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  textMuted: '#64748b',
  critical: '#ef4444',
  high: '#f59e0b',
  medium: '#3b82f6',
  low: '#10b981',
};

const RISK_COLORS = { CRITICAL: COLORS.critical, HIGH: COLORS.high, MEDIUM: COLORS.medium, LOW: COLORS.low };
const STATUS_COLORS = { OPEN: COLORS.danger, UNDER_REVIEW: COLORS.warning, ESCALATED: COLORS.info, CLOSED: COLORS.textMuted };
const ALERT_TYPE_COLORS = { STRUCTURING: '#f59e0b', LAYERING: '#ef4444', RAPID_MOVEMENT: '#8b5cf6', HIGH_VALUE: '#3b82f6', ROUND_TRIP: '#10b981', OTHER: '#64748b' };

// ─── Sub-components ──────────────────────────────────────────────────────────

function Badge({ label, color }) {
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 8px',
      borderRadius: 4,
      fontSize: 11,
      fontWeight: 700,
      backgroundColor: color + '22',
      color: color,
      border: `1px solid ${color}44`,
      textTransform: 'uppercase',
      letterSpacing: '0.05em',
    }}>
      {label}
    </span>
  );
}

function StatCard({ title, value, subtitle, color, icon }) {
  return (
    <div style={{
      background: COLORS.surface,
      border: `1px solid ${COLORS.border}`,
      borderRadius: 12,
      padding: '20px 24px',
      flex: 1,
      minWidth: 160,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <p style={{ margin: 0, color: COLORS.textSecondary, fontSize: 12, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.08em' }}>{title}</p>
          <p style={{ margin: '8px 0 4px', color: color || COLORS.textPrimary, fontSize: 28, fontWeight: 700 }}>{value}</p>
          {subtitle && <p style={{ margin: 0, color: COLORS.textMuted, fontSize: 12 }}>{subtitle}</p>}
        </div>
        {icon && <span style={{ fontSize: 28, opacity: 0.7 }}>{icon}</span>}
      </div>
    </div>
  );
}

function BarChart({ data, maxValue, colorFn }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, height: 80 }}>
      {data.map((item, i) => {
        const height = Math.max(4, (item.count / maxValue) * 80);
        return (
          <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
            <span style={{ color: COLORS.textMuted, fontSize: 10 }}>{item.count}</span>
            <div style={{
              width: '100%',
              height,
              background: colorFn ? colorFn(i) : COLORS.primary,
              borderRadius: '3px 3px 0 0',
              transition: 'height 0.3s',
            }} />
            <span style={{ color: COLORS.textMuted, fontSize: 9, textAlign: 'center' }}>{item.label}</span>
          </div>
        );
      })}
    </div>
  );
}

function DonutSegment({ value, total, color, label }) {
  const pct = total > 0 ? (value / total) * 100 : 0;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
      <div style={{ width: 10, height: 10, borderRadius: 2, backgroundColor: color, flexShrink: 0 }} />
      <span style={{ color: COLORS.textSecondary, fontSize: 13, flex: 1 }}>{label}</span>
      <span style={{ color: COLORS.textPrimary, fontSize: 13, fontWeight: 600 }}>{value}</span>
      <span style={{ color: COLORS.textMuted, fontSize: 12, width: 36, textAlign: 'right' }}>{pct.toFixed(0)}%</span>
    </div>
  );
}

function NetworkViz({ nodes, edges }) {
  if (!nodes || nodes.length === 0) return null;
  const W = 500, H = 280;
  const xs = nodes.map(n => n.x);
  const ys = nodes.map(n => n.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const scaleX = (x) => 20 + ((x - minX) / (maxX - minX + 1)) * (W - 40);
  const scaleY = (y) => 20 + ((y - minY) / (maxY - minY + 1)) * (H - 40);
  const nodeMap = {};
  nodes.forEach(n => { nodeMap[n.id] = n; });

  return (
    <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} style={{ background: 'transparent' }}>
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M 0 0 L 10 5 L 0 10 z" fill={COLORS.border} />
        </marker>
      </defs>
      {edges.map((e, i) => {
        const s = nodeMap[e.source], t = nodeMap[e.target];
        if (!s || !t) return null;
        const x1 = scaleX(s.x), y1 = scaleY(s.y), x2 = scaleX(t.x), y2 = scaleY(t.y);
        const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
        return (
          <g key={i}>
            <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={COLORS.border} strokeWidth={1.5} markerEnd="url(#arrow)" />
            <text x={mx} y={my - 4} textAnchor="middle" fill={COLORS.textMuted} fontSize={9}>{e.label}</text>
          </g>
        );
      })}
      {nodes.map((n) => {
        const cx = scaleX(n.x), cy = scaleY(n.y);
        const color = RISK_COLORS[n.riskLevel] || COLORS.primary;
        const r = n.type === 'ENTITY' ? 20 : 14;
        return (
          <g key={n.id}>
            <circle cx={cx} cy={cy} r={r} fill={color + '33'} stroke={color} strokeWidth={2} />
            <text x={cx} y={cy + 4} textAnchor="middle" fill={color} fontSize={8} fontWeight="bold">
              {n.id.replace('ENT-', 'E').replace('ACC-', 'A')}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ─── Main dashboard ──────────────────────────────────────────────────────────

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [riskScores, setRiskScores] = useState([]);
  const [network, setNetwork] = useState({ nodes: [], edges: [] });
  const [transactions, setTransactions] = useState([]);
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch('/api/stats').then(r => r.json()),
      fetch('/api/alerts').then(r => r.json()),
      fetch('/api/risk-scores').then(r => r.json()),
      fetch('/api/network').then(r => r.json()),
      fetch('/api/transactions').then(r => r.json()),
    ]).then(([s, a, r, n, t]) => {
      setStats(s);
      setAlerts(a.alerts || []);
      setRiskScores(r.riskScores || []);
      setNetwork(n);
      setTransactions(t.transactions || []);
      setLoading(false);
    });
  }, []);

  const tabs = [
    { id: 'overview', label: '📊 Overview' },
    { id: 'alerts', label: '🚨 Alerts' },
    { id: 'risk', label: '⚠️ Risk Scores' },
    { id: 'network', label: '🕸️ Network' },
    { id: 'transactions', label: '💸 Transactions' },
  ];

  const containerStyle = {
    minHeight: '100vh',
    background: COLORS.bg,
    color: COLORS.textPrimary,
    fontFamily: "'Segoe UI', system-ui, -apple-system, sans-serif",
    fontSize: 14,
  };

  const headerStyle = {
    background: COLORS.surface,
    borderBottom: `1px solid ${COLORS.border}`,
    padding: '0 32px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    height: 64,
    position: 'sticky',
    top: 0,
    zIndex: 100,
  };

  if (loading) {
    return (
      <div style={{ ...containerStyle, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>🔍</div>
          <p style={{ color: COLORS.textSecondary }}>Loading AML Analytics Platform...</p>
        </div>
      </div>
    );
  }

  const alertsByType = stats?.alertsByType || {};
  const alertTypeTotal = Object.values(alertsByType).reduce((a, b) => a + b, 0);
  const trendMax = Math.max(...(stats?.alertTrend?.map(t => t.count) || [1]));

  return (
    <div style={containerStyle}>
      <Head>
        <title>Financial Crime Analytics Platform</title>
        <meta name="description" content="SMBC-Style AML Financial Crime Analytics Data Platform" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      {/* Header */}
      <header style={headerStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 24 }}>🛡️</span>
          <div>
            <h1 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: COLORS.textPrimary }}>Financial Crime Analytics Platform</h1>
            <p style={{ margin: 0, fontSize: 11, color: COLORS.textMuted }}>SMBC-Style AML | Azure / Databricks / PostgreSQL</p>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ fontSize: 12, color: COLORS.textMuted }}>Sprint 4 — AML Scoring Engine</span>
          <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: COLORS.success }} />
          <span style={{ fontSize: 12, color: COLORS.success }}>Live</span>
        </div>
      </header>

      {/* Tab navigation */}
      <nav style={{ background: COLORS.surface, borderBottom: `1px solid ${COLORS.border}`, padding: '0 32px', display: 'flex', gap: 4 }}>
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              background: 'none',
              border: 'none',
              padding: '14px 16px',
              cursor: 'pointer',
              color: activeTab === tab.id ? COLORS.primary : COLORS.textSecondary,
              borderBottom: activeTab === tab.id ? `2px solid ${COLORS.primary}` : '2px solid transparent',
              fontWeight: activeTab === tab.id ? 600 : 400,
              fontSize: 13,
              transition: 'color 0.2s',
            }}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <main style={{ padding: '24px 32px', maxWidth: 1400, margin: '0 auto' }}>

        {/* ── OVERVIEW ───────────────────────────────────────────────────── */}
        {activeTab === 'overview' && (
          <div>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 24 }}>
              <StatCard title="Total Alerts" value={stats.overview.totalAlerts} subtitle={`${stats.overview.openAlerts} open`} color={COLORS.danger} icon="🚨" />
              <StatCard title="Critical Entities" value={stats.overview.criticalEntities} subtitle="requiring immediate action" color={COLORS.critical} icon="⚠️" />
              <StatCard title="Transactions Monitored" value={stats.overview.transactionsMonitored.toLocaleString()} subtitle="last 30 days" color={COLORS.primary} icon="💸" />
              <StatCard title="Value Flagged" value={`$${(stats.overview.totalValueFlagged / 1e6).toFixed(1)}M`} subtitle="under investigation" color={COLORS.warning} icon="🏦" />
              <StatCard title="Avg Risk Score" value={stats.overview.avgRiskScore} subtitle="across all entities" color={COLORS.info} icon="📈" />
              <StatCard title="SARs Filed (MTD)" value={stats.overview.sarsFiledMtd} subtitle="Suspicious Activity Reports" color={COLORS.success} icon="📋" />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              {/* Alert trend */}
              <div style={{ background: COLORS.surface, border: `1px solid ${COLORS.border}`, borderRadius: 12, padding: 20 }}>
                <h3 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 600, color: COLORS.textSecondary }}>Alert Trend (7 Days)</h3>
                <BarChart
                  data={(stats.alertTrend || []).map(t => ({ count: t.count, label: t.date.slice(5) }))}
                  maxValue={trendMax}
                  colorFn={(i) => `hsl(${220 + i * 8}, 70%, 55%)`}
                />
              </div>

              {/* Alert type distribution */}
              <div style={{ background: COLORS.surface, border: `1px solid ${COLORS.border}`, borderRadius: 12, padding: 20 }}>
                <h3 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 600, color: COLORS.textSecondary }}>Alert Distribution by Type</h3>
                {Object.entries(alertsByType).map(([type, count]) => (
                  <DonutSegment key={type} value={count} total={alertTypeTotal} color={ALERT_TYPE_COLORS[type] || COLORS.primary} label={type.replace('_', ' ')} />
                ))}
              </div>
            </div>

            {/* Recent alerts */}
            <div style={{ background: COLORS.surface, border: `1px solid ${COLORS.border}`, borderRadius: 12, padding: 20, marginTop: 16 }}>
              <h3 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 600, color: COLORS.textSecondary }}>Recent High-Risk Alerts</h3>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: `1px solid ${COLORS.border}` }}>
                    {['Alert ID', 'Entity', 'Type', 'Risk Score', 'Status', 'Created'].map(h => (
                      <th key={h} style={{ textAlign: 'left', padding: '8px 12px', color: COLORS.textMuted, fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {alerts.filter(a => a.riskScore > 70).slice(0, 5).map(a => (
                    <tr key={a.alertId} style={{ borderBottom: `1px solid ${COLORS.border}22` }}>
                      <td style={{ padding: '10px 12px', color: COLORS.primary, fontFamily: 'monospace', fontSize: 12 }}>{a.alertId}</td>
                      <td style={{ padding: '10px 12px', color: COLORS.textPrimary }}>{a.entityName}</td>
                      <td style={{ padding: '10px 12px' }}><Badge label={a.alertType} color={ALERT_TYPE_COLORS[a.alertType]} /></td>
                      <td style={{ padding: '10px 12px', color: a.riskScore >= 80 ? COLORS.danger : COLORS.warning, fontWeight: 700 }}>{a.riskScore.toFixed(1)}</td>
                      <td style={{ padding: '10px 12px' }}><Badge label={a.status} color={STATUS_COLORS[a.status]} /></td>
                      <td style={{ padding: '10px 12px', color: COLORS.textMuted, fontSize: 12 }}>{new Date(a.createdAt).toLocaleDateString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ── ALERTS ─────────────────────────────────────────────────────── */}
        {activeTab === 'alerts' && (
          <div>
            <h2 style={{ margin: '0 0 20px', fontSize: 18, fontWeight: 700 }}>AML Alerts</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {alerts.map(a => (
                <div key={a.alertId} style={{
                  background: COLORS.surface,
                  border: `1px solid ${COLORS.border}`,
                  borderLeft: `4px solid ${RISK_COLORS[a.riskScore >= 80 ? 'CRITICAL' : a.riskScore >= 60 ? 'HIGH' : 'MEDIUM']}`,
                  borderRadius: 10,
                  padding: '16px 20px',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                    <div>
                      <span style={{ color: COLORS.primary, fontFamily: 'monospace', fontSize: 12, marginRight: 12 }}>{a.alertId}</span>
                      <Badge label={a.alertType} color={ALERT_TYPE_COLORS[a.alertType]} />
                      <span style={{ marginLeft: 8 }}><Badge label={a.status} color={STATUS_COLORS[a.status]} /></span>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <span style={{ fontSize: 22, fontWeight: 700, color: a.riskScore >= 80 ? COLORS.danger : COLORS.warning }}>{a.riskScore.toFixed(1)}</span>
                      <span style={{ color: COLORS.textMuted, fontSize: 11, marginLeft: 4 }}>/ 100</span>
                    </div>
                  </div>
                  <p style={{ margin: '4px 0 8px', fontWeight: 600, color: COLORS.textPrimary }}>{a.entityName}</p>
                  <p style={{ margin: 0, color: COLORS.textSecondary, fontSize: 13 }}>{a.description}</p>
                  <div style={{ marginTop: 10, display: 'flex', gap: 20, fontSize: 12, color: COLORS.textMuted }}>
                    <span>📊 {a.transactionCount} transactions</span>
                    <span>💰 {a.currency} {a.totalAmount.toLocaleString()}</span>
                    <span>🕐 {new Date(a.createdAt).toLocaleString()}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── RISK SCORES ────────────────────────────────────────────────── */}
        {activeTab === 'risk' && (
          <div>
            <h2 style={{ margin: '0 0 20px', fontSize: 18, fontWeight: 700 }}>Entity Risk Scores</h2>
            <table style={{ width: '100%', borderCollapse: 'collapse', background: COLORS.surface, borderRadius: 12, overflow: 'hidden', border: `1px solid ${COLORS.border}` }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${COLORS.border}` }}>
                  {['Entity ID', 'Name', 'Risk Score', 'Risk Level', 'PEP', 'Country', 'Last Updated'].map(h => (
                    <th key={h} style={{ textAlign: 'left', padding: '12px 16px', color: COLORS.textMuted, fontSize: 11, fontWeight: 600, textTransform: 'uppercase' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {riskScores.map((r, i) => (
                  <tr key={r.entityId} style={{ borderBottom: `1px solid ${COLORS.border}22`, background: i % 2 === 0 ? 'transparent' : COLORS.bg + '44' }}>
                    <td style={{ padding: '12px 16px', color: COLORS.primary, fontFamily: 'monospace', fontSize: 12 }}>{r.entityId}</td>
                    <td style={{ padding: '12px 16px', color: COLORS.textPrimary, fontWeight: 500 }}>{r.entityName}</td>
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <div style={{ width: 60, height: 6, background: COLORS.border, borderRadius: 3 }}>
                          <div style={{ width: `${r.score}%`, height: '100%', background: RISK_COLORS[r.riskLevel], borderRadius: 3 }} />
                        </div>
                        <span style={{ color: RISK_COLORS[r.riskLevel], fontWeight: 700, fontSize: 13 }}>{r.score.toFixed(1)}</span>
                      </div>
                    </td>
                    <td style={{ padding: '12px 16px' }}><Badge label={r.riskLevel} color={RISK_COLORS[r.riskLevel]} /></td>
                    <td style={{ padding: '12px 16px', color: r.pepFlag ? COLORS.danger : COLORS.textMuted }}>{r.pepFlag ? '⚠️ YES' : 'No'}</td>
                    <td style={{ padding: '12px 16px', color: COLORS.textSecondary, fontFamily: 'monospace' }}>{r.countryCode}</td>
                    <td style={{ padding: '12px 16px', color: COLORS.textMuted, fontSize: 12 }}>{new Date(r.lastUpdated).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* ── NETWORK ────────────────────────────────────────────────────── */}
        {activeTab === 'network' && (
          <div>
            <h2 style={{ margin: '0 0 8px', fontSize: 18, fontWeight: 700 }}>Transaction Network Graph</h2>
            <p style={{ color: COLORS.textMuted, margin: '0 0 20px', fontSize: 13 }}>Entity–account relationship graph highlighting layering patterns and suspicious fund flows</p>
            <div style={{ background: COLORS.surface, border: `1px solid ${COLORS.border}`, borderRadius: 12, padding: 20, marginBottom: 16 }}>
              <div style={{ display: 'flex', gap: 16, marginBottom: 12, flexWrap: 'wrap' }}>
                {Object.entries(RISK_COLORS).map(([level, color]) => (
                  <div key={level} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{ width: 10, height: 10, borderRadius: '50%', background: color }} />
                    <span style={{ color: COLORS.textMuted, fontSize: 12 }}>{level}</span>
                  </div>
                ))}
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{ width: 18, height: 18, borderRadius: '50%', border: `2px solid ${COLORS.primary}` }} />
                  <span style={{ color: COLORS.textMuted, fontSize: 12 }}>Entity (E)</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{ width: 14, height: 14, borderRadius: '50%', border: `2px solid ${COLORS.primary}` }} />
                  <span style={{ color: COLORS.textMuted, fontSize: 12 }}>Account (A)</span>
                </div>
              </div>
              <NetworkViz nodes={network.nodes} edges={network.edges} />
            </div>
            <div style={{ background: COLORS.surface, border: `1px solid ${COLORS.border}`, borderRadius: 12, padding: 20 }}>
              <h3 style={{ margin: '0 0 12px', fontSize: 13, fontWeight: 600, color: COLORS.textSecondary }}>Detected Transaction Chains</h3>
              {network.edges && network.edges.map((e, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, padding: '8px 12px', background: COLORS.bg, borderRadius: 6, fontSize: 13 }}>
                  <span style={{ color: COLORS.primary, fontFamily: 'monospace' }}>{e.source}</span>
                  <span style={{ color: COLORS.textMuted }}>→</span>
                  <span style={{ color: COLORS.primary, fontFamily: 'monospace' }}>{e.target}</span>
                  <span style={{ flex: 1 }} />
                  <span style={{ color: COLORS.warning, fontWeight: 600 }}>{e.label}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── TRANSACTIONS ───────────────────────────────────────────────── */}
        {activeTab === 'transactions' && (
          <div>
            <h2 style={{ margin: '0 0 20px', fontSize: 18, fontWeight: 700 }}>Transaction Monitoring</h2>
            <table style={{ width: '100%', borderCollapse: 'collapse', background: COLORS.surface, borderRadius: 12, overflow: 'hidden', border: `1px solid ${COLORS.border}` }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${COLORS.border}` }}>
                  {['TXN ID', 'Source', 'Destination', 'Amount', 'Type', 'Status', 'Risk', 'Flagged'].map(h => (
                    <th key={h} style={{ textAlign: 'left', padding: '12px 14px', color: COLORS.textMuted, fontSize: 11, fontWeight: 600, textTransform: 'uppercase' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {transactions.map((t, i) => (
                  <tr key={t.transactionId} style={{ borderBottom: `1px solid ${COLORS.border}22`, background: t.flagged ? COLORS.danger + '08' : 'transparent' }}>
                    <td style={{ padding: '10px 14px', color: COLORS.primary, fontFamily: 'monospace', fontSize: 11 }}>{t.transactionId}</td>
                    <td style={{ padding: '10px 14px', color: COLORS.textSecondary, fontFamily: 'monospace', fontSize: 11 }}>{t.sourceAccount}</td>
                    <td style={{ padding: '10px 14px', color: COLORS.textSecondary, fontFamily: 'monospace', fontSize: 11 }}>{t.destinationAccount}</td>
                    <td style={{ padding: '10px 14px', color: COLORS.textPrimary, fontWeight: 600 }}>{t.currency} {t.amount.toLocaleString()}</td>
                    <td style={{ padding: '10px 14px' }}><Badge label={t.transactionType} color={COLORS.info} /></td>
                    <td style={{ padding: '10px 14px' }}><Badge label={t.status} color={t.status === 'COMPLETED' ? COLORS.success : COLORS.warning} /></td>
                    <td style={{ padding: '10px 14px', color: t.riskScore >= 80 ? COLORS.danger : t.riskScore >= 60 ? COLORS.warning : COLORS.success, fontWeight: 700 }}>{t.riskScore}</td>
                    <td style={{ padding: '10px 14px' }}>{t.flagged ? <span style={{ color: COLORS.danger }}>🚩 YES</span> : <span style={{ color: COLORS.textMuted }}>—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>

      <footer style={{ textAlign: 'center', padding: '24px', color: COLORS.textMuted, fontSize: 11, borderTop: `1px solid ${COLORS.border}`, marginTop: 32 }}>
        Financial Crime Analytics Platform · SMBC-Style AML · Python · Java · SQL · Azure · Databricks · Docker · Vercel
      </footer>
    </div>
  );
}
