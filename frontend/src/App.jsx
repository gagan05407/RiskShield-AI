import React, { useState, useEffect } from 'react';
import {
  LayoutDashboard, CreditCard, Search, Zap, LineChart, FileText, Settings,
  ChevronLeft, ChevronRight, Download, Upload, CheckCircle2, AlertTriangle, AlertOctagon,
  Shield, Send, RefreshCw, Lock, Cpu, Database, Play, Eye, FileSpreadsheet, ArrowRight, X,
  UserCheck, Users, MessageSquare, Bell, CheckCircle, AlertCircle
} from 'lucide-react';
import {
  PieChart, Pie, Cell, ResponsiveContainer, ScatterChart, Scatter, XAxis, YAxis, Tooltip,
  BarChart, Bar, Legend, CartesianGrid
} from 'recharts';
import * as api from './api';
import LoginModal from './LoginModal';
import UserApprovalView from './UserApprovalView';

const ROLE_CONFIG = {
  admin: {
    roleTitle: 'System Administrator',
    badge: 'Admin',
    defaultNav: 'AI Settings',
    allowedNavs: ['AI Settings', 'Model Performance', 'Audit Logs', 'User Approval', 'Communication'],
    navItems: [
      { name: 'AI Settings', icon: Settings },
      { name: 'Model Performance', icon: LineChart },
      { name: 'Audit Logs', icon: FileText },
      { name: 'User Approval', icon: UserCheck },
      { name: 'Communication', icon: MessageSquare },
    ]
  },
  analyst: {
    roleTitle: 'Risk Analyst',
    badge: 'Analyst',
    defaultNav: 'Overview',
    allowedNavs: ['Overview', 'Transactions', 'Investigation', 'AI Copilot', 'Dataset', 'Models', 'Admin Support'],
    navItems: [
      { name: 'Overview', icon: LayoutDashboard },
      { name: 'Transactions', icon: CreditCard },
      { name: 'Investigation', icon: Search },
      { name: 'AI Copilot', icon: Zap },
      { name: 'Dataset', icon: Database },
      { name: 'Models', icon: Cpu },
      { name: 'Admin Support', icon: MessageSquare },
    ]
  },
  viewer: {
    roleTitle: 'Transaction Viewer',
    badge: 'Viewer',
    defaultNav: 'Transactions',
    allowedNavs: ['Transactions'],
    navItems: [
      { name: 'Transactions', icon: CreditCard },
    ]
  }
};


