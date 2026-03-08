import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './TenantDetails.css';

function TenantDetails({ tenantId, onClose }) {
  const [tenant, setTenant] = useState(null);
  const [stats, setStats] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [leads, setLeads] = useState([]);
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(true);
  const [sessionsPage, setSessionsPage] = useState(1);
  const [leadsPage, setLeadsPage] = useState(1);
  const [totalSessions, setTotalSessions] = useState(0);
  const [totalLeads, setTotalLeads] = useState(0);
  const [selectedSession, setSelectedSession] = useState(null);
  const [sessionMessages, setSessionMessages] = useState([]);

  useEffect(() => {
    loadTenantDetails();
    loadSessions();
    loadLeads();
  }, [tenantId]);

  useEffect(() => {
    if (activeTab === 'sessions') {
      loadSessions();
    } else if (activeTab === 'leads') {
      loadLeads();
    }
  }, [activeTab, sessionsPage, leadsPage]);

  const loadTenantDetails = async () => {
    try {
      const token = localStorage.getItem('admin_token');
      const response = await axios.get(
        `/api/v1/admin/tenants/${tenantId}/details`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setTenant(response.data.tenant);
      setStats(response.data.stats);
      setSessions(response.data.recent_sessions || []);
    } catch (error) {
      console.error('Ошибка загрузки деталей:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadSessions = async () => {
    try {
      const token = localStorage.getItem('admin_token');
      const response = await axios.get(
        `/api/v1/admin/tenants/${tenantId}/all-sessions?skip=${(sessionsPage-1)*20}&limit=20`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setSessions(response.data.sessions);
      setTotalSessions(response.data.total);
    } catch (error) {
      console.error('Ошибка загрузки сессий:', error);
    }
  };

  const loadLeads = async () => {
    try {
      const token = localStorage.getItem('admin_token');
      const response = await axios.get(
        `/api/v1/admin/tenants/${tenantId}/leads?skip=${(leadsPage-1)*20}&limit=20`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setLeads(response.data.leads);
      setTotalLeads(response.data.total);
    } catch (error) {
      console.error('Ошибка загрузки лидов:', error);
    }
  };

  const loadSessionMessages = async (sessionId) => {
    try {
      const token = localStorage.getItem('admin_token');
      const response = await axios.get(
        `/api/v1/admin/tenants/${tenantId}/session/${sessionId}/messages`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setSessionMessages(response.data);
      setSelectedSession(sessionId);
    } catch (error) {
      console.error('Ошибка загрузки сообщений:', error);
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString('ru-RU');
  };

  if (loading) {
    return <div className="tenant-details-loading">Загрузка...</div>;
  }

  return (
    <div className="tenant-details-modal">
      <div className="tenant-details-content">
        <div className="tenant-details-header">
          <h2>{tenant?.company_name}</h2>
          <button onClick={onClose} className="close-btn">✕</button>
        </div>

        <div className="tenant-details-tabs">
          <button
            className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            Обзор
          </button>
          <button
            className={`tab-btn ${activeTab === 'sessions' ? 'active' : ''}`}
            onClick={() => setActiveTab('sessions')}
          >
            Все диалоги
          </button>
          <button
            className={`tab-btn ${activeTab === 'leads' ? 'active' : ''}`}
            onClick={() => setActiveTab('leads')}
          >
            Лиды
          </button>
        </div>

        <div className="tenant-details-body">
          {activeTab === 'overview' && (
            <div className="overview-tab">
              <div className="tenant-info">
                <h3>Информация о компании</h3>
                <div className="info-grid">
                  <div className="info-item">
                    <span className="info-label">ID:</span>
                    <span className="info-value">{tenant?.id}</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">Владелец:</span>
                    <span className="info-value">{tenant?.owner_email}</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">Сайт:</span>
                    <span className="info-value">
                      {tenant?.website_url ? (
                        <a href={tenant.website_url} target="_blank" rel="noopener noreferrer">
                          {tenant.website_url}
                        </a>
                      ) : 'Не указан'}
                    </span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">Статус:</span>
                    <span className={`status-badge ${tenant?.is_active ? 'active' : 'inactive'}`}>
                      {tenant?.is_active ? 'Активна' : 'Заблокирована'}
                    </span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">Баланс:</span>
                    <span className="info-value balance">{tenant?.message_balance} сообщений</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">Дата создания:</span>
                    <span className="info-value">{formatDate(tenant?.created_at)}</span>
                  </div>
                </div>
              </div>

              {stats && (
                <div className="stats-section">
                  <h3>Статистика</h3>
                  <div className="stats-grid">
                    <div className="stat-card">
                      <div className="stat-value">{stats.total_sessions}</div>
                      <div className="stat-label">Всего диалогов</div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-value">{stats.active_sessions}</div>
                      <div className="stat-label">Активных (24ч)</div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-value">{stats.total_leads}</div>
                      <div className="stat-label">Всего лидов</div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-value">{stats.total_messages}</div>
                      <div className="stat-label">Всего сообщений</div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-value">{stats.conversion_rate}%</div>
                      <div className="stat-label">Конверсия в лиды</div>
                    </div>
                  </div>
                </div>
              )}

              <div className="recent-sessions">
                <h3>Последние диалоги</h3>
                <div className="sessions-list">
                  {sessions.map(session => (
                    <div
                      key={session.id}
                      className="session-item"
                      onClick={() => {
                        setSelectedSession(session.id);
                        loadSessionMessages(session.id);
                      }}
                    >
                      <div className="session-header">
                        <span className="session-name">{session.lead_name}</span>
                        <span className="session-time">{formatDate(session.created_at)}</span>
                      </div>
                      <div className="session-contacts">
                        {session.lead_phone && <span>📞 {session.lead_phone}</span>}
                        {session.lead_email && <span>✉️ {session.lead_email}</span>}
                      </div>
                      <div className="session-preview">{session.last_message || 'Нет сообщений'}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'sessions' && (
            <div className="sessions-tab">
              <h3>Все диалоги ({totalSessions})</h3>
              <div className="sessions-list full">
                {sessions.map(session => (
                  <div
                    key={session.id}
                    className={`session-item ${selectedSession === session.id ? 'selected' : ''}`}
                    onClick={() => loadSessionMessages(session.id)}
                  >
                    <div className="session-header">
                      <span className="session-name">{session.lead_name}</span>
                      <span className="session-badge">{session.has_contacts ? '📞' : '👤'}</span>
                      <span className="session-time">{formatDate(session.created_at)}</span>
                    </div>
                    <div className="session-contacts">
                      {session.lead_phone && <span>📞 {session.lead_phone}</span>}
                      {session.lead_email && <span>✉️ {session.lead_email}</span>}
                    </div>
                    <div className="session-preview">{session.preview}</div>
                    <div className="session-meta">
                      <span>Сообщений: {session.messages_count}</span>
                    </div>
                  </div>
                ))}
              </div>

              {selectedSession && (
                <div className="session-messages">
                  <h4>Сообщения диалога</h4>
                  <button onClick={() => setSelectedSession(null)} className="close-messages">✕</button>
                  <div className="messages-list">
                    {sessionMessages.map(msg => (
                      <div key={msg.id} className={`message ${msg.is_from_lead ? 'from-lead' : 'from-bot'}`}>
                        <div className="message-sender">{msg.sender}</div>
                        <div className="message-content">{msg.content}</div>
                        <div className="message-time">{formatDate(msg.created_at)}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'leads' && (
            <div className="leads-tab">
              <h3>Лиды ({totalLeads})</h3>
              <table className="leads-table">
                <thead>
                  <tr>
                    <th>Имя</th>
                    <th>Телефон</th>
                    <th>Email</th>
                    <th>Дата</th>
                    <th>Сообщений</th>
                  </tr>
                </thead>
                <tbody>
                  {leads.map(lead => (
                    <tr key={lead.id}>
                      <td>{lead.lead_name}</td>
                      <td>{lead.lead_phone || '—'}</td>
                      <td>{lead.lead_email || '—'}</td>
                      <td>{formatDate(lead.created_at)}</td>
                      <td>{lead.messages_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default TenantDetails;