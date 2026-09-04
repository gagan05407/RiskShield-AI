import React, { useState, useEffect } from 'react';
import { CheckCircle2, XCircle, Clock, ShieldCheck, UserCheck, UserX, RefreshCw } from 'lucide-react';
import * as api from './api';

export default function UserApprovalView({ showToast }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);
  const [filterTab, setFilterTab] = useState('pending'); // 'pending' | 'all'

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const data = await api.getAdminUsers();
      setUsers(data.users || []);
    } catch (err) {
      showToast('Failed to load user list', 'danger');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleApprove = async (userId, username) => {
    setActionLoading(userId);
    try {
      const res = await api.approveUser(userId);
      showToast(res.message || `User '${username}' approved successfully.`);
      await fetchUsers();
    } catch (err) {
      showToast(err.response?.data?.detail || `Failed to approve user '${username}'`, 'danger');
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (userId, username) => {
    setActionLoading(userId);
    try {
      const res = await api.rejectUser(userId);
      showToast(res.message || `User '${username}' rejected.`, 'danger');
      await fetchUsers();
    } catch (err) {
      showToast(err.response?.data?.detail || `Failed to reject user '${username}'`, 'danger');
    } finally {
      setActionLoading(null);
    }
  };

  const pendingUsers = users.filter((u) => (u.status || 'PENDING_APPROVAL').toUpperCase() === 'PENDING_APPROVAL');
  const displayUsers = filterTab === 'pending' ? pendingUsers : users;

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch {
      return dateStr;
    }
  };

  return (
    <div>
      <div className="rs-page-hero">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1 className="rs-page-title">User Registration Approval & Access Control</h1>
            <p className="rs-page-sub">Review, activate, or reject Analyst and Viewer account registrations</p>
          </div>
          <button
            className="rs-btn rs-btn-secondary"
            onClick={fetchUsers}
            disabled={loading}
            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <RefreshCw size={15} className={loading ? 'rs-spin' : ''} /> Refresh List
          </button>
        </div>
      </div>

      {/* KPI Stats */}
      <div className="rs-kpi-grid">
        <div className="rs-kpi-card" style={{ borderLeft: '4px solid #D97706' }}>
          <div className="rs-kpi-label">Pending Approval</div>
          <div className="rs-kpi-value" style={{ color: '#D97706' }}>{pendingUsers.length}</div>
          <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: 4 }}>Awaiting admin activation</div>
        </div>

        <div className="rs-kpi-card" style={{ borderLeft: '4px solid #059669' }}>
          <div className="rs-kpi-label">Active Users</div>
          <div className="rs-kpi-value" style={{ color: '#059669' }}>
            {users.filter((u) => (u.status || '').toUpperCase() === 'ACTIVE').length}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: 4 }}>Authorized system accounts</div>
        </div>

        <div className="rs-kpi-card" style={{ borderLeft: '4px solid #DC2626' }}>
          <div className="rs-kpi-label">Rejected Registrations</div>
          <div className="rs-kpi-value" style={{ color: '#DC2626' }}>
            {users.filter((u) => (u.status || '').toUpperCase() === 'REJECTED').length}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: 4 }}>Declined access requests</div>
        </div>

        <div className="rs-kpi-card" style={{ borderLeft: '4px solid #2563EB' }}>
          <div className="rs-kpi-label">Total Accounts</div>
          <div className="rs-kpi-value">{users.length}</div>
          <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: 4 }}>Registered across all roles</div>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="rs-panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div className="rs-panel-title" style={{ marginBottom: 0 }}>
            {filterTab === 'pending' ? `Pending User Registrations (${pendingUsers.length})` : `All User Accounts (${users.length})`}
          </div>

          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className={`rs-chip-btn ${filterTab === 'pending' ? 'active' : ''}`}
              onClick={() => setFilterTab('pending')}
              style={{
                background: filterTab === 'pending' ? '#2563EB' : '#FFFFFF',
                color: filterTab === 'pending' ? '#FFFFFF' : '#334155',
                borderColor: filterTab === 'pending' ? '#2563EB' : '#CBD5E1',
              }}
            >
              Pending ({pendingUsers.length})
            </button>
            <button
              className={`rs-chip-btn ${filterTab === 'all' ? 'active' : ''}`}
              onClick={() => setFilterTab('all')}
              style={{
                background: filterTab === 'all' ? '#2563EB' : '#FFFFFF',
                color: filterTab === 'all' ? '#FFFFFF' : '#334155',
                borderColor: filterTab === 'all' ? '#2563EB' : '#CBD5E1',
              }}
            >
              All Users ({users.length})
            </button>
          </div>
        </div>

        {loading ? (
          <div style={{ padding: '32px 0', textAlign: 'center', color: '#64748B' }}>
            <RefreshCw size={24} className="rs-spin" style={{ margin: '0 auto 8px' }} />
            <p>Loading user accounts...</p>
          </div>
        ) : displayUsers.length === 0 ? (
          <div style={{ padding: '36px 0', textAlign: 'center', color: '#64748B', background: '#FAFBFD', borderRadius: 8 }}>
            <CheckCircle2 size={36} color="#059669" style={{ margin: '0 auto 8px' }} />
            <h4 style={{ color: '#0F172A', fontWeight: 700 }}>
              {filterTab === 'pending' ? 'No Pending User Registrations' : 'No Users Found'}
            </h4>
            <p style={{ fontSize: '0.85rem', marginTop: 4 }}>
              {filterTab === 'pending'
                ? 'All registered Analyst and Viewer accounts have been processed.'
                : 'No registered user accounts match the current filter.'}
            </p>
          </div>
        ) : (
          <div className="rs-table-wrap">
            <table className="rs-table">
              <thead>
                <tr>
                  <th>User / Name</th>
                  <th>Email Address</th>
                  <th>Requested Role</th>
                  <th>Registered Date</th>
                  <th>Status</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {displayUsers.map((u) => {
                  const status = (u.status || 'PENDING_APPROVAL').toUpperCase();
                  const isPending = status === 'PENDING_APPROVAL';
                  const isActive = status === 'ACTIVE';
                  const isRejected = status === 'REJECTED';
                  const isSelf = u.username === 'admin';

                  return (
                    <tr key={u.user_id}>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <div
                            style={{
                              width: 32,
                              height: 32,
                              borderRadius: '50%',
                              background: u.role === 'admin' ? '#1E293B' : u.role === 'analyst' ? '#2563EB' : '#64748B',
                              color: '#FFFFFF',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              fontWeight: 700,
                              fontSize: '0.8rem',
                            }}
                          >
                            {u.username.charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <div style={{ fontWeight: 700, color: '#0F172A' }}>{u.full_name || u.username}</div>
                            <div style={{ fontSize: '0.72rem', color: '#64748B' }}>@{u.username}</div>
                          </div>
                        </div>
                      </td>
                      <td>
                        <span style={{ fontSize: '0.82rem', color: '#334155' }}>{u.email}</span>
                      </td>
                      <td>
                        <span
                          className="rs-badge"
                          style={{
                            background: u.role === 'admin' ? '#F1F5F9' : u.role === 'analyst' ? '#EFF6FF' : '#F8FAFC',
                            color: u.role === 'admin' ? '#0F172A' : u.role === 'analyst' ? '#1D4ED8' : '#475569',
                            border: `1px solid ${u.role === 'admin' ? '#94A3B8' : u.role === 'analyst' ? '#93C5FD' : '#CBD5E1'}`,
                            textTransform: 'uppercase',
                            fontWeight: 700,
                            fontSize: '0.7rem',
                          }}
                        >
                          {u.role}
                        </span>
                      </td>
                      <td>
                        <span style={{ fontSize: '0.8rem', color: '#64748B' }}>{formatDate(u.created_at)}</span>
                      </td>
                      <td>
                        <span
                          className="rs-badge"
                          style={{
                            background: isActive ? '#ECFDF5' : isPending ? '#FFFBEB' : '#FEF2F2',
                            color: isActive ? '#047857' : isPending ? '#B45309' : '#B91C1C',
                            border: `1px solid ${isActive ? '#A7F3D0' : isPending ? '#FDE68A' : '#FECACA'}`,
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 4,
                            fontWeight: 700,
                            fontSize: '0.72rem',
                          }}
                        >
                          {isActive && <CheckCircle2 size={12} />}
                          {isPending && <Clock size={12} />}
                          {isRejected && <XCircle size={12} />}
                          {status}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        {isSelf ? (
                          <span style={{ fontSize: '0.75rem', color: '#94A3B8', fontStyle: 'italic' }}>System Admin</span>
                        ) : (
                          <div style={{ display: 'inline-flex', gap: 6 }}>
                            {status !== 'ACTIVE' && (
                              <button
                                className="rs-btn"
                                onClick={() => handleApprove(u.user_id, u.username)}
                                disabled={actionLoading === u.user_id}
                                style={{
                                  background: '#059669',
                                  color: '#FFFFFF',
                                  padding: '5px 12px',
                                  fontSize: '0.75rem',
                                  fontWeight: 700,
                                  borderRadius: 6,
                                  border: 'none',
                                  cursor: 'pointer',
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: 4,
                                }}
                              >
                                <UserCheck size={14} /> Approve
                              </button>
                            )}

                            {status !== 'REJECTED' && (
                              <button
                                className="rs-btn"
                                onClick={() => handleReject(u.user_id, u.username)}
                                disabled={actionLoading === u.user_id}
                                style={{
                                  background: '#DC2626',
                                  color: '#FFFFFF',
                                  padding: '5px 12px',
                                  fontSize: '0.75rem',
                                  fontWeight: 700,
                                  borderRadius: 6,
                                  border: 'none',
                                  cursor: 'pointer',
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: 4,
                                }}
                              >
                                <UserX size={14} /> Reject
                              </button>
                            )}
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