// ─────────────────────────────────────────────────────────────────────────────
// MARKDOWN RENDERER HELPER FOR TABLES, BOLD, AND CODE
// ─────────────────────────────────────────────────────────────────────────────
function renderMarkdown(text) {
  if (!text) return null;

  // Split content by table blocks or double newlines
  const lines = text.split('\n');
  const elements = [];
  let inTable = false;
  let tableRows = [];
  let currentParagraph = [];

  const flushParagraph = (key) => {
    if (currentParagraph.length > 0) {
      const pText = currentParagraph.join('\n');
      elements.push(
        <p key={key} style={{ marginBottom: 12, lineHeight: 1.6 }} dangerouslySetInnerHTML={{ __html: formatInline(pText) }} />
      );
      currentParagraph = [];
    }
  };

  const flushTable = (key) => {
    if (tableRows.length > 0) {
      const headerRow = tableRows[0];
      const bodyRows = tableRows.slice(2); // Skip header & separator line (|---|)

      const parseCells = (rowStr) =>
        rowStr.split('|').map(c => c.trim()).filter((c, idx, arr) => idx > 0 && idx < arr.length - 1);

      const headers = parseCells(headerRow);

      elements.push(
        <div key={key} className="rs-table-wrap" style={{ margin: '14px 0' }}>
          <table className="rs-table">
            <thead>
              <tr>
                {headers.map((h, i) => (
                  <th key={i} dangerouslySetInnerHTML={{ __html: formatInline(h) }} />
                ))}
              </tr>
            </thead>
            <tbody>
              {bodyRows.map((rStr, rIdx) => {
                const cells = parseCells(rStr);
                if (cells.length === 0) return null;
                return (
                  <tr key={rIdx}>
                    {cells.map((cell, cIdx) => (
                      <td key={cIdx} dangerouslySetInnerHTML={{ __html: formatInline(cell) }} />
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      );
      tableRows = [];
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
      flushParagraph(`p-${i}`);
      inTable = true;
      tableRows.push(line.trim());
    } else {
      if (inTable) {
        flushTable(`tbl-${i}`);
        inTable = false;
      }
      if (line.startsWith('### ')) {
        flushParagraph(`p-${i}`);
        elements.push(<h3 key={`h3-${i}`} style={{ fontSize: '1.05rem', fontWeight: 800, marginTop: 14, marginBottom: 8 }} dangerouslySetInnerHTML={{ __html: formatInline(line.replace('### ', '')) }} />);
      } else if (line.startsWith('## ')) {
        flushParagraph(`p-${i}`);
        elements.push(<h2 key={`h2-${i}`} style={{ fontSize: '1.15rem', fontWeight: 800, marginTop: 16, marginBottom: 8 }} dangerouslySetInnerHTML={{ __html: formatInline(line.replace('## ', '')) }} />);
      } else if (line.trim()) {
        currentParagraph.push(line);
      } else {
        flushParagraph(`p-${i}`);
      }
    }
  }

  if (inTable) flushTable(`tbl-final`);
  flushParagraph(`p-final`);

  return <div>{elements}</div>;
}

function formatInline(str) {
  if (!str) return '';
  return str
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br/>');
}


// ─────────────────────────────────────────────────────────────────────────────
// MAIN APP COMPONENT
// ─────────────────────────────────────────────────────────────────────────────
export default function App() {
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('riskshield_user');
    return saved ? JSON.parse(saved) : null;
  });
  const [token, setToken] = useState(() => localStorage.getItem('riskshield_token'));

  const userRole = (user?.role || 'analyst').toLowerCase();
  const roleConfig = ROLE_CONFIG[userRole] || ROLE_CONFIG.analyst;

  const [activeNav, setActiveNav] = useState(() => {
    const r = (user?.role || 'analyst').toLowerCase();
    return ROLE_CONFIG[r]?.defaultNav || 'Overview';
  });

  const [collapsed, setCollapsed] = useState(false);
  const [systemStatus, setSystemStatus] = useState(null);
  const [datasets, setDatasets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [notification, setNotification] = useState(null);
  const [activeTxId, setActiveTxId] = useState('TX1001');
  const [unreadCount, setUnreadCount] = useState(0);

  const fetchUnreadCount = async () => {
    if (!token || userRole === 'viewer') return;
    try {
      const res = await api.getUnreadNotificationCount();
      setUnreadCount(res.unread_count || 0);
    } catch (err) {
      console.error("Error fetching unread notification count:", err);
    }
  };

  useEffect(() => {
    fetchUnreadCount();
    const interval = setInterval(fetchUnreadCount, 8000);
    return () => clearInterval(interval);
  }, [token, userRole]);

  // Enforce role route protection: if current activeNav is not allowed for role, redirect to default
  useEffect(() => {
    if (user && roleConfig) {
      if (!roleConfig.allowedNavs.includes(activeNav)) {
        setActiveNav(roleConfig.defaultNav);
      }
    }
  }, [userRole, roleConfig, activeNav, user]);


  useEffect(() => {
    const handleLogout = () => {
      setUser(null);
      setToken(null);
    };
    window.addEventListener('auth_logout', handleLogout);
    return () => window.removeEventListener('auth_logout', handleLogout);
  }, []);

  const showToast = (msg, type = 'success') => {
    setNotification({ msg, type });
    setTimeout(() => setNotification(null), 4000);
  };

  const fetchStatus = async () => {
    if (!token) return;
    try {
      const status = await api.getSystemStatus();
      setSystemStatus(status);
      const ds = await api.getDatasets();
      setDatasets(ds.datasets || []);
    } catch (err) {
      console.error("Failed to fetch system status:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (token) {
      fetchStatus();
    }
  }, [token]);

  const handleLoginSuccess = (userData) => {
    setUser(userData);
    setToken(localStorage.getItem('riskshield_token'));
    const r = (userData.role || 'analyst').toLowerCase();
    const targetNav = ROLE_CONFIG[r]?.defaultNav || 'Overview';
    setActiveNav(targetNav);
    showToast(`Welcome back, ${userData.full_name || userData.username}! Logged in as ${ROLE_CONFIG[r]?.roleTitle || r}`);
  };

  const handleDatasetSwitch = async (filename) => {
    try {
      setLoading(true);
      const newStatus = await api.switchDataset(filename);
      setSystemStatus(newStatus);
      await fetchStatus();
      const txData = await api.getTransactions({ page: 1, page_size: 10 });
      if (txData.items && txData.items.length > 0) {
        setActiveTxId(txData.items[0].transaction_id);
      }
      showToast(`Switched active dataset to: ${newStatus.active_dataset_label || filename}`);
    } catch (err) {
      showToast("Failed to switch dataset", "danger");
    } finally {
      setLoading(false);
    }
  };

  const handleRecordDecision = async (txId, newDecision, reason = '') => {
    try {
      const remark = reason.trim() || `Analyst set decision to ${newDecision}`;
      const res = await api.recordDecision(txId, newDecision, remark);
      if (res.success) {
        showToast(`Analyst decision for ${txId} set to ${newDecision}`);
        fetchStatus();
      }
      return res;
    } catch (err) {
      showToast(`Failed to record decision for ${txId}`, "danger");
    }
  };

  if (!token || !user) {
    return <LoginModal onLoginSuccess={handleLoginSuccess} />;
  }

  return (
    <div className={`rs-app ${collapsed ? 'sidebar-collapsed' : ''}`}>
      {/* Toast Notification */}
      {notification && (
        <div style={{
          position: 'fixed', top: 16, right: 24, zIndex: 1000,
          background: notification.type === 'danger' ? '#DC2626' : '#059669',
          color: '#FFF', padding: '10px 18px', borderRadius: 8, fontWeight: 600,
          boxShadow: '0 4px 14px rgba(0,0,0,0.15)', display: 'flex', alignItems: 'center', gap: 8
        }}>
          {notification.type === 'danger' ? <AlertOctagon size={18} /> : <CheckCircle2 size={18} />}
          {notification.msg}
        </div>
      )}

      {/* Sidebar */}
      <aside className={`rs-sidebar ${collapsed ? 'collapsed' : ''}`}>
        <div className="rs-sidebar-brand">
          <div className="rs-brand-info">
            <img src="/logo.svg" alt="RiskShield Logo" width={28} height={28} />
            {!collapsed && (
              <div>
                <div className="rs-brand-title">RiskShield AI</div>
                <div className="rs-brand-sub">{roleConfig.roleTitle}</div>
              </div>
            )}
          </div>
          <button className="rs-toggle-btn" onClick={() => setCollapsed(!collapsed)}>
            {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
          </button>
        </div>

        <nav className="rs-sidebar-nav">
          <div className="rs-sidebar-section" style={{ paddingTop: 4 }}>Navigation</div>
          <div className="rs-nav-group">
            {roleConfig.navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeNav === item.name;
              return (
                <button
                  key={item.name}
                  className={`rs-nav-item ${isActive ? 'active' : ''}`}
                  onClick={() => setActiveNav(item.name)}
                  title={collapsed ? item.name : undefined}
                >
                  <Icon size={17} className="rs-nav-icon" />
                  {!collapsed && <span>{item.name}</span>}
                </button>
              );
            })}
          </div>

          {!collapsed && (
            <>
              {/* Only Analysts have active dataset scenarios switcher in sidebar */}
              {userRole === 'analyst' && (
                <>
                  <div className="rs-sidebar-section">Active Dataset</div>
                  <div style={{ padding: '0 4px 6px' }}>
                    <select
                      className="rs-dataset-select"
                      value={systemStatus?.active_dataset || 'mixed_risk_transactions.csv'}
                      onChange={(e) => handleDatasetSwitch(e.target.value)}
                    >
                      {datasets.map((d) => (
                        <option key={d.filename} value={d.filename}>{d.label}</option>
                      ))}
                    </select>
                  </div>

                  <div className="rs-sidebar-section">Quick Scenarios</div>
                  <div style={{ padding: '0 4px 6px' }}>
                    <div className="rs-scenarios-grid">
                      <button className="rs-btn-scen" onClick={() => handleDatasetSwitch('normal_transactions.csv')}>Normal</button>
                      <button className="rs-btn-scen" onClick={() => handleDatasetSwitch('mixed_risk_transactions.csv')}>Mixed</button>
                      <button className="rs-btn-scen" onClick={() => handleDatasetSwitch('fraud_spike_transactions.csv')}>Fraud Spike</button>
                      <button className="rs-btn-scen" onClick={() => handleDatasetSwitch('edge_case_transactions.csv')}>Edge Cases</button>
                    </div>
                    <button
                      className="rs-btn-scen"
                      style={{ width: '100%', marginTop: 2, background: 'rgba(220, 38, 38, 0.15)', borderColor: '#DC2626', color: '#FCA5A5' }}
                      onClick={() => handleDatasetSwitch('fraud_transactions.csv')}
                    >
                      High Risk / Fraud
                    </button>
                  </div>
                </>
              )}

              <div className="rs-sidebar-section">System Status</div>
              <div style={{ padding: '0 6px 12px', display: 'flex', flexDirection: 'column', gap: 5, fontSize: '0.75rem', color: '#94A3B8' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span className="rs-status-dot green" /> ML Engine (XGBoost)
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span className="rs-status-dot green" /> Agent + RAG (ChromaDB)
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span className={`rs-status-dot ${systemStatus?.redis_status === 'ONLINE' ? 'green' : 'amber'}`} />
                  Redis Cache: {systemStatus?.redis_status === 'ONLINE' ? 'Active' : 'Fallback Mode'}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span className={`rs-status-dot ${systemStatus?.celery_status === 'ONLINE' ? 'green' : 'amber'}`} />
                  Celery Worker: {systemStatus?.celery_status === 'ONLINE' ? 'Active' : 'Inline Mode'}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span className={`rs-status-dot ${systemStatus?.has_api_key ? 'green' : 'amber'}`} />
                  LLM: {systemStatus?.provider ? `${systemStatus.provider.slice(0, 8)}...` : 'Offline'}
                </div>
              </div>
            </>
          )}
        </nav>
      </aside>

      {/* Main Workspace */}
      <main className="rs-main-content">
        {/* Header */}
        <header className="rs-header">
          <div className="rs-header-title-wrap">
            <img src="/logo.svg" alt="RiskShield" width={22} height={22} />
            <div>
              <div className="rs-header-title">RiskShield AI</div>
              <div className="rs-header-sub">{roleConfig.roleTitle} Platform</div>
            </div>
          </div>

          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
            {userRole !== 'viewer' && (
              <button
                className="rs-btn"
                style={{
                  background: unreadCount > 0 ? '#EFF6FF' : '#F8FAFC',
                  border: `1px solid ${unreadCount > 0 ? '#3B82F6' : 'var(--rs-border)'}`,
                  position: 'relative',
                  padding: '6px 12px',
                  borderRadius: 8,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6
                }}
                onClick={() => {
                  setActiveNav(userRole === 'admin' ? 'Communication' : 'Admin Support');
                  fetchUnreadCount();
                }}
                title="Notifications & Admin Support"
              >
                <Bell size={18} color={unreadCount > 0 ? '#2563EB' : '#64748B'} />
                <span style={{ fontSize: '0.78rem', fontWeight: 700, color: unreadCount > 0 ? '#1E40AF' : '#475569' }}>
                  Notifications
                </span>
                {unreadCount > 0 && (
                  <span
                    style={{
                      padding: '2px 7px',
                      fontSize: '0.72rem',
                      fontWeight: 800,
                      borderRadius: 10,
                      background: '#DC2626',
                      color: '#FFFFFF'
                    }}
                  >
                    {unreadCount}
                  </span>
                )}
              </button>
            )}

            <div className="rs-user-profile-badge">
              <div
                className="rs-user-avatar"
                style={{
                  background: userRole === 'admin' ? '#0F172A' : userRole === 'analyst' ? '#2563EB' : '#475569'
                }}
              >
                {user?.username ? user.username.charAt(0).toUpperCase() : 'U'}
              </div>
              <div className="rs-user-info">
                <span className="rs-user-name">{user?.full_name || user?.username || 'User'}</span>
                <span
                  className="rs-user-role"
                  style={{
                    fontWeight: 700,
                    color: userRole === 'admin' ? '#2563EB' : userRole === 'analyst' ? '#059669' : '#64748B'
                  }}
                >
                  {roleConfig.roleTitle} ({roleConfig.badge})
                </span>
              </div>
            </div>
            <button className="rs-logout-btn" onClick={api.logoutUser}>
              Logout
            </button>
          </div>
        </header>


        {/* Dynamic Page Views */}
        <div className="rs-body">
          {/* Access Denied Guard */}
          {!roleConfig.allowedNavs.includes(activeNav) && (
            <div className="rs-panel" style={{ textAlign: 'center', padding: '40px 20px' }}>
              <AlertOctagon size={40} color="#DC2626" style={{ margin: '0 auto 10px' }} />
              <h2 style={{ color: '#0F172A', fontWeight: 800, fontSize: '1.2rem' }}>Access Restricted</h2>
              <p style={{ color: '#64748B', maxWidth: 440, margin: '6px auto 14px', fontSize: '0.85rem' }}>
                Your role (<strong>{roleConfig.roleTitle}</strong>) does not have permission to access the <strong>{activeNav}</strong> section.
              </p>
              <button className="rs-btn rs-btn-primary" onClick={() => setActiveNav(roleConfig.defaultNav)}>
                Return to {roleConfig.defaultNav}
              </button>
            </div>
          )}

          {/* Admin Views */}
          {activeNav === 'AI Settings' && roleConfig.allowedNavs.includes('AI Settings') && (
            <AIConfigView showToast={showToast} fetchStatus={fetchStatus} />
          )}
          {activeNav === 'Model Performance' && roleConfig.allowedNavs.includes('Model Performance') && (
            <ModelPerformanceView showToast={showToast} />
          )}
          {activeNav === 'Audit Logs' && roleConfig.allowedNavs.includes('Audit Logs') && (
            <AuditLogsView />
          )}
          {activeNav === 'User Approval' && roleConfig.allowedNavs.includes('User Approval') && (
            <UserApprovalView showToast={showToast} />
          )}
          {activeNav === 'Communication' && roleConfig.allowedNavs.includes('Communication') && (
            <AdminCommunicationView showToast={showToast} />
          )}

          {/* Analyst & Viewer Views */}
          {activeNav === 'Overview' && roleConfig.allowedNavs.includes('Overview') && (
            <OverviewView showToast={showToast} systemStatus={systemStatus} />
          )}
          {activeNav === 'Transactions' && roleConfig.allowedNavs.includes('Transactions') && (
            <TransactionsView
              showToast={showToast}
              setActiveNav={setActiveNav}
              activeTxId={activeTxId}
              setActiveTxId={setActiveTxId}
              systemStatus={systemStatus}
              handleRecordDecision={handleRecordDecision}
              userRole={userRole}
            />
          )}
          {activeNav === 'Investigation' && roleConfig.allowedNavs.includes('Investigation') && (
            <InvestigationView
              showToast={showToast}
              activeTxId={activeTxId}
              setActiveTxId={setActiveTxId}
              handleRecordDecision={handleRecordDecision}
            />
          )}
          {activeNav === 'AI Copilot' && roleConfig.allowedNavs.includes('AI Copilot') && (
            <CopilotView
              showToast={showToast}
              systemStatus={systemStatus}
              activeTxId={activeTxId}
              setActiveTxId={setActiveTxId}
              handleRecordDecision={handleRecordDecision}
            />
          )}
          {activeNav === 'Dataset' && roleConfig.allowedNavs.includes('Dataset') && (
            <DatasetView
              datasets={datasets}
              systemStatus={systemStatus}
              handleDatasetSwitch={handleDatasetSwitch}
              showToast={showToast}
            />
          )}
          {activeNav === 'Models' && roleConfig.allowedNavs.includes('Models') && (
            <ModelsView showToast={showToast} />
          )}
          {activeNav === 'Admin Support' && roleConfig.allowedNavs.includes('Admin Support') && (
            <AnalystCommunicationView showToast={showToast} systemStatus={systemStatus} />
          )}

        </div>
      </main>
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────────────
// VIEW 1: OVERVIEW
// ─────────────────────────────────────────────────────────────────────────────
function OverviewView({ showToast, systemStatus }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getOverview().then(setData).finally(() => setLoading(false));
  }, [systemStatus]);

  if (loading || !data) return <div className="rs-panel">Loading Overview...</div>;

  const { summary, pie_data, scatter_sample, pm_summary, top_locations, high_priority } = data;

  return (
    <div>
      <div className="rs-page-hero">
        <h1 className="rs-page-title">Risk Management Overview</h1>
        <p className="rs-page-sub">
          Real-time monitoring of payment transactions, risk distribution, and high-priority anomalies — {systemStatus?.active_dataset_label}
        </p>
      </div>

      {/* KPI Cards */}
      <div className="rs-kpi-grid">
        <div className="rs-kpi-card" style={{ borderTop: '3px solid #2563EB' }}>
          <div className="rs-kpi-header"><CreditCard size={16} /><span className="rs-kpi-label">Total Transactions</span></div>
          <div className="rs-kpi-value">{summary.total.toLocaleString()}</div>
          <div className="rs-kpi-sub">+{summary.new_count} real-time</div>
        </div>

        <div className="rs-kpi-card" style={{ borderTop: '3px solid #059669' }}>
          <div className="rs-kpi-header"><CheckCircle2 size={16} color="#059669" /><span className="rs-kpi-label">Approved</span></div>
          <div className="rs-kpi-value">{summary.approve.toLocaleString()}</div>
          <div className="rs-kpi-sub">{((summary.approve / max1(summary.total)) * 100).toFixed(1)}% of total</div>
        </div>

        <div className="rs-kpi-card" style={{ borderTop: '3px solid #D97706' }}>
          <div className="rs-kpi-header"><AlertTriangle size={16} color="#D97706" /><span className="rs-kpi-label">Under Review</span></div>
          <div className="rs-kpi-value">{summary.review.toLocaleString()}</div>
          <div className="rs-kpi-sub">{((summary.review / max1(summary.total)) * 100).toFixed(1)}% of total</div>
        </div>

        <div className="rs-kpi-card" style={{ borderTop: '3px solid #DC2626' }}>
          <div className="rs-kpi-header"><Shield size={16} color="#DC2626" /><span className="rs-kpi-label">On Hold</span></div>
          <div className="rs-kpi-value">{summary.hold.toLocaleString()}</div>
          <div className="rs-kpi-sub">{summary.high_risk_rate}% of total</div>
        </div>

        <div className="rs-kpi-card" style={{ borderTop: '3px solid #4F46E5' }}>
          <div className="rs-kpi-header"><LineChart size={16} color="#4F46E5" /><span className="rs-kpi-label">High Risk Rate</span></div>
          <div className="rs-kpi-value">{summary.high_risk_rate}%</div>
          <div className="rs-kpi-sub">Flagged as HOLD</div>
        </div>

        <div className="rs-kpi-card" style={{ borderTop: '3px solid #DC2626' }}>
          <div className="rs-kpi-header"><Lock size={16} color="#DC2626" /><span className="rs-kpi-label">Amount at Risk</span></div>
          <div className="rs-kpi-value">₹{(summary.amount_at_risk / 100000).toFixed(1)}L</div>
          <div className="rs-kpi-sub">HOLD transactions</div>
        </div>
      </div>

      {/* Charts Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 14, marginBottom: 14 }}>
        {/* Risk Distribution Donut */}
        <div className="rs-panel" style={{ marginBottom: 0 }}>
          <div className="rs-panel-title">Risk Distribution</div>
          <div style={{ height: 210 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={pie_data} cx="50%" cy="50%" innerRadius={50} outerRadius={78} paddingAngle={4} dataKey="value">
                  {pie_data.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip formatter={(value) => [value.toLocaleString(), 'Count']} />
                <Legend verticalAlign="bottom" height={32} wrapperStyle={{ fontSize: '0.78rem' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Scatter Plot Amount vs Score */}
        <div className="rs-panel" style={{ marginBottom: 0 }}>
          <div className="rs-panel-title">Amount (₹) vs Risk Score</div>
          <div style={{ height: 210 }}>
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 8, right: 14, bottom: 14, left: 6 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                <XAxis type="number" dataKey="amount" name="Amount (₹)" unit="₹" tick={{ fontSize: 11 }} />
                <YAxis type="number" dataKey="risk_score" name="Score" domain={[0, 100]} tick={{ fontSize: 11 }} />
                <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                <Scatter name="Transactions" data={scatter_sample} fill="#2563EB" />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 14, marginBottom: 14 }}>
        {/* Bar Chart by Payment Method */}
        <div className="rs-panel" style={{ marginBottom: 0 }}>
          <div className="rs-panel-title">Risk by Payment Method</div>
          <div style={{ height: 200 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={pm_summary} margin={{ top: 8, right: 10, bottom: 10, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                <XAxis dataKey="payment_method" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: '0.78rem' }} />
                <Bar dataKey="APPROVE" fill="#059669" stackId="a" radius={[0, 0, 0, 0]} />
                <Bar dataKey="REVIEW" fill="#D97706" stackId="a" radius={[0, 0, 0, 0]} />
                <Bar dataKey="HOLD" fill="#DC2626" stackId="a" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Top Risk Locations */}
        <div className="rs-panel" style={{ marginBottom: 0 }}>
          <div className="rs-panel-title">Top High Risk Locations</div>
          <div style={{ height: 200 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={top_locations} layout="vertical" margin={{ top: 8, right: 14, bottom: 10, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis dataKey="location" type="category" width={80} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#4F46E5" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* High Priority Table */}
      <div className="rs-panel">
        <div className="rs-panel-title">High Priority Anomaly Transactions</div>
        <div className="rs-table-wrap">
          <table className="rs-table">
            <thead>
              <tr>
                <th>TX ID</th>
                <th>Customer</th>
                <th>Amount</th>
                <th>Method</th>
                <th>Location</th>
                <th>Risk Score</th>
                <th>Decision</th>
                <th>Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {high_priority.map((tx) => (
                <tr key={tx.transaction_id}>
                  <td><code>{tx.transaction_id}</code></td>
                  <td><code>{tx.customer_id}</code></td>
                  <td>₹{tx.amount.toLocaleString()}</td>
                  <td>{tx.payment_method}</td>
                  <td>{tx.location}</td>
                  <td>
                    <span style={{ fontWeight: 700, color: tx.risk_score > 55 ? '#DC2626' : '#D97706' }}>
                      {tx.risk_score}/100
                    </span>
                  </td>
                  <td>
                    <span className={`rs-badge ${tx.effective_status === 'HOLD' ? 'rs-badge-hold' : 'rs-badge-review'}`}>
                      {tx.effective_status}
                    </span>
                  </td>
                  <td>{tx.timestamp}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────────────
// VIEW 2: TRANSACTIONS
// ─────────────────────────────────────────────────────────────────────────────
function TransactionsView({ showToast, setActiveNav, activeTxId, setActiveTxId, systemStatus, userRole }) {
  const [data, setData] = useState({ items: [], total: 0, page: 1, total_pages: 1, pm_options: [] });
  const [loading, setLoading] = useState(true);
  const [selectedTxId, setSelectedTxId] = useState(activeTxId);
  const [detailData, setDetailData] = useState(null);
  const [newTxModal, setNewTxModal] = useState(false);
  const isViewer = userRole === 'viewer';

  // Filter States
  const [statusFilter, setStatusFilter] = useState(['APPROVE', 'REVIEW', 'HOLD']);
  const [pmFilter, setPmFilter] = useState([]);
  const [custSearch, setCustSearch] = useState('');
  const [txSearch, setTxSearch] = useState('');
  const [minAmt, setMinAmt] = useState(0);
  const [maxAmt, setMaxAmt] = useState(100000);
  const [sortBy, setSortBy] = useState('risk_score_desc');
  const [page, setPage] = useState(1);

  // New Transaction Form
  const [newTx, setNewTx] = useState({
    transaction_id: `TX_RT_${Math.floor(1000 + Math.random() * 9000)}`,
    customer_id: 'C1005',
    amount: 25000,
    payment_method: 'UPI',
    device_id: 'DEV_NEW_99',
    location: 'Mumbai',
    failed_attempts: 0,
    account_age_days: 180
  });

  const [overrideForm, setOverrideForm] = useState({ decision: 'HOLD', remark: '' });

  const loadTransactions = async () => {
    setLoading(true);
    try {
      const res = await api.getTransactions({
        page,
        page_size: 50,
        status: statusFilter.join(','),
        payment_method: pmFilter.join(','),
        cust_search: custSearch,
        tx_search: txSearch,
        min_amount: minAmt > 0 ? minAmt : undefined,
        max_amount: maxAmt < 100000 ? maxAmt : undefined,
        sort_by: sortBy
      });
      setData(res);
    } catch (err) {
      showToast("Failed to load transactions", "danger");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTransactions();
  }, [page, statusFilter, pmFilter, custSearch, txSearch, minAmt, maxAmt, sortBy, systemStatus?.active_dataset]);

  const loadDetail = async (txId) => {
    setSelectedTxId(txId);
    setActiveTxId(txId);
    try {
      const res = await api.getTransactionDetail(txId);
      setDetailData(res);
      setOverrideForm({ decision: res.effective_status, remark: res.latest_action?.analyst_remark || '' });
    } catch (err) {
      showToast("Failed to load transaction details", "danger");
    }
  };

  const handleCreateTx = async (e) => {
    e.preventDefault();
    if (isViewer) return;
    try {
      const res = await api.createNewTransaction(newTx);
      showToast(`Transaction ${res.transaction.transaction_id} scored: ${res.ml_score.status}`);
      setNewTxModal(false);
      loadTransactions();
      loadDetail(res.transaction.transaction_id);
    } catch (err) {
      showToast("Failed to create transaction", "danger");
    }
  };

  const handleOverride = async (e) => {
    e.preventDefault();
    if (isViewer) return;
    if (!overrideForm.remark.trim()) {
      showToast("Analyst remark is required for decision override", "danger");
      return;
    }
    try {
      await api.recordAnalystDecision(selectedTxId, overrideForm.decision, overrideForm.remark);
      showToast(`Decision updated to ${overrideForm.decision}`);
      loadDetail(selectedTxId);
      loadTransactions();
    } catch (err) {
      showToast("Failed to record decision", "danger");
    }
  };

  const handleFileUpload = async (e) => {
    if (isViewer) return;
    const file = e.target.files[0];
    if (!file) return;
    try {
      const res = await api.uploadTransactionsCsv(file);
      showToast(`Uploaded & processed ${res.imported_rows} transactions successfully!`);
      loadTransactions();
    } catch (err) {
      showToast(err.response?.data?.detail || "Upload failed", "danger");
    }
  };

  return (
    <div>
      <div className="rs-page-hero" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 className="rs-page-title">Transaction Operations</h1>
          <p className="rs-page-sub">Search, filter, inspect and export payment transactions — {data.total_working?.toLocaleString() || 0} total working</p>
        </div>
        {!isViewer ? (
          <button className="rs-btn rs-btn-primary" onClick={() => setNewTxModal(true)}>
            + New Real-Time Transaction
          </button>
        ) : (
          <span className="rs-badge" style={{ background: '#F1F5F9', color: '#475569', border: '1px solid #CBD5E1', padding: '6px 12px', fontSize: '0.8rem' }}>
            🔒 Read-Only Access Mode
          </span>
        )}
      </div>

      {/* Filter Bar */}
      <div className="rs-filter-bar">
        <div className="rs-field">
          <label className="rs-label">Status Filter</label>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
            {['APPROVE', 'REVIEW', 'HOLD'].map((st) => (
              <button
                key={st}
                type="button"
                className={`rs-chip-btn ${statusFilter.includes(st) ? 'active' : ''}`}
                style={{ background: statusFilter.includes(st) ? '#0F1F3D' : '#FFF', color: statusFilter.includes(st) ? '#FFF' : '#334155' }}
                onClick={() => {
                  setStatusFilter(statusFilter.includes(st) ? statusFilter.filter(s => s !== st) : [...statusFilter, st]);
                }}
              >
                {st}
              </button>
            ))}
          </div>
        </div>

        <div className="rs-field">
          <label className="rs-label">Customer ID</label>
          <input className="rs-input" placeholder="Search C1005..." value={custSearch} onChange={(e) => setCustSearch(e.target.value)} />
        </div>

        <div className="rs-field">
          <label className="rs-label">Transaction ID</label>
          <input className="rs-input" placeholder="Search TX1001..." value={txSearch} onChange={(e) => setTxSearch(e.target.value)} />
        </div>

        <div className="rs-field">
          <label className="rs-label">Sort By</label>
          <select className="rs-select" value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
            <option value="risk_score_desc">Risk Score ↓</option>
            <option value="risk_score_asc">Risk Score ↑</option>
            <option value="amount_desc">Amount ↓</option>
            <option value="timestamp_desc">Timestamp ↓</option>
          </select>
        </div>
      </div>

      {/* Transactions Table */}
      <div className="rs-panel">
        <div className="rs-panel-title">
          <span>Transaction Explorer</span>
          <span style={{ fontSize: '0.72rem', color: '#64748B', fontWeight: 600 }}>{data.total.toLocaleString()} records matching filters</span>
        </div>
        <div className="rs-table-wrap">
          <table className="rs-table">
            <thead>
              <tr>
                <th>TX ID</th>
                <th>Customer</th>
                <th>Timestamp</th>
                <th>Amount (₹)</th>
                <th>Method</th>
                <th>Location</th>
                <th>Device</th>
                <th>Risk Score</th>
                <th>AI Decision</th>
                <th>Effective</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((tx) => (
                <tr key={tx.transaction_id} style={{ background: activeTxId === tx.transaction_id ? '#EEF2FF' : undefined }}>
                  <td><code>{tx.transaction_id}</code></td>
                  <td><code>{tx.customer_id}</code></td>
                  <td><span style={{ fontSize: '0.78rem', color: '#64748B' }}>{tx.timestamp}</span></td>
                  <td><strong>₹{tx.amount?.toLocaleString()}</strong></td>
                  <td>{tx.payment_method}</td>
                  <td>{tx.location}</td>
                  <td><code>{tx.device_id}</code></td>
                  <td>
                    <span style={{ fontWeight: 700, color: tx.risk_score > 55 ? '#DC2626' : (tx.risk_score > 25 ? '#D97706' : '#059669') }}>
                      {tx.risk_score}/100
                    </span>
                  </td>
                  <td>
                    <span className={`rs-badge ${tx.model_status === 'APPROVE' ? 'rs-badge-approve' : (tx.model_status === 'REVIEW' ? 'rs-badge-review' : 'rs-badge-hold')}`}>
                      {tx.model_status}
                    </span>
                  </td>
                  <td>
                    <span className={`rs-badge ${tx.effective_status === 'APPROVE' ? 'rs-badge-approve' : (tx.effective_status === 'REVIEW' ? 'rs-badge-review' : 'rs-badge-hold')}`}>
                      {tx.effective_status}
                    </span>
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <div style={{ display: 'inline-flex', gap: 4 }}>
                      <button className="rs-btn rs-btn-outline rs-btn-sm" onClick={() => loadDetail(tx.transaction_id)}>
                        Inspect
                      </button>
                      {!isViewer && (
                        <button className="rs-btn rs-btn-secondary rs-btn-sm" onClick={() => { setActiveTxId(tx.transaction_id); setActiveNav('Investigation'); }}>
                          Investigate
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 10 }}>
          <div style={{ fontSize: '0.78rem', color: '#64748B' }}>
            Page <strong>{data.page}</strong> of <strong>{data.total_pages}</strong> ({data.total} filtered)
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <button className="rs-btn rs-btn-outline rs-btn-sm" disabled={data.page <= 1} onClick={() => setPage(page - 1)}>
              ← Previous
            </button>
            <button className="rs-btn rs-btn-outline rs-btn-sm" disabled={data.page >= data.total_pages} onClick={() => setPage(page + 1)}>
              Next →
            </button>
          </div>
        </div>
      </div>

      {/* Export & Upload Section */}
      <div style={{ display: 'grid', gridTemplateColumns: isViewer ? '1fr' : 'repeat(auto-fit, minmax(320px, 1fr))', gap: 14, marginBottom: 14 }}>
        {/* Export Card */}
        <div className="rs-panel" style={{ marginBottom: 0 }}>
          <div className="rs-panel-title">Export Data</div>
          <p style={{ fontSize: '0.8125rem', color: '#64748B', marginBottom: 10 }}>Download CSV reports of datasets or filtered transactions.</p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <a className="rs-btn rs-btn-secondary rs-btn-sm" href={api.getExportUrl('active')} download>
              <Download size={14} /> Active Dataset CSV
            </a>
            <a className="rs-btn rs-btn-outline rs-btn-sm" href={api.getExportUrl('filtered')} download>
              <Download size={14} /> Filtered Results CSV
            </a>
          </div>
        </div>

        {/* Upload Card - Analyst Only */}
        {!isViewer && (
          <div className="rs-panel" style={{ marginBottom: 0 }}>
            <div className="rs-panel-title">Import Transaction Data</div>
            <label className="rs-upload-card" style={{ display: 'block', padding: '16px 12px' }}>
              <Upload size={24} className="rs-upload-icon" style={{ margin: '0 auto 6px' }} />
              <div className="rs-upload-title" style={{ fontSize: '0.875rem' }}>Click to upload CSV dataset</div>
              <div className="rs-upload-sub" style={{ fontSize: '0.75rem' }}>Supported format: .csv (Required transaction schema)</div>
              <input type="file" accept=".csv" onChange={handleFileUpload} style={{ display: 'none' }} />
            </label>
          </div>
        )}
      </div>

      {/* Detail Drawer Modal / Panel */}
      {selectedTxId && detailData && (
        <div className="rs-panel" style={{ borderLeft: '4px solid #2563EB', marginBottom: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 800 }}>Transaction Inspector: <code>{selectedTxId}</code></h3>
            <button className="rs-btn rs-btn-outline rs-btn-sm" onClick={() => setSelectedTxId(null)}>
              <X size={14} /> Close
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14 }}>
            <div>
              <div className="rs-panel-title">Telemetry & Profile</div>
              <div style={{ fontSize: '0.8125rem', display: 'flex', flexDirection: 'column', gap: 4 }}>
                <div><strong>Customer ID:</strong> <code>{detailData.transaction.customer_id}</code></div>
                <div><strong>Amount:</strong> ₹{detailData.transaction.amount?.toLocaleString()}</div>
                <div><strong>Payment Method:</strong> {detailData.transaction.payment_method}</div>
                <div><strong>Location:</strong> {detailData.transaction.location}</div>
                <div><strong>Device ID:</strong> <code>{detailData.transaction.device_id}</code></div>
                <div><strong>Failed Attempts:</strong> {detailData.transaction.failed_attempts}</div>
                <div><strong>Account Age:</strong> {detailData.transaction.account_age_days} days</div>
              </div>
            </div>

            <div>
              <div className="rs-panel-title">ML Risk Assessment</div>
              <div className="rs-score-bar-wrap">
                <div className="rs-score-bar-row">
                  <span className="rs-score-num" style={{ color: detailData.ml_score.risk_score > 55 ? '#DC2626' : '#059669' }}>
                    {detailData.ml_score.risk_score}
                  </span>
                  <span className="rs-score-denom">/100</span>
                </div>
                <div className="rs-score-track">
                  <div className="rs-score-fill" style={{ width: `${detailData.ml_score.risk_score}%`, background: detailData.ml_score.risk_score > 55 ? '#DC2626' : '#059669' }} />
                </div>
              </div>

              <div style={{ marginTop: 8 }}>
                <span className="rs-label">Risk Signals:</span>
                <div style={{ marginTop: 3 }}>
                  {(detailData.ml_score.risk_signals || []).map((s, i) => (
                    <span key={i} className="rs-signal-chip">{s}</span>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Analyst Override Form - Analyst Only */}
          {!isViewer ? (
            <form onSubmit={handleOverride} style={{ marginTop: 12, paddingTop: 10, borderTop: '1px solid #E2E8F0' }}>
              <div className="rs-panel-title">Analyst Decision Override</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 10, alignItems: 'flex-end' }}>
                <div className="rs-field">
                  <label className="rs-label">Select Override Decision</label>
                  <select className="rs-select" value={overrideForm.decision} onChange={(e) => setOverrideForm({ ...overrideForm, decision: e.target.value })}>
                    <option value="APPROVE">APPROVE</option>
                    <option value="REVIEW">REVIEW</option>
                    <option value="HOLD">HOLD</option>
                  </select>
                </div>
                <div className="rs-field">
                  <label className="rs-label">Reason / Analyst Remark *</label>
                  <input
                    className="rs-input"
                    placeholder="e.g. Verified customer identity via phone call."
                    value={overrideForm.remark}
                    onChange={(e) => setOverrideForm({ ...overrideForm, remark: e.target.value })}
                  />
                </div>
              </div>
              <button type="submit" className="rs-btn rs-btn-primary rs-btn-sm" style={{ marginTop: 10 }}>
                Save Analyst Override
              </button>
            </form>
          ) : (
            <div style={{ marginTop: 10, paddingTop: 8, borderTop: '1px solid #E2E8F0', color: '#64748B', fontSize: '0.78rem', fontStyle: 'italic' }}>
              🔒 Read-Only Mode: Decision overrides and manual interventions are restricted to Analysts.
            </div>
          )}
        </div>
      )}

      {/* New TX Modal */}
      {newTxModal && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(10,22,40,0.6)',
          backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 16
        }}>
          <div className="rs-panel" style={{ width: 440, maxWidth: '100%', margin: 0, padding: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h3 style={{ fontWeight: 800, fontSize: '1.05rem' }}>Create Real-Time Transaction</h3>
              <button className="rs-btn rs-btn-outline rs-btn-sm" style={{ padding: '2px 6px' }} onClick={() => setNewTxModal(false)}><X size={15} /></button>
            </div>
            <form onSubmit={handleCreateTx} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div className="rs-field">
                <label className="rs-label">Transaction ID</label>
                <input className="rs-input" placeholder="Transaction ID" value={newTx.transaction_id} onChange={(e) => setNewTx({ ...newTx, transaction_id: e.target.value })} required />
              </div>
              <div className="rs-field">
                <label className="rs-label">Customer ID</label>
                <input className="rs-input" placeholder="Customer ID" value={newTx.customer_id} onChange={(e) => setNewTx({ ...newTx, customer_id: e.target.value })} required />
              </div>
              <div className="rs-field">
                <label className="rs-label">Amount (₹)</label>
                <input className="rs-input" type="number" placeholder="Amount (₹)" value={newTx.amount} onChange={(e) => setNewTx({ ...newTx, amount: parseFloat(e.target.value) })} required />
              </div>
              <div className="rs-field">
                <label className="rs-label">Payment Rail</label>
                <select className="rs-select" value={newTx.payment_method} onChange={(e) => setNewTx({ ...newTx, payment_method: e.target.value })}>
                  <option value="UPI">UPI</option>
                  <option value="Credit Card">Credit Card</option>
                  <option value="Netbanking">Netbanking</option>
                  <option value="Debit Card">Debit Card</option>
                </select>
              </div>
              <div className="rs-field">
                <label className="rs-label">Device ID</label>
                <input className="rs-input" placeholder="Device ID" value={newTx.device_id} onChange={(e) => setNewTx({ ...newTx, device_id: e.target.value })} />
              </div>
              <div className="rs-field">
                <label className="rs-label">Location</label>
                <input className="rs-input" placeholder="Location" value={newTx.location} onChange={(e) => setNewTx({ ...newTx, location: e.target.value })} />
              </div>
              <button type="submit" className="rs-btn rs-btn-primary" style={{ marginTop: 6 }}>
                Analyze & Score Transaction
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────────────
// VIEW 3: INVESTIGATION
// ─────────────────────────────────────────────────────────────────────────────
function InvestigationView({ showToast, activeTxId, setActiveTxId, handleRecordDecision }) {
  const [txId, setTxId] = useState(activeTxId || 'TX1001');
  const [reasonInput, setReasonInput] = useState('');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);

  useEffect(() => {
    if (activeTxId) {
      setTxId(activeTxId);
      handleRunInvestigation(activeTxId);
    }
  }, [activeTxId]);

  const handleRunInvestigation = async (targetId) => {
    const idToUse = targetId || txId;
    if (!idToUse) return;
    setRunning(true);
    setErrorMsg(null);
    try {
      const res = await api.runInvestigation(idToUse);
      setResult(res);
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || "Investigation failed to execute.");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div>
      <div className="rs-page-hero">
        <h1 className="rs-page-title">AI Agent Investigation Workbench</h1>
        <p className="rs-page-sub">Autonomous risk analysis, customer/device telemetry, and grounded investigation report</p>
      </div>

      <div className="rs-panel" style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ flex: 1, display: 'flex', gap: 8, alignItems: 'center', minWidth: 260 }}>
          <label className="rs-label" style={{ whiteSpace: 'nowrap' }}>Target Transaction:</label>
          <input
            className="rs-input"
            style={{ width: 260 }}
            placeholder="Enter Transaction ID (e.g. TX1001)..."
            value={txId}
            onChange={(e) => setTxId(e.target.value)}
          />
        </div>
        <button className="rs-btn rs-btn-primary" onClick={() => handleRunInvestigation(txId)} disabled={running}>
          {running ? <RefreshCw className="spin" size={15} /> : <Play size={15} />}
          {running ? 'Running Autonomous AI Investigation...' : 'Run AI Agent Investigation'}
        </button>
      </div>

      {errorMsg && (
        <div style={{ background: '#FEE2E2', border: '1px solid #FCA5A5', color: '#991B1B', padding: '10px 14px', borderRadius: 6, marginBottom: 14, fontSize: '0.82rem' }}>
          <strong>Investigation Error:</strong> {errorMsg}
        </div>
      )}

      {result && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* DECISION SUMMARY */}
          <div className="rs-panel" style={{ borderLeft: '4px solid #2563EB', background: '#F8FAFC', marginBottom: 0 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <div className="rs-panel-title" style={{ margin: 0, paddingBottom: 0, borderBottom: 'none' }}>DECISION SUMMARY</div>
              <div style={{ fontSize: '0.8125rem', color: '#475569', fontWeight: 600 }}>
                Target TX: <code>{result.transaction?.transaction_id}</code>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 10, marginBottom: 10, background: '#FFFFFF', padding: 12, borderRadius: 6, border: '1px solid #E2E8F0' }}>
              <div>
                <div style={{ fontSize: '0.6875rem', color: '#64748B', fontWeight: 700, textTransform: 'uppercase' }}>Risk Score</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 800, color: (result.transaction?.risk_score || result.ml_score?.risk_score || 0) > 55 ? '#DC2626' : '#059669', marginTop: 2 }}>
                  {result.transaction?.risk_score ?? result.ml_score?.risk_score ?? 0} / 100
                </div>
              </div>

              <div>
                <div style={{ fontSize: '0.6875rem', color: '#64748B', fontWeight: 700, textTransform: 'uppercase', marginBottom: 4 }}>AI Recommendation</div>
                <span className={`rs-badge ${(result.transaction?.ai_decision || result.recommendation) === 'APPROVE' ? 'rs-badge-approve' : ((result.transaction?.ai_decision || result.recommendation) === 'REVIEW' ? 'rs-badge-review' : 'rs-badge-hold')}`}>
                  {result.transaction?.ai_decision || result.recommendation || 'REVIEW'}
                </span>
              </div>

              <div>
                <div style={{ fontSize: '0.6875rem', color: '#64748B', fontWeight: 700, textTransform: 'uppercase', marginBottom: 4 }}>Analyst Decision</div>
                <span className={`rs-badge ${result.transaction?.analyst_decision === 'HOLD' ? 'rs-badge-hold' : (result.transaction?.analyst_decision === 'REVIEW' ? 'rs-badge-review' : (result.transaction?.analyst_decision === 'APPROVE' ? 'rs-badge-approve' : 'rs-badge-neutral'))}`}>
                  {result.transaction?.analyst_decision || 'Not set'}
                </span>
              </div>

              <div>
                <div style={{ fontSize: '0.6875rem', color: '#64748B', fontWeight: 700, textTransform: 'uppercase' }}>Analyst Override</div>
                <div style={{ fontSize: '1rem', fontWeight: 800, color: result.transaction?.analyst_override ? '#2563EB' : '#64748B', marginTop: 2 }}>
                  {result.transaction?.analyst_override ? 'YES' : 'NO'}
                </div>
              </div>

              <div>
                <div style={{ fontSize: '0.6875rem', color: '#64748B', fontWeight: 700, textTransform: 'uppercase', marginBottom: 4 }}>Effective Status</div>
                <span className={`rs-badge ${result.transaction?.effective_status === 'HOLD' ? 'rs-badge-hold' : (result.transaction?.effective_status === 'REVIEW' ? 'rs-badge-review' : 'rs-badge-approve')}`} style={{ fontWeight: 800 }}>
                  {result.transaction?.effective_status || 'APPROVE'}
                </span>
              </div>
            </div>

            <div style={{ padding: '8px 12px', background: '#FFFFFF', borderRadius: 6, marginBottom: 10, fontSize: '0.8125rem', border: '1px solid #E2E8F0' }}>
              <span style={{ fontWeight: 700, color: '#475569', textTransform: 'uppercase', fontSize: '0.6875rem', display: 'block', marginBottom: 2 }}>Analyst Reason / Remark:</span>
              <span style={{ color: result.transaction?.analyst_reason ? '#0F172A' : '#64748B', fontStyle: result.transaction?.analyst_reason ? 'normal' : 'italic', fontWeight: result.transaction?.analyst_reason ? 600 : 400 }}>
                {result.transaction?.analyst_reason || 'No analyst reason recorded.'}
              </span>
            </div>

            {/* Direct Analyst Decision & Optional Reason Control */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, paddingTop: 10, borderTop: '1px solid #CBD5E1', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 240 }}>
                <label style={{ fontSize: '0.78rem', fontWeight: 700, color: '#1E293B', whiteSpace: 'nowrap' }}>Reason:</label>
                <input
                  className="rs-input"
                  style={{ fontSize: '0.78rem', height: 30 }}
                  placeholder="Enter analyst remark or override reason..."
                  value={reasonInput}
                  onChange={(e) => setReasonInput(e.target.value)}
                />
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#1E293B', textTransform: 'uppercase' }}>Set Decision:</span>
                <div style={{ display: 'flex', gap: 6 }}>
                  {['HOLD', 'REVIEW', 'APPROVE'].map((st) => (
                    <button
                      key={st}
                      className={`rs-btn ${result.transaction?.effective_status === st ? 'rs-btn-primary' : 'rs-btn-outline'} rs-btn-sm`}
                      onClick={async () => {
                        await handleRecordDecision(result.transaction?.transaction_id, st, reasonInput);
                        setReasonInput('');
                        handleRunInvestigation(result.transaction?.transaction_id);
                      }}
                    >
                      {st}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* TRANSACTION DETAILS & RISK ANALYSIS */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 14 }}>
            <div className="rs-panel" style={{ marginBottom: 0 }}>
              <div className="rs-panel-title">TRANSACTION DETAILS</div>
              <table className="rs-table">
                <tbody>
                  <tr><td><strong>Transaction ID</strong></td><td><code>{result.transaction?.transaction_id}</code></td></tr>
                  <tr><td><strong>Customer ID</strong></td><td><code>{result.transaction?.customer_id}</code></td></tr>
                  <tr><td><strong>Amount</strong></td><td>₹{result.transaction?.amount?.toLocaleString()}</td></tr>
                  <tr><td><strong>Payment Method</strong></td><td>{result.transaction?.payment_method}</td></tr>
                  <tr><td><strong>Location</strong></td><td>{result.transaction?.location}</td></tr>
                  <tr><td><strong>Device ID</strong></td><td><code>{result.transaction?.device_id}</code></td></tr>
                  <tr><td><strong>Timestamp</strong></td><td>{result.transaction?.timestamp}</td></tr>
                </tbody>
              </table>
            </div>

            <div className="rs-panel" style={{ marginBottom: 0 }}>
              <div className="rs-panel-title">RISK ANALYSIS</div>
              <div style={{ marginBottom: 10 }}>
                <span className="rs-label">Identified Risk Signals:</span>
                <div style={{ marginTop: 4 }}>
                  {(result.ml_score?.risk_signals || []).map((sig, idx) => (
                    <span key={idx} className="rs-signal-chip">{sig}</span>
                  ))}
                </div>
              </div>
              <table className="rs-table">
                <tbody>
                  <tr><td><strong>Risk Score</strong></td><td><strong>{result.transaction?.risk_score ?? result.ml_score?.risk_score ?? 0} / 100</strong></td></tr>
                  <tr><td><strong>Fraud Probability</strong></td><td>{(result.ml_score?.fraud_probability * 100)?.toFixed(1)}%</td></tr>
                  <tr><td><strong>Account Age</strong></td><td>{result.transaction?.account_age_days} days</td></tr>
                  <tr><td><strong>Failed Attempts</strong></td><td>{result.transaction?.failed_attempts}</td></tr>
                  <tr><td><strong>Velocity (Last 5m)</strong></td><td>{result.velocity?.tx_last_5min || 1} tx(s)</td></tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* CUSTOMER & DEVICE HISTORY */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 14 }}>
            <div className="rs-panel" style={{ marginBottom: 0 }}>
              <div className="rs-panel-title">
                <span>CUSTOMER HISTORY ({result.customer_history?.length || 0})</span>
                <code>{result.transaction?.customer_id}</code>
              </div>
              {result.customer_history && result.customer_history.length > 0 ? (
                <div className="rs-table-wrap">
                  <table className="rs-table">
                    <thead>
                      <tr><th>TX ID</th><th>Amount (₹)</th><th>Method</th><th>Status</th><th>Timestamp</th></tr>
                    </thead>
                    <tbody>
                      {result.customer_history.slice(0, 8).map((h) => (
                        <tr key={h.transaction_id}>
                          <td><code>{h.transaction_id}</code></td>
                          <td>₹{h.amount?.toLocaleString()}</td>
                          <td>{h.payment_method}</td>
                          <td>
                            <span className={`rs-badge ${h.effective_status === 'HOLD' ? 'rs-badge-hold' : (h.effective_status === 'REVIEW' ? 'rs-badge-review' : 'rs-badge-approve')}`}>
                              {h.effective_status || 'APPROVE'}
                            </span>
                          </td>
                          <td style={{ fontSize: '0.75rem', color: '#64748B' }}>{h.timestamp}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div style={{ padding: '12px', color: '#64748B', fontSize: '0.8125rem', background: '#F8FAFC', borderRadius: 6, margin: '4px 0' }}>
                  No previous transactions found for customer <code>{result.transaction?.customer_id}</code> in the active dataset.
                </div>
              )}
            </div>

            <div className="rs-panel" style={{ marginBottom: 0 }}>
              <div className="rs-panel-title">
                <span>DEVICE HISTORY ({result.device_history?.length || 0})</span>
                <code>{result.transaction?.device_id}</code>
              </div>
              {result.device_history && result.device_history.length > 0 ? (
                <div className="rs-table-wrap">
                  <table className="rs-table">
                    <thead>
                      <tr><th>TX ID</th><th>Customer</th><th>Amount (₹)</th><th>Location</th><th>Status</th></tr>
                    </thead>
                    <tbody>
                      {result.device_history.slice(0, 8).map((d) => (
                        <tr key={d.transaction_id}>
                          <td><code>{d.transaction_id}</code></td>
                          <td><code>{d.customer_id}</code></td>
                          <td>₹{d.amount?.toLocaleString()}</td>
                          <td>{d.location}</td>
                          <td>
                            <span className={`rs-badge ${d.effective_status === 'HOLD' ? 'rs-badge-hold' : (d.effective_status === 'REVIEW' ? 'rs-badge-review' : 'rs-badge-approve')}`}>
                              {d.effective_status || 'APPROVE'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div style={{ padding: '12px', color: '#64748B', fontSize: '0.8125rem', background: '#F8FAFC', borderRadius: 6, margin: '4px 0' }}>
                  No previous transactions found for device <code>{result.transaction?.device_id}</code> in the active dataset.
                </div>
              )}
            </div>
          </div>

          {/* INVESTIGATION FINDINGS */}
          <div className="rs-panel" style={{ marginBottom: 0 }}>
            <div className="rs-panel-title">INVESTIGATION FINDINGS</div>
            <div style={{ color: '#0F172A', fontSize: '0.85rem' }}>
              {renderMarkdown(result.final_explanation)}
            </div>
            <div style={{ marginTop: 12, paddingTop: 10, borderTop: '1px solid #E2E8F0' }}>
              <div style={{ fontSize: '0.72rem', color: '#64748B', fontWeight: 700, textTransform: 'uppercase', marginBottom: 6 }}>
                Evidence / Sources Used:
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {(result.sources || ["SQLite Database Telemetry", "XGBoost ML Engine"]).map((src, sIdx) => (
                  <span key={sIdx} className="rs-chip-btn" style={{ cursor: 'default', background: '#F1F5F9', color: '#334155', padding: '2px 8px', fontSize: '0.72rem' }}>
                    • {src}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────────────
// VIEW: ADMIN COMMUNICATION & SUPPORT
// ─────────────────────────────────────────────────────────────────────────────
function AdminCommunicationView({ showToast }) {

  const [conversations, setConversations] = useState([]);
  const [selectedAnalystId, setSelectedAnalystId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputMsg, setInputMsg] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);

  const fetchConversations = async () => {
    try {
      const res = await api.getAdminConversations();
      const list = res.conversations || [];
      setConversations(list);
      if (list.length > 0 && !selectedAnalystId) {
        setSelectedAnalystId(list[0].analyst_id);
      }
    } catch (err) {
      console.error("Error fetching conversations:", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchMessages = async (analystId) => {
    if (!analystId) return;
    try {
      const res = await api.getConversationMessages(analystId);
      setMessages(res.messages || []);
    } catch (err) {
      console.error("Error fetching messages:", err);
    }
  };

  useEffect(() => {
    fetchConversations();
    const interval = setInterval(fetchConversations, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (selectedAnalystId) {
      fetchMessages(selectedAnalystId);
    }
  }, [selectedAnalystId]);

  const handleSend = async () => {
    if (!inputMsg.trim() || !selectedAnalystId) return;
    try {
      setSending(true);
      await api.sendCommunicationMessage({ analyst_id: selectedAnalystId, message: inputMsg.trim() });
      setInputMsg('');
      await fetchMessages(selectedAnalystId);
      await fetchConversations();
    } catch (err) {
      console.error("Failed to send message:", err);
      showToast("Failed to send message", "error");
    } finally {
      setSending(false);
    }
  };

  const handleResolve = async (messageId) => {
    try {
      await api.resolveApiKeyRequest(messageId);
      showToast("API Key Request marked as RESOLVED", "success");
      await fetchMessages(selectedAnalystId);
      await fetchConversations();
    } catch (err) {
      console.error("Failed to resolve request:", err);
      showToast("Failed to resolve API request", "danger");
    }
  };

  const selectedAnalyst = conversations.find(c => c.analyst_id === selectedAnalystId) || conversations[0];

  return (
    <div>
      <div className="rs-page-hero">
        <h1 className="rs-page-title">Admin ↔ Analyst Communication & Notifications</h1>
        <p className="rs-page-sub">Direct 1-to-1 support channel with Analysts and AI API configuration request management</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 16, minHeight: 560 }}>
        {/* Left Column: Analysts List */}
        <div className="rs-panel" style={{ padding: 12 }}>
          <div className="rs-panel-title" style={{ fontSize: '0.9rem', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Users size={16} /> Analyst Channels
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {conversations.length === 0 ? (
              <div style={{ fontSize: '0.8rem', color: '#64748B', padding: 10 }}>No approved Analysts available.</div>
            ) : (
              conversations.map((c) => {
                const isSelected = c.analyst_id === selectedAnalystId;
                return (
                  <div
                    key={c.analyst_id}
                    onClick={() => setSelectedAnalystId(c.analyst_id)}
                    style={{
                      padding: '10px 12px',
                      borderRadius: 8,
                      cursor: 'pointer',
                      background: isSelected ? '#EFF6FF' : '#FFFFFF',
                      border: `1px solid ${isSelected ? '#3B82F6' : '#E2E8F0'}`,
                      borderLeft: `4px solid ${isSelected ? '#2563EB' : 'transparent'}`,
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                      <span style={{ fontWeight: 700, fontSize: '0.85rem', color: isSelected ? '#1E40AF' : '#0F172A' }}>
                        {c.analyst_full_name}
                      </span>
                      <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#10B981' }} />
                    </div>

                    <div style={{ fontSize: '0.72rem', color: '#64748B', display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                      <span>@{c.analyst_username}</span>
                      {c.unread_count > 0 && (
                        <span style={{ background: '#DC2626', color: '#FFFFFF', fontSize: '0.68rem', fontWeight: 800, padding: '1px 6px', borderRadius: 10 }}>
                          {c.unread_count} unread
                        </span>
                      )}
                      {c.has_open_api_request && (
                        <span style={{ background: '#F59E0B', color: '#FFFFFF', fontSize: '0.68rem', fontWeight: 800, padding: '1px 6px', borderRadius: 4 }}>
                          ⚠️ API Request
                        </span>
                      )}
                    </div>

                    {c.latest_message && (
                      <div style={{ fontSize: '0.73rem', color: '#64748B', marginTop: 6, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        <strong>{c.latest_message.sender_role === 'admin' ? 'You' : c.analyst_username}:</strong> {c.latest_message.message.slice(0, 32)}...
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: 1-to-1 Thread */}
        <div className="rs-panel" style={{ display: 'flex', flexDirection: 'column', height: 580, padding: 0 }}>
          {selectedAnalyst ? (
            <>
              {/* Header */}
              <div style={{ padding: '12px 16px', borderBottom: '1px solid #E2E8F0', background: '#F8FAFC', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div style={{ fontWeight: 800, fontSize: '0.95rem', color: '#0F172A' }}>
                    Conversation with {selectedAnalyst.analyst_full_name}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#64748B' }}>
                    @{selectedAnalyst.analyst_username} • Private Channel
                  </div>
                </div>
                {selectedAnalyst.has_open_api_request && (
                  <span className="rs-badge rs-badge-review" style={{ background: '#FEF3C7', color: '#B45309', border: '1px solid #FCD34D' }}>
                    ⚠️ Open API Key Request
                  </span>
                )}
              </div>

              {/* Messages Container */}
              <div style={{ flex: 1, padding: 16, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12, background: '#FAFAFA' }}>
                {messages.length === 0 ? (
                  <div style={{ textAlign: 'center', color: '#94A3B8', marginTop: 40, fontSize: '0.85rem' }}>
                    No messages in this conversation yet. Send a message to initiate contact.
                  </div>
                ) : (
                  messages.map((m) => {
                    const isAdmin = m.sender_role === 'admin';
                    const isApiReq = m.msg_type === 'API_KEY_REQUEST';

                    if (isApiReq) {
                      return (
                        <div
                          key={m.message_id}
                          style={{
                            background: m.status === 'RESOLVED' ? '#ECFDF5' : '#FFFBEB',
                            border: `1px solid ${m.status === 'RESOLVED' ? '#6EE7B7' : '#FCD34D'}`,
                            borderRadius: 10,
                            padding: 14,
                            margin: '6px 0'
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                            <div style={{ fontWeight: 800, fontSize: '0.88rem', color: m.status === 'RESOLVED' ? '#047857' : '#B45309', display: 'flex', alignItems: 'center', gap: 6 }}>
                              <AlertTriangle size={16} /> AI Configuration Request
                            </div>
                            <span
                              style={{
                                fontSize: '0.72rem',
                                fontWeight: 800,
                                padding: '2px 8px',
                                borderRadius: 4,
                                background: m.status === 'RESOLVED' ? '#10B981' : '#F59E0B',
                                color: '#FFFFFF'
                              }}
                            >
                              {m.status}
                            </span>
                          </div>

                          <div style={{ fontSize: '0.82rem', color: '#1E293B', whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>
                            {m.message}
                          </div>

                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 10, paddingTop: 8, borderTop: '1px solid rgba(0,0,0,0.06)' }}>
                            <span style={{ fontSize: '0.72rem', color: '#64748B' }}>{m.created_at}</span>
                            {m.status === 'OPEN' && (
                              <button
                                className="rs-btn rs-btn-primary"
                                style={{ padding: '4px 12px', fontSize: '0.75rem', fontWeight: 700 }}
                                onClick={() => handleResolve(m.message_id)}
                              >
                                <CheckCircle size={14} /> Mark Resolved
                              </button>
                            )}
                            {m.status === 'RESOLVED' && (
                              <span style={{ fontSize: '0.75rem', color: '#047857', fontWeight: 700 }}>
                                Resolved at {m.resolved_at}
                              </span>
                            )}
                          </div>
                        </div>
                      );
                    }

                    return (
                      <div
                        key={m.message_id}
                        style={{
                          alignSelf: isAdmin ? 'flex-end' : 'flex-start',
                          maxWidth: '75%'
                        }}
                      >
                        <div style={{ fontSize: '0.7rem', color: '#64748B', marginBottom: 2, textAlign: isAdmin ? 'right' : 'left' }}>
                          {isAdmin ? 'You (Admin)' : m.sender_username} • {m.created_at}
                        </div>
                        <div
                          style={{
                            background: isAdmin ? '#2563EB' : '#FFFFFF',
                            color: isAdmin ? '#FFFFFF' : '#0F172A',
                            padding: '10px 14px',
                            borderRadius: isAdmin ? '12px 12px 2px 12px' : '12px 12px 12px 2px',
                            border: isAdmin ? 'none' : '1px solid #E2E8F0',
                            fontSize: '0.85rem',
                            lineHeight: 1.5,
                            boxShadow: '0 1px 2px rgba(0,0,0,0.04)'
                          }}
                        >
                          {m.message}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>

              {/* Composer */}
              <div style={{ padding: 12, borderTop: '1px solid #E2E8F0', background: '#FFFFFF', display: 'flex', gap: 10 }}>
                <input
                  className="rs-input"
                  placeholder={`Type a message to ${selectedAnalyst.analyst_full_name}...`}
                  value={inputMsg}
                  onChange={(e) => setInputMsg(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                />
                <button className="rs-btn rs-btn-primary" onClick={handleSend} disabled={sending || !inputMsg.trim()}>
                  <Send size={16} /> Send
                </button>
              </div>
            </>
          ) : (
            <div style={{ padding: 40, textAlign: 'center', color: '#64748B' }}>Select an analyst channel to view conversation.</div>
          )}
        </div>
      </div>
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────────────
// VIEW: ANALYST COMMUNICATION & SUPPORT
// ─────────────────────────────────────────────────────────────────────────────
function AnalystCommunicationView({ showToast, systemStatus }) {
  const [messages, setMessages] = useState([]);
  const [inputMsg, setInputMsg] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [notifying, setNotifying] = useState(false);

  const fetchMessages = async () => {
    try {
      const res = await api.getConversationMessages();
      setMessages(res.messages || []);
    } catch (err) {
      console.error("Error fetching conversation messages:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMessages();
    const interval = setInterval(fetchMessages, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleSend = async () => {
    if (!inputMsg.trim()) return;
    try {
      setSending(true);
      await api.sendCommunicationMessage({ message: inputMsg.trim() });
      setInputMsg('');
      await fetchMessages();
    } catch (err) {
      console.error("Failed to send message:", err);
      showToast("Unable to send message. Please try again.", "danger");
    } finally {
      setSending(false);
    }
  };

  const handleNotifyApiKey = async () => {
    try {
      setNotifying(true);
      const res = await api.notifyApiKeyRequest();
      if (res.status === 'success') {
        showToast("API-key request sent to Admin", "success");
      } else if (res.status === 'duplicate') {
        showToast("Admin has already been notified about this issue.", "info");
      }
      await fetchMessages();
    } catch (err) {
      console.error("Failed to notify admin:", err);
      showToast("Failed to send notification to Admin", "danger");
    } finally {
      setNotifying(false);
    }
  };

  return (
    <div>
      <div className="rs-page-hero">
        <h1 className="rs-page-title">Admin Support & System Notifications</h1>
        <p className="rs-page-sub">Direct private communication channel with System Administrator</p>
      </div>

      <div className="rs-panel" style={{ display: 'flex', flexDirection: 'column', height: 600, padding: 0 }}>
        {/* Header */}
        <div style={{ padding: '12px 16px', borderBottom: '1px solid #E2E8F0', background: '#F8FAFC', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontWeight: 800, fontSize: '0.95rem', color: '#0F172A' }}>
              System Administrator Support
            </div>
            <div style={{ fontSize: '0.75rem', color: '#64748B' }}>
              Private 1-to-1 Support & API Key Configuration Channel
            </div>
          </div>

          <button
            className="rs-btn"
            style={{
              background: '#D97706',
              color: '#FFFFFF',
              border: 'none',
              fontWeight: 700,
              fontSize: '0.78rem',
              padding: '6px 12px',
              display: 'flex',
              alignItems: 'center',
              gap: 6
            }}
            onClick={handleNotifyApiKey}
            disabled={notifying}
          >
            <Send size={14} /> Notify Admin About API Key
          </button>
        </div>

        {/* Messages Container */}
        <div style={{ flex: 1, padding: 16, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12, background: '#FAFAFA' }}>
          {messages.length === 0 ? (
            <div style={{ textAlign: 'center', color: '#94A3B8', marginTop: 40, fontSize: '0.85rem' }}>
              No messages yet. Use the input below or click 'Notify Admin About API Key' to send a request.
            </div>
          ) : (
            messages.map((m) => {
              const isAnalyst = m.sender_role === 'analyst';
              const isApiReq = m.msg_type === 'API_KEY_REQUEST';

              if (isApiReq) {
                return (
                  <div
                    key={m.message_id}
                    style={{
                      background: m.status === 'RESOLVED' ? '#ECFDF5' : '#FFFBEB',
                      border: `1px solid ${m.status === 'RESOLVED' ? '#6EE7B7' : '#FCD34D'}`,
                      borderRadius: 10,
                      padding: 14,
                      margin: '6px 0',
                      alignSelf: 'center',
                      width: '90%'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                      <div style={{ fontWeight: 800, fontSize: '0.88rem', color: m.status === 'RESOLVED' ? '#047857' : '#B45309', display: 'flex', alignItems: 'center', gap: 6 }}>
                        <AlertTriangle size={16} /> AI Configuration Request
                      </div>
                      <span
                        style={{
                          fontSize: '0.72rem',
                          fontWeight: 800,
                          padding: '2px 8px',
                          borderRadius: 4,
                          background: m.status === 'RESOLVED' ? '#10B981' : '#F59E0B',
                          color: '#FFFFFF'
                        }}
                      >
                        {m.status === 'RESOLVED' ? 'RESOLVED' : 'PENDING ADMIN'}
                      </span>
                    </div>

                    <div style={{ fontSize: '0.82rem', color: '#1E293B', whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>
                      {m.message}
                    </div>

                    <div style={{ marginTop: 8, fontSize: '0.75rem', color: m.status === 'RESOLVED' ? '#047857' : '#B45309', fontWeight: 600 }}>
                      {m.status === 'RESOLVED' ? '✓ Your API configuration request has been resolved by Admin.' : '⏳ Request submitted. Waiting for System Administrator.'}
                    </div>
                  </div>
                );
              }

              return (
                <div
                  key={m.message_id}
                  style={{
                    alignSelf: isAnalyst ? 'flex-end' : 'flex-start',
                    maxWidth: '75%'
                  }}
                >
                  <div style={{ fontSize: '0.7rem', color: '#64748B', marginBottom: 2, textAlign: isAnalyst ? 'right' : 'left' }}>
                    {isAnalyst ? 'You' : 'System Administrator'} • {m.created_at}
                  </div>
                  <div
                    style={{
                      background: isAnalyst ? '#2563EB' : '#FFFFFF',
                      color: isAnalyst ? '#FFFFFF' : '#0F172A',
                      padding: '10px 14px',
                      borderRadius: isAnalyst ? '12px 12px 2px 12px' : '12px 12px 12px 2px',
                      border: isAnalyst ? 'none' : '1px solid #E2E8F0',
                      fontSize: '0.85rem',
                      lineHeight: 1.5,
                      boxShadow: '0 1px 2px rgba(0,0,0,0.04)'
                    }}
                  >
                    {m.message}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Composer */}
        <div style={{ padding: 12, borderTop: '1px solid #E2E8F0', background: '#FFFFFF', display: 'flex', gap: 10 }}>
          <input
            className="rs-input"
            placeholder="Type a message to System Administrator..."
            value={inputMsg}
            onChange={(e) => setInputMsg(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          />
          <button className="rs-btn rs-btn-primary" onClick={handleSend} disabled={sending || !inputMsg.trim()}>
            <Send size={16} /> Send
          </button>
        </div>
      </div>
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────────────
// VIEW 4: AI COPILOT
// ─────────────────────────────────────────────────────────────────────────────
function CopilotView({ showToast, systemStatus, activeTxId, setActiveTxId, handleRecordDecision }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [txId, setTxId] = useState(activeTxId || 'TX1001');

  useEffect(() => {
    if (activeTxId) setTxId(activeTxId);
  }, [activeTxId]);

  const handleSend = async (queryText) => {
    const text = queryText || input;
    if (!text.trim()) return;

    const newMsgs = [...messages, { role: 'user', content: text }];
    setMessages(newMsgs);
    if (!queryText) setInput('');
    setLoading(true);

    try {
      const res = await api.sendCopilotMessage(text, txId);
      if (res.target_tx_id && res.target_tx_id !== txId) {
        setTxId(res.target_tx_id);
        setActiveTxId(res.target_tx_id);
      }
      setMessages([...newMsgs, { role: 'assistant', content: res.answer, sources: res.sources }]);
    } catch (err) {
      showToast("Copilot response error. Check API key in AI Configuration.", "danger");
    } finally {
      setLoading(false);
    }
  };

  const [notifyingAdmin, setNotifyingAdmin] = useState(false);
  const [notifySuccessMsg, setNotifySuccessMsg] = useState('');

  const handleNotifyAdmin = async () => {
    try {
      setNotifyingAdmin(true);
      const res = await api.notifyApiKeyRequest();
      if (res.status === 'success') {
        showToast('Admin has been notified.', 'success');
        setNotifySuccessMsg('Admin has been notified.');
      } else if (res.status === 'duplicate') {
        showToast('Admin has already been notified about this issue.', 'info');
        setNotifySuccessMsg('Admin has already been notified about this issue.');
      }
    } catch (err) {
      console.error('Failed to notify admin:', err);
      showToast('Failed to send notification to Admin.', 'error');
    } finally {
      setNotifyingAdmin(false);
    }
  };

  return (
    <div className="rs-copilot-container">
      <div className="rs-page-hero">
        <h1 className="rs-page-title">RiskShield Copilot</h1>
        <p className="rs-page-sub">Enterprise AI assistant for payment risk investigation and policy queries</p>
      </div>

      {/* Active Context Banner & Analyst Control Bar */}
      <div className="rs-panel" style={{ padding: '12px 16px', marginBottom: 14, background: '#F8FAFC', borderLeft: '4px solid #2563EB' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <span style={{ fontSize: '0.75rem', color: '#64748B', fontWeight: 700, textTransform: 'uppercase' }}>Active Context:</span>
            <span>Target TX: <strong style={{ color: '#2563EB' }}><code>{txId}</code></strong></span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#334155', textTransform: 'uppercase' }}>Set Analyst Decision:</span>
            <div style={{ display: 'flex', gap: 6 }}>
              {['HOLD', 'REVIEW', 'APPROVE'].map((st) => (
                <button
                  key={st}
                  className="rs-btn rs-btn-outline"
                  style={{ padding: '4px 12px', fontSize: '0.78rem', fontWeight: 700 }}
                  onClick={async () => {
                    await handleRecordDecision(txId, st);
                    handleSend(`What is the current status of ${txId}?`);
                  }}
                >
                  {st}
                </button>
              ))}
            </div>
            <input
              className="rs-input"
              style={{ width: 140, padding: '4px 8px', fontSize: '0.78rem' }}
              placeholder="Change TX ID..."
              value={txId}
              onChange={(e) => { setTxId(e.target.value); setActiveTxId(e.target.value); }}
            />
            <button className="rs-btn rs-btn-outline" style={{ padding: '4px 10px', fontSize: '0.78rem' }} onClick={() => setMessages([])}>
              Clear
            </button>
          </div>
        </div>
      </div>

      {!systemStatus?.has_api_key && (
        <div style={{ background: '#FFFBEB', border: '1px solid #FCD34D', color: '#92400E', padding: '14px 16px', borderRadius: 10, marginBottom: 14, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <div style={{ fontWeight: 800, fontSize: '0.9rem', marginBottom: 2, color: '#B45309' }}>
              ⚠️ AI Copilot is currently unavailable because the LLM API key has not been configured.
            </div>
            <div style={{ fontSize: '0.8rem', color: '#78350F' }}>
              Rule-based local telemetry active. Request System Administrator to configure the API key in AI Settings.
            </div>
          </div>
          <div>
            <button
              className="rs-btn"
              style={{
                background: notifyingAdmin ? '#94A3B8' : notifySuccessMsg ? '#059669' : '#D97706',
                color: '#FFFFFF',
                border: 'none',
                fontWeight: 700,
                fontSize: '0.82rem',
                padding: '8px 14px',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                cursor: notifyingAdmin || notifySuccessMsg ? 'default' : 'pointer'
              }}
              disabled={notifyingAdmin || Boolean(notifySuccessMsg)}
              onClick={handleNotifyAdmin}
            >
              <Send size={14} />
              {notifyingAdmin ? 'Notifying Admin...' : notifySuccessMsg || 'Notify Admin'}
            </button>
          </div>
        </div>
      )}


      {/* Suggested Prompts */}
      <div className="rs-prompt-chips">
        {[
          "What is the current status?",
          "Why is this transaction risky?",
          "Show customer history",
          "Show device history",
          "Explain the risk score",
          "Put transaction on HOLD"
        ].map((prompt, i) => (
          <button key={i} className="rs-chip-btn" onClick={() => handleSend(prompt)}>
            {prompt}
          </button>
        ))}
      </div>

      {/* Chat History */}
      <div className="rs-chat-history">
        {messages.map((m, i) => (
          <div key={i} className={`rs-chat-msg ${m.role}`}>
            <div>{renderMarkdown(m.content)}</div>
            {m.sources && (
              <div style={{ fontSize: '0.7rem', color: '#64748B', marginTop: 6, paddingTop: 4, borderTop: '1px solid rgba(0,0,0,0.06)' }}>
                <strong>Sources:</strong> {m.sources.join(' · ')}
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="rs-chat-msg assistant" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <RefreshCw className="spin" size={14} /> Thinking & retrieving telemetry...
          </div>
        )}
      </div>

      {/* Chat Input */}
      <div style={{ display: 'flex', gap: 10, marginTop: 10 }}>
        <input
          className="rs-input"
          placeholder={`Ask RiskShield Copilot about ${txId}...`}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
        />
        <button className="rs-btn rs-btn-primary" onClick={() => handleSend()} disabled={loading}>
          <Send size={16} /> Send
        </button>
      </div>
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────────────
// VIEW 5: DATASET VIEW (ANALYST)
// ─────────────────────────────────────────────────────────────────────────────
function DatasetView({ datasets, systemStatus, handleDatasetSwitch, showToast }) {
  const currentDataset = systemStatus?.active_dataset || 'mixed_risk_transactions.csv';

  const datasetMeta = [
    {
      filename: 'mixed_risk_transactions.csv',
      label: 'Mixed Risk Real-World Dataset',
      desc: 'Balanced production distribution with realistic UPI, Card, and Netbanking traffic containing standard anomaly distributions.',
      tag: 'Default Active',
      riskRatio: 'Medium (15% Flagged)',
      recommendedFor: 'General operational risk evaluation and triage testing.'
    },
    {
      filename: 'normal_transactions.csv',
      label: 'Normal Low-Risk Baseline Dataset',
      desc: 'Clean baseline dataset with low anomaly rate, standard amounts, and minimal velocity spikes.',
      tag: 'Baseline',
      riskRatio: 'Very Low (<2% Flagged)',
      recommendedFor: 'Testing false positive rates and baseline authorization throughput.'
    },
    {
      filename: 'fraud_spike_transactions.csv',
      label: 'Coordinated Attack / Fraud Spike Dataset',
      desc: 'High velocity transaction bursts, device-sharing rings, and rapid-fire payment attempts.',
      tag: 'High Stress',
      riskRatio: 'High (45% Flagged)',
      recommendedFor: 'Stress testing velocity throttles, automated holds, and CRAG investigation.'
    },
    {
      filename: 'edge_case_transactions.csv',
      label: 'Edge Case & Boundary Dataset',
      desc: 'Extreme amount variances, brand new accounts, international cards, and boundary risk scores.',
      tag: 'Edge Cases',
      riskRatio: 'Moderate (28% Flagged)',
      recommendedFor: 'Calibrating decision boundary thresholds and manual review queues.'
    },
    {
      filename: 'fraud_transactions.csv',
      label: 'High Risk / Severe Fraud Dataset',
      desc: 'Concentrated fraudulent transactions with compromised credentials and high chargeback risk.',
      tag: 'Severe Risk',
      riskRatio: 'Critical (80%+ Flagged)',
      recommendedFor: 'Evaluating recall on severe fraud patterns and automated enforcement.'
    }
  ];

  return (
    <div>
      <div className="rs-page-hero">
        <h1 className="rs-page-title">Dataset Management & Telemetry</h1>
        <p className="rs-page-sub">
          Inspect telemetry pipelines, switch active evaluation scenarios, and explore dataset schemas — Active: <strong>{systemStatus?.active_dataset_label || currentDataset}</strong>
        </p>
      </div>

      {/* Quick Switch Cards */}
      <div className="rs-panel" style={{ marginBottom: 20 }}>
        <div className="rs-panel-title">Available Evaluation Scenarios</div>
        <p style={{ fontSize: '0.85rem', color: '#64748B', marginBottom: 16 }}>
          Switching datasets immediately re-evaluates all ML risk scores, telemetry pipelines, and RAG agent memory contexts.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16 }}>
          {datasetMeta.map((ds) => {
            const isActive = currentDataset === ds.filename;
            return (
              <div
                key={ds.filename}
                style={{
                  border: isActive ? '2px solid #2563EB' : '1px solid #E2E8F0',
                  background: isActive ? '#F8FAFC' : '#FFFFFF',
                  borderRadius: 10,
                  padding: 16,
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  boxShadow: isActive ? '0 4px 12px rgba(37,99,235,0.12)' : 'none',
                  transition: 'all 0.2s ease'
                }}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                    <h3 style={{ fontSize: '0.95rem', fontWeight: 800, color: '#0F172A', margin: 0 }}>
                      {ds.label}
                    </h3>
                    <span
                      style={{
                        fontSize: '0.7rem',
                        fontWeight: 700,
                        padding: '2px 8px',
                        borderRadius: 999,
                        background: isActive ? '#DBEAFE' : '#F1F5F9',
                        color: isActive ? '#1E40AF' : '#475569'
                      }}
                    >
                      {isActive ? 'ACTIVE' : ds.tag}
                    </span>
                  </div>

                  <p style={{ fontSize: '0.82rem', color: '#475569', lineHeight: 1.5, marginBottom: 12 }}>
                    {ds.desc}
                  </p>

                  <div style={{ fontSize: '0.78rem', color: '#64748B', marginBottom: 14 }}>
                    <div><strong>Risk Profile:</strong> {ds.riskRatio}</div>
                    <div style={{ marginTop: 2 }}><strong>Target Usage:</strong> {ds.recommendedFor}</div>
                  </div>
                </div>

                <button
                  className={`rs-btn ${isActive ? 'rs-btn-primary' : 'rs-btn-outline'}`}
                  style={{ width: '100%', justifyContent: 'center', fontSize: '0.82rem' }}
                  onClick={() => handleDatasetSwitch(ds.filename)}
                  disabled={isActive}
                >
                  {isActive ? '✓ Currently Loaded' : 'Load Dataset'}
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* Schema Specification Table */}
      <div className="rs-panel">
        <div className="rs-panel-title">Transaction Dataset Schema Specification</div>
        <p style={{ fontSize: '0.85rem', color: '#64748B', marginBottom: 14 }}>
          Standardized telemetry columns ingested by the RiskShield AI risk engine:
        </p>

        <div className="rs-table-wrap">
          <table className="rs-table">
            <thead>
              <tr>
                <th>Column Name</th>
                <th>Type</th>
                <th>Description</th>
                <th>Example Value</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><code>transaction_id</code></td>
                <td>String</td>
                <td>Unique payment transaction identifier (e.g. TX1001)</td>
                <td><code>TX1001</code></td>
              </tr>
              <tr>
                <td><code>customer_id</code></td>
                <td>String</td>
                <td>Unique customer / merchant account entity ID</td>
                <td><code>C1005</code></td>
              </tr>
              <tr>
                <td><code>amount</code></td>
                <td>Float</td>
                <td>Transaction amount in INR (₹)</td>
                <td><code>₹24,500.00</code></td>
              </tr>
              <tr>
                <td><code>payment_method</code></td>
                <td>Categorical</td>
                <td>Payment rail: UPI, Credit Card, Netbanking, Debit Card</td>
                <td><code>UPI</code></td>
              </tr>
              <tr>
                <td><code>location</code></td>
                <td>String</td>
                <td>Originating geo-city or IP resolution node</td>
                <td><code>Mumbai</code></td>
              </tr>
              <tr>
                <td><code>device_id</code></td>
                <td>String</td>
                <td>Hardware / browser canvas fingerprint identifier</td>
                <td><code>DEV_9821</code></td>
              </tr>
              <tr>
                <td><code>failed_attempts</code></td>
                <td>Integer</td>
                <td>Failed authorization attempts in the last 60 minutes</td>
                <td><code>0</code></td>
              </tr>
              <tr>
                <td><code>account_age_days</code></td>
                <td>Integer</td>
                <td>Customer relationship tenure in days</td>
                <td><code>180</code></td>
              </tr>
              <tr>
                <td><code>timestamp</code></td>
                <td>DateTime</td>
                <td>ISO-8601 payment initiation timestamp</td>
                <td><code>2026-09-04 14:32:00</code></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────────────
// VIEW 6: MODELS VIEW (ANALYST)
// ─────────────────────────────────────────────────────────────────────────────
function ModelsView({ showToast }) {
  const models = [
    {
      name: 'XGBoost Gradient Boosted Trees (Primary)',
      version: 'v2.4.1-prod',
      status: 'Active (Production)',
      rocAuc: '0.984',
      precision: '92.1%',
      recall: '89.4%',
      f1Score: '0.907',
      latency: '1.8 ms',
      type: 'Tree Ensemble',
      description: 'Primary risk scoring model trained on historical payment anomalies, chargeback records, and velocity patterns.'
    },
    {
      name: 'Random Forest Ensemble Classifier',
      version: 'v1.8.0-eval',
      status: 'Secondary Benchmark',
      rocAuc: '0.962',
      precision: '89.5%',
      recall: '86.2%',
      f1Score: '0.878',
      latency: '2.4 ms',
      type: 'Bagging Ensemble',
      description: 'Robust parallel tree model used for cross-validation and non-linear feature interaction benchmarks.'
    },
    {
      name: 'Logistic Regression Calibrator',
      version: 'v1.2.0-base',
      status: 'Calibration Layer',
      rocAuc: '0.918',
      precision: '84.0%',
      recall: '79.5%',
      f1Score: '0.817',
      latency: '0.4 ms',
      type: 'Linear Probabilistic',
      description: 'Zero-latency generalized linear model utilized for probability calibration and confidence score scaling.'
    },
    {
      name: 'Heuristic Rule-Based Gatekeeper',
      version: 'v3.1.0-rules',
      status: 'Pre-Filter Rules',
      rocAuc: '0.850',
      precision: '96.5%',
      recall: '45.0%',
      f1Score: '0.614',
      latency: '0.1 ms',
      type: 'Deterministic Rules',
      description: 'Deterministic fast-path rules enforcing velocity spikes (>5 in 5m), extreme amounts (>₹1,00,000 on new accounts).'
    }
  ];

  return (
    <div>
      <div className="rs-page-hero">
        <h1 className="rs-page-title">Available Machine Learning Models</h1>
        <p className="rs-page-sub">
          Explore deployed AI risk models, evaluate accuracy telemetry, and view feature importance weights
        </p>
      </div>

      {/* Model Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16, marginBottom: 20 }}>
        {models.map((m, idx) => (
          <div key={idx} className="rs-panel" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                <div>
                  <h3 style={{ fontSize: '1rem', fontWeight: 800, color: '#0F172A', margin: 0 }}>{m.name}</h3>
                  <span style={{ fontSize: '0.75rem', color: '#64748B' }}>Version: {m.version} • {m.type}</span>
                </div>
                <span
                  style={{
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    padding: '2px 8px',
                    borderRadius: 999,
                    background: idx === 0 ? '#DCFCE7' : '#F1F5F9',
                    color: idx === 0 ? '#166534' : '#475569'
                  }}
                >
                  {m.status}
                </span>
              </div>

              <p style={{ fontSize: '0.83rem', color: '#475569', lineHeight: 1.5, margin: '10px 0 16px' }}>
                {m.description}
              </p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, background: '#F8FAFC', padding: 10, borderRadius: 8, border: '1px solid #E2E8F0', textAlign: 'center' }}>
              <div>
                <div style={{ fontSize: '0.7rem', color: '#64748B', fontWeight: 700 }}>ROC-AUC</div>
                <div style={{ fontSize: '1rem', fontWeight: 800, color: '#2563EB' }}>{m.rocAuc}</div>
              </div>
              <div>
                <div style={{ fontSize: '0.7rem', color: '#64748B', fontWeight: 700 }}>Precision</div>
                <div style={{ fontSize: '1rem', fontWeight: 800, color: '#059669' }}>{m.precision}</div>
              </div>
              <div>
                <div style={{ fontSize: '0.7rem', color: '#64748B', fontWeight: 700 }}>Latency</div>
                <div style={{ fontSize: '1rem', fontWeight: 800, color: '#0F172A' }}>{m.latency}</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Model Benchmark Table */}
      <div className="rs-panel" style={{ marginBottom: 20 }}>
        <div className="rs-panel-title">Model Performance & Accuracy Benchmarks</div>
        <div className="rs-table-wrap">
          <table className="rs-table">
            <thead>
              <tr>
                <th>Model Name</th>
                <th>Architecture</th>
                <th>Latency</th>
                <th>ROC-AUC</th>
                <th>Precision</th>
                <th>Recall</th>
                <th>F1-Score</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {models.map((m, idx) => (
                <tr key={idx}>
                  <td><strong>{m.name}</strong></td>
                  <td><code>{m.type}</code></td>
                  <td>{m.latency}</td>
                  <td><strong style={{ color: '#2563EB' }}>{m.rocAuc}</strong></td>
                  <td>{m.precision}</td>
                  <td>{m.recall}</td>
                  <td>{m.f1Score}</td>
                  <td>
                    <span className={`rs-badge ${idx === 0 ? 'rs-badge-approve' : 'rs-badge-review'}`}>
                      {m.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Feature Importance Panel */}
      <div className="rs-panel">
        <div className="rs-panel-title">Primary Model Feature Importance (XGBoost)</div>
        <p style={{ fontSize: '0.85rem', color: '#64748B', marginBottom: 14 }}>
          Relative contribution of telemetry attributes to the final fraud probability calculation:
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {[
            { feature: 'Transaction Amount (₹)', weight: 34, color: '#2563EB' },
            { feature: 'Velocity (Transactions in last 5 min)', weight: 26, color: '#4F46E5' },
            { feature: 'Failed Authentication Attempts', weight: 18, color: '#D97706' },
            { feature: 'Account Age (Tenure Days)', weight: 12, color: '#059669' },
            { feature: 'Payment Rail (UPI / Card)', weight: 6, color: '#0284C7' },
            { feature: 'Device Fingerprint Entropy', weight: 4, color: '#64748B' }
          ].map((f, i) => (
            <div key={i}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', marginBottom: 4 }}>
                <span style={{ fontWeight: 600, color: '#1E293B' }}>{f.feature}</span>
                <span style={{ fontWeight: 700, color: f.color }}>{f.weight}%</span>
              </div>
              <div style={{ height: 8, background: '#E2E8F0', borderRadius: 4, overflow: 'hidden' }}>
                <div style={{ width: `${f.weight * 2.5}%`, height: '100%', background: f.color, borderRadius: 4 }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────────────
// VIEW 6: MODEL PERFORMANCE
// ─────────────────────────────────────────────────────────────────────────────
function ModelPerformanceView({ showToast }) {
  const [data, setData] = useState(null);
  const [threshold, setThreshold] = useState(50);
  const [fpCost, setFpCost] = useState(2000);
  const [fnCost, setFnCost] = useState(35000);
  const [costSim, setCostSim] = useState(null);
  const [saving, setSaving] = useState(false);
  const saveTimeoutRef = React.useRef(null);

  const fetchModelPerf = async () => {
    try {
      const res = await api.getModelPerformance();
      setData(res);
      const activeThresh = res.threshold !== undefined ? res.threshold : 50;
      setThreshold(activeThresh);
      // Run initial cost simulation with saved threshold
      const simRes = await api.calculateCustomCost({
        fp_cost: 2000,
        fn_cost: 35000,
        sim_threshold: activeThresh,
      });
      setCostSim(simRes);
    } catch (err) {
      console.error("Failed to load model performance:", err);
    }
  };

  useEffect(() => {
    fetchModelPerf();
  }, []);

  const runSimulation = async (newThresh, newFp, newFn) => {
    const t = newThresh !== undefined ? newThresh : threshold;
    const fp = newFp !== undefined ? newFp : fpCost;
    const fn = newFn !== undefined ? newFn : fnCost;

    try {
      const res = await api.calculateCustomCost({
        fp_cost: parseFloat(fp) || 0,
        fn_cost: parseFloat(fn) || 0,
        sim_threshold: parseInt(t) || 50,
      });
      setCostSim(res);
    } catch (err) {
      console.error("Cost calculation error:", err);
    }
  };

  const handleThresholdSlider = (val) => {
    setThreshold(val);
    runSimulation(val, fpCost, fnCost);

    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    saveTimeoutRef.current = setTimeout(async () => {
      try {
        setSaving(true);
        await api.updateRiskThreshold(val);
        if (showToast) {
          showToast(`Fraud Risk Score Cutoff Threshold updated to ${val}%`, 'success');
        }
      } catch (err) {
        console.error("Failed to save threshold to backend:", err);
        const reason = err.response?.data?.detail || err.message || 'Server error';
        if (showToast) {
          showToast(`Failed to save threshold: ${reason}`, 'error');
        }
      } finally {

        setSaving(false);
      }
    }, 400);
  };

  if (!data) return <div className="rs-panel">Loading model performance & metrics...</div>;

  const { metrics, comparison, cost_impact } = data;
  const currentSim = costSim?.simulated || cost_impact;
  const baseSim = costSim?.base || cost_impact;
  const delta = costSim?.cost_delta !== undefined ? costSim.cost_delta : 0;

  return (
    <div>
      <div className="rs-page-hero">
        <h1 className="rs-page-title">ML Model Performance & Financial Cost Modeling</h1>
        <p className="rs-page-sub">Held-out test set metrics, confusion matrix, and interactive financial risk sensitivity analysis</p>
      </div>

      {/* Metrics Grid */}
      <div className="rs-kpi-grid">
        <div className="rs-kpi-card"><div className="rs-kpi-label">Accuracy</div><div className="rs-kpi-value">{(metrics.accuracy * 100).toFixed(1)}%</div></div>
        <div className="rs-kpi-card"><div className="rs-kpi-label">Precision</div><div className="rs-kpi-value">{(metrics.precision * 100).toFixed(1)}%</div></div>
        <div className="rs-kpi-card"><div className="rs-kpi-label">Recall</div><div className="rs-kpi-value">{(metrics.recall * 100).toFixed(1)}%</div></div>
        <div className="rs-kpi-card"><div className="rs-kpi-label">F1 Score</div><div className="rs-kpi-value">{metrics.f1?.toFixed(3)}</div></div>
        <div className="rs-kpi-card"><div className="rs-kpi-label">ROC-AUC</div><div className="rs-kpi-value">{metrics.roc_auc?.toFixed(3)}</div></div>
        <div className="rs-kpi-card"><div className="rs-kpi-label">PR-AUC</div><div className="rs-kpi-value">{metrics.pr_auc?.toFixed(3)}</div></div>
      </div>

      {/* Financial Cost & Threshold Sensitivity Panel */}
      <div className="rs-panel" style={{ border: '1px solid #2563EB', background: 'linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%)' }}>
        <div className="rs-panel-title" style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#1E40AF' }}>
          <Settings size={20} color="#2563EB" /> Interactive Financial Cost & Risk Threshold Simulator
        </div>

        {/* Inputs row */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16, marginBottom: 20 }}>
          <div className="rs-field">
            <label className="rs-label">Cost per False Positive (User Friction) ₹</label>
            <input
              type="number"
              className="rs-input"
              value={fpCost}
              onChange={(e) => {
                const val = e.target.value;
                setFpCost(val);
                runSimulation(threshold, val, fnCost);
              }}
              placeholder="e.g. 2000"
            />
            <span style={{ fontSize: '0.72rem', color: '#64748B' }}>Cost of customer support & manual review</span>
          </div>

          <div className="rs-field">
            <label className="rs-label">Cost per False Negative (Fraud Loss) ₹</label>
            <input
              type="number"
              className="rs-input"
              value={fnCost}
              onChange={(e) => {
                const val = e.target.value;
                setFnCost(val);
                runSimulation(threshold, fpCost, val);
              }}
              placeholder="e.g. 35000"
            />
            <span style={{ fontSize: '0.72rem', color: '#64748B' }}>Cost of uncollected chargeback & penalties</span>
          </div>
        </div>

        {/* Threshold Slider */}
        <div style={{ background: '#FFFFFF', border: '1px solid var(--rs-border)', borderRadius: 12, padding: 16, marginBottom: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <label className="rs-label" style={{ fontSize: '0.85rem' }}>
              Fraud Risk Score Cutoff Threshold: <strong>{threshold}%</strong> {saving && <span style={{ fontSize: '0.72rem', color: '#2563EB', marginLeft: 8 }}>(Saving...)</span>}
            </label>
            <span className="rs-badge rs-badge-approve">
              {threshold < 40 ? 'Lenient (Fewer False Negatives)' : threshold > 60 ? 'Strict (Fewer False Positives)' : 'Balanced Default'}
            </span>
          </div>
          <input
            type="range"
            min={10}
            max={90}
            step={5}
            value={threshold}
            onChange={(e) => {
              const val = parseInt(e.target.value);
              handleThresholdSlider(val);
            }}
            style={{ width: '100%', accentColor: '#2563EB', cursor: 'pointer' }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: '#64748B', marginTop: 4 }}>
            <span>10% (Flag More Tx)</span>
            <span>50% (Standard)</span>
            <span>90% (Strict High Risk Only)</span>
          </div>
        </div>


        {/* Financial Impact Comparison Display */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 14 }}>
          <div className="rs-kpi-card" style={{ background: '#FFFFFF', border: '1px solid #E2E8F0' }}>
            <div className="rs-kpi-label">Baseline Total Risk Cost (50%)</div>
            <div className="rs-kpi-value" style={{ fontSize: '1.4rem', color: '#475569' }}>
              ₹{baseSim.total_risk_cost?.toLocaleString()}
            </div>
            <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: 4 }}>
              FP ({costSim?.base_fp || metrics.false_positives}): ₹{baseSim.false_positive_cost?.toLocaleString()} | FN ({costSim?.base_fn || metrics.false_negatives}): ₹{baseSim.false_negative_exposure?.toLocaleString()}
            </div>
          </div>

          <div className="rs-kpi-card" style={{ background: '#EFF6FF', border: '1px solid #3B82F6' }}>
            <div className="rs-kpi-label" style={{ color: '#1D4ED8' }}>Simulated Risk Cost ({threshold}%)</div>
            <div className="rs-kpi-value" style={{ fontSize: '1.6rem', color: '#1E40AF' }}>
              ₹{currentSim.total_risk_cost?.toLocaleString()}
            </div>
            <div style={{ fontSize: '0.75rem', color: '#1E40AF', marginTop: 4 }}>
              FP ({costSim?.sim_fp ?? metrics.false_positives}): ₹{currentSim.false_positive_cost?.toLocaleString()} | FN ({costSim?.sim_fn ?? metrics.false_negatives}): ₹{currentSim.false_negative_exposure?.toLocaleString()}
            </div>
          </div>

          <div className="rs-kpi-card" style={{ background: delta <= 0 ? '#ECFDF5' : '#FEF2F2', border: `1px solid ${delta <= 0 ? '#10B981' : '#EF4444'}` }}>
            <div className="rs-kpi-label" style={{ color: delta <= 0 ? '#047857' : '#B91C1C' }}>
              {delta <= 0 ? '✓ Net Cost Savings' : '⚠️ Net Financial Increase'}
            </div>
            <div className="rs-kpi-value" style={{ fontSize: '1.5rem', color: delta <= 0 ? '#059669' : '#DC2626' }}>
              {delta <= 0 ? '-' : '+'}₹{Math.abs(delta).toLocaleString()}
            </div>
            <div style={{ fontSize: '0.75rem', color: delta <= 0 ? '#047857' : '#B91C1C', marginTop: 4 }}>
              Compared to 50% baseline threshold
            </div>
          </div>
        </div>
      </div>

      {/* Model Evaluation Comparison Table */}
      <div className="rs-panel">
        <div className="rs-panel-title">Model Evaluation Comparison</div>
        <div className="rs-table-wrap">
          <table className="rs-table">
            <thead>
              <tr>
                <th>Model</th>
                <th>Precision</th>
                <th>Recall</th>
                <th>F1 Score</th>
                <th>False Positives</th>
                <th>False Negatives</th>
              </tr>
            </thead>
            <tbody>
              {comparison.map((c, i) => (
                <tr key={i}>
                  <td><strong>{c.model}</strong></td>
                  <td>{c.precision}%</td>
                  <td>{c.recall}%</td>
                  <td>{c.f1}</td>
                  <td>{c.fp}</td>
                  <td>{c.fn}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────────────
// VIEW 7: AUDIT LOGS
// ─────────────────────────────────────────────────────────────────────────────
function AuditLogsView() {
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    api.getAuditLogs().then((r) => setLogs(r.logs || []));
  }, []);

  return (
    <div>
      <div className="rs-page-hero">
        <h1 className="rs-page-title">AI Investigation Audit Trail</h1>
        <p className="rs-page-sub">Immutable record of agent actions, tool calls, and analyst manual overrides</p>
      </div>

      <div className="rs-panel">
        <div className="rs-panel-title">Audit Logs History</div>
        <div className="rs-table-wrap">
          <table className="rs-table">
            <thead>
              <tr>
                <th>Log ID</th>
                <th>Timestamp</th>
                <th>TX ID</th>
                <th>Action</th>
                <th>Score</th>
                <th>CRAG Status</th>
                <th>Recommendation</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((l) => (
                <tr key={l.log_id}>
                  <td><code>#{l.log_id}</code></td>
                  <td>{l.timestamp}</td>
                  <td><code>{l.transaction_id}</code></td>
                  <td>{l.agent_action}</td>
                  <td>{l.risk_score}</td>
                  <td>{l.crag_result}</td>
                  <td>
                    <span className={`rs-badge ${l.recommendation === 'APPROVE' ? 'rs-badge-approve' : 'rs-badge-hold'}`}>
                      {l.recommendation}
                    </span>
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


// ─────────────────────────────────────────────────────────────────────────────
// VIEW 8: AI CONFIGURATION
// ─────────────────────────────────────────────────────────────────────────────
function AIConfigView({ showToast, fetchStatus }) {
  const [config, setConfig] = useState(null);
  const [models, setModels] = useState([]);
  const [provider, setProvider] = useState('Google Gemini');
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('');
  const [testing, setTesting] = useState(false);

  const loadConfig = async () => {
    const res = await api.getAIConfig();
    setConfig(res);
    setProvider(res.provider);
    setModel(res.model);
    loadModels(res.provider);
  };

  const loadModels = async (prov) => {
    const res = await api.getAIModels(prov);
    setModels(res.models || []);
    if (!res.models.includes(model)) {
      setModel(res.models[0] || '');
    }
  };

  useEffect(() => {
    loadConfig();
  }, []);

  const handleProviderChange = (newProv) => {
    setProvider(newProv);
    loadModels(newProv);
  };

  const handleSave = async () => {
    try {
      const res = await api.saveAIConfig({ provider, api_key: apiKey, model });
      setConfig(res);
      fetchStatus();
      showToast(`Configuration saved & verified for ${provider}`);
    } catch (err) {
      showToast(err.response?.data?.detail || "Failed to save configuration", "danger");
    }
  };

  const handleTest = async () => {
    setTesting(true);
    try {
      const res = await api.testAIConfig({ provider, api_key: apiKey, model });
      setConfig(res.config);
      fetchStatus();
      if (res.success) {
        showToast(res.message);
      } else {
        showToast(res.message, "danger");
      }
    } catch (err) {
      showToast("Connection test failed", "danger");
    } finally {
      setTesting(false);
    }
  };

  if (!config) return <div className="rs-panel">Loading configuration...</div>;

  return (
    <div>
      <div className="rs-page-hero">
        <h1 className="rs-page-title">AI & LLM Provider Configuration</h1>
        <p className="rs-page-sub">Configure Bring-Your-Own-Key (BYOK) providers and verify model connections</p>
      </div>

      <div className="rs-panel">
        <div className="rs-panel-title">Active LLM Configuration</div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
          <div>
            <label className="rs-label">LLM Provider</label>
            <select className="rs-select" value={provider} onChange={(e) => handleProviderChange(e.target.value)}>
              <option value="Google Gemini">Google Gemini</option>
              <option value="Groq">Groq</option>
              <option value="OpenAI">OpenAI</option>
              <option value="OpenRouter">OpenRouter</option>
            </select>
          </div>

          <div>
            <label className="rs-label">Model Selection</label>
            <select className="rs-select" value={model} onChange={(e) => setModel(e.target.value)}>
              {models.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>
        </div>

        <div style={{ marginBottom: 14 }}>
          <label className="rs-label">API Key (BYOK)</label>
          <input
            type="password"
            className="rs-input"
            placeholder={config.masked_key ? `Configured (${config.masked_key})` : "Enter API Key..."}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
          />
        </div>

        <div style={{ display: 'flex', gap: 10 }}>
          <button className="rs-btn rs-btn-primary" onClick={handleSave}>
            Save Configuration
          </button>
          <button className="rs-btn rs-btn-outline" onClick={handleTest} disabled={testing}>
            {testing ? <RefreshCw className="spin" size={16} /> : <Zap size={16} />}
            Test Connection
          </button>
        </div>

        {config.tech_details && (
          <div style={{ marginTop: 14, background: '#F8FAFC', padding: 10, borderRadius: 6, fontSize: '0.8rem', fontFamily: 'monospace' }}>
            {config.tech_details}
          </div>
        )}
      </div>
    </div>
  );
}


// Helper math func
function max1(val) {
  return Math.max(1, val);
}
