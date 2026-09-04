import React, { useState } from 'react';
import { loginUser, registerUser } from './api';

export default function LoginModal({ onLoginSuccess }) {
  const [isRegister, setIsRegister] = useState(false);
  const [registeredSuccess, setRegisteredSuccess] = useState(false);
  const [registeredUsername, setRegisteredUsername] = useState('');
  const [registeredRole, setRegisteredRole] = useState('analyst');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [role, setRole] = useState('analyst');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const demoAccounts = [
    { username: 'admin', password: 'admin123', label: 'Admin', role: 'admin', desc: 'AI Settings, Model Performance, Audit, User Approvals' },
    { username: 'analyst', password: 'analyst123', label: 'Analyst', role: 'analyst', desc: 'Overview, Transactions, Investigation, Copilot' },
    { username: 'viewer', password: 'viewer123', label: 'Viewer', role: 'viewer', desc: 'Strictly Read-Only Transactions' },
  ];

  const handleFillDemo = (acc) => {
    setIsRegister(false);
    setRegisteredSuccess(false);
    setUsername(acc.username);
    setPassword(acc.password);
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isRegister) {
        if (!username || !email || !password) {
          setError('Please fill in all required fields.');
          setLoading(false);
          return;
        }
        await registerUser({
          username,
          email,
          password,
          full_name: fullName,
          role,
        });
        setRegisteredUsername(username);
        setRegisteredRole(role);
        setRegisteredSuccess(true);
        setPassword('');
      } else {
        if (!username || !password) {
          setError('Please enter both username and password.');
          setLoading(false);
          return;
        }
        const data = await loginUser(username, password);
        if (onLoginSuccess) onLoginSuccess(data.user);
      }
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Authentication failed. Please try again.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-modal-overlay">
      <div className="login-modal-container">
        <div className="login-header">
          <div className="login-shield-badge">🛡️</div>
          <h2>RiskShield AI</h2>
          <p className="login-subtitle">Autonomous Financial Fraud Decision Engine</p>
        </div>

        {/* Demo Credentials Box */}
        <div className="demo-credentials-card">
          <div className="demo-card-header">
            <span className="demo-icon">🔑</span>
            <strong>Active Demo Accounts (Pre-Approved)</strong>
          </div>
          <p className="demo-hint">Click any preset role below to auto-fill test credentials:</p>
          <div className="demo-buttons-grid">
            {demoAccounts.map((acc) => (
              <button
                key={acc.username}
                type="button"
                className="demo-account-btn"
                onClick={() => handleFillDemo(acc)}
                title={acc.desc}
              >
                <div className="demo-btn-title">
                  <span className="badge-role">{acc.label}</span>
                </div>
                <div className="demo-btn-creds">
                  <code>{acc.username}</code> / <code>{acc.password}</code>
                </div>
              </button>
            ))}
          </div>
        </div>

        {registeredSuccess ? (
          /* Professional Confirmation View After Registration */
          <div style={{
            background: 'rgba(15, 23, 42, 0.75)',
            border: '1px solid #1E3A5F',
            borderRadius: 10,
            padding: '24px 18px',
            textAlign: 'center',
            marginTop: 10
          }}>
            <div style={{
              width: 48,
              height: 48,
              borderRadius: '50%',
              background: 'rgba(16, 185, 129, 0.15)',
              border: '1px solid rgba(16, 185, 129, 0.4)',
              color: '#34D399',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '1.5rem',
              fontWeight: 800,
              margin: '0 auto 12px'
            }}>
              ✓
            </div>
            <h3 style={{ color: '#FFFFFF', fontSize: '1.15rem', fontWeight: 800, marginBottom: 8 }}>
              Registration Submitted
            </h3>
            <p style={{ color: '#E2E8F0', fontSize: '0.85rem', lineHeight: 1.5, marginBottom: 8 }}>
              Your <strong>{registeredRole.toUpperCase()}</strong> account (<code>{registeredUsername}</code>) has been submitted for administrator approval.
            </p>
            <p style={{ color: '#94A3B8', fontSize: '0.8rem', lineHeight: 1.5, marginBottom: 20 }}>
              You will be able to log in once an administrator approves your account.
            </p>
            <button
              type="button"
              className="auth-submit-btn"
              style={{ width: '100%' }}
              onClick={() => {
                setRegisteredSuccess(false);
                setIsRegister(false);
                setError('');
                setPassword('');
              }}
            >
              Return to Login
            </button>
          </div>
        ) : (
          <>
            {/* Tab Switcher */}
            <div className="auth-tab-group">
              <button
                type="button"
                className={`auth-tab ${!isRegister ? 'active' : ''}`}
                onClick={() => { setIsRegister(false); setError(''); }}
              >
                Sign In
              </button>
              <button
                type="button"
                className={`auth-tab ${isRegister ? 'active' : ''}`}
                onClick={() => { setIsRegister(true); setError(''); }}
              >
                Register (Requires Approval)
              </button>
            </div>

            {error && <div className="auth-error-alert">⚠️ {error}</div>}

            <form onSubmit={handleSubmit} className="auth-form">
              <div className="form-field">
                <label>Username *</label>
                <input
                  type="text"
                  placeholder="e.g. jdoe"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                />
              </div>

              {isRegister && (
                <>
                  <div className="form-field">
                    <label>Email Address *</label>
                    <input
                      type="email"
                      placeholder="analyst@riskshield.ai"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                    />
                  </div>

                  <div className="form-field">
                    <label>Full Name</label>
                    <input
                      type="text"
                      placeholder="John Doe"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                    />
                  </div>

                  <div className="form-field">
                    <label>Requested Role</label>
                    <select value={role} onChange={(e) => setRole(e.target.value)}>
                      <option value="analyst">Analyst (Overview, Transactions, Investigations, Copilot)</option>
                      <option value="viewer">Viewer (Strictly Read-Only Transactions)</option>
                    </select>
                    <span style={{ fontSize: '0.72rem', color: '#94A3B8', marginTop: 2 }}>
                      * New Analyst & Viewer accounts require Admin approval before first sign-in.
                    </span>
                  </div>
                </>
              )}

              <div className="form-field">
                <label>Password *</label>
                <input
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>

              <button type="submit" className="auth-submit-btn" disabled={loading}>
                {loading ? (
                  <span>Processing...</span>
                ) : isRegister ? (
                  'Submit Registration for Approval'
                ) : (
                  'Sign In to Dashboard →'
                )}
              </button>
            </form>
          </>
        )}

        <div className="login-footer-info">
          🔒 RBAC Enabled: Admin (System/AI), Analyst (Risk Ops), Viewer (Read-Only)
        </div>
      </div>
    </div>
  );
}
