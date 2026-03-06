import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import './TenantDetailPage.css';

function TenantDetailPage() {
  const { tenantId } = useParams();
  const navigate = useNavigate();
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
  const [balanceAmount, setBalanceAmount] = useState('');
  const [showBalanceModal, setShowBalanceModal] = useState(false);
  const [balanceAction, setBalanceAction] = useState('add'); // 'add' или 'deduct'

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
        `http://localhost:8000/api/v1/admin/tenants/${tenantId}/details`,
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
        `http://localhost:8000/api/v1/admin/tenants/${tenantId}/all-sessions?skip=${(sessionsPage-1)*20}&limit=20`,
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
        `http://localhost:8000/api/v1/admin/tenants/${tenantId}/leads?skip=${(leadsPage-1)*20}&limit=20`,
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
        `http://localhost:8000/api/v1/admin/tenants/${tenantId}/session/${sessionId}/messages`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setSessionMessages(response.data);
      setSelectedSession(sessionId);
    } catch (error) {
      console.error('Ошибка загрузки сообщений:', error);
    }
  };

  const toggleTenant = async () => {
    try {
      const token = localStorage.getItem('admin_token');
      await axios.post(
        `http://localhost:8000/api/v1/admin/tenants/${tenantId}/toggle`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      loadTenantDetails();
    } catch (error) {
      alert('Ошибка: ' + (error.response?.data?.detail || error.message));
    }
  };

  const handleBalanceAction = async () => {
    if (!balanceAmount || isNaN(balanceAmount) || parseInt(balanceAmount) <= 0) {
      alert('Введите корректное число');
      return;
    }

    try {
      const token = localStorage.getItem('admin_token');
      const endpoint = balanceAction === 'add'
        ? `http://localhost:8000/api/v1/admin/tenants/${tenantId}/balance?amount=${balanceAmount}`
        : `http://localhost:8000/api/v1/admin/tenants/${tenantId}/deduct-balance?amount=${balanceAmount}`;

      await axios.post(endpoint, {}, { headers: { Authorization: `Bearer ${token}` } });
      loadTenantDetails();
      setShowBalanceModal(false);
      setBalanceAmount('');
    } catch (error) {
      alert('Ошибка: ' + (error.response?.data?.detail || error.message));
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString('ru-RU');
  };

  const formatShortDate = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 60) {
      return `${diffMins} мин назад`;
    } else if (diffHours < 24) {
      return `${diffHours} ч назад`;
    } else if (diffDays < 7) {
      return `${diffDays} д назад`;
    } else {
      return date.toLocaleDateString('ru-RU');
    }
  };

  if (loading) {
    return <div className="tenant-page-loading">Загрузка данных компании...</div>;
  }

  return (
    <div className="tenant-detail-page">
      {/* Хлебные крошки */}
      <div className="breadcrumbs">
        <button onClick={() => navigate('/admin')} className="breadcrumb-link">
          ← Админ-панель
        </button>
        <span className="breadcrumb-separator">/</span>
        <span className="breadcrumb-current">{tenant?.company_name}</span>
      </div>

      {/* Шапка с информацией о компании */}
      <div className="tenant-page-header">
        <div className="tenant-title">
          <h1>{tenant?.company_name}</h1>
          <span className={`status-badge-large ${tenant?.is_active ? 'active' : 'inactive'}`}>
            {tenant?.is_active ? 'Активна' : 'Заблокирована'}
          </span>
        </div>
        <div className="header-actions">
          <button onClick={toggleTenant} className="action-btn toggle-btn">
            {tenant?.is_active ? 'Заблокировать' : 'Разблокировать'}
          </button>
          <button
            onClick={() => {
              setBalanceAction('add');
              setShowBalanceModal(true);
            }}
            className="action-btn add-btn"
          >
            + Пополнить баланс
          </button>
          <button
            onClick={() => {
              setBalanceAction('deduct');
              setShowBalanceModal(true);
            }}
            className="action-btn deduct-btn"
          >
            - Списать сообщения
          </button>
        </div>
      </div>

      {/* Баланс и основная информация */}
      <div className="tenant-info-cards">
        <div className="info-card balance-card">
          <div className="card-content">
            <div className="card-label">Баланс сообщений</div>
            <div className="card-value">{tenant?.message_balance}</div>
          </div>
        </div>
        <div className="info-card">
          <div className="card-content">
            <div className="card-label">Email владельца</div>
            <div className="card-value">{tenant?.owner_email}</div>
          </div>
        </div>
        <div className="info-card">
          <div className="card-content">
            <div className="card-label">Сайт</div>
            <div className="card-value">
              {tenant?.website_url ? (
                <a href={tenant.website_url} target="_blank" rel="noopener noreferrer">
                  {tenant.website_url}
                </a>
              ) : 'Не указан'}
            </div>
          </div>
        </div>
        <div className="info-card">
          <div className="card-content">
            <div className="card-label">Дата создания</div>
            <div className="card-value">{formatDate(tenant?.created_at)}</div>
          </div>
        </div>
      </div>

      {/* Статистика */}
      <div className="stats-section">
        <h2>Статистика компании</h2>
        <div className="stats-grid-large">
          <div className="stat-card-large">
            <div className="stat-value">{stats?.total_sessions || 0}</div>
            <div className="stat-label">Всего диалогов</div>
          </div>
          <div className="stat-card-large">
            <div className="stat-value">{stats?.active_sessions || 0}</div>
            <div className="stat-label">Активных (24ч)</div>
          </div>
          <div className="stat-card-large">
            <div className="stat-value">{stats?.total_leads || 0}</div>
            <div className="stat-label">Всего лидов</div>
          </div>
          <div className="stat-card-large">
            <div className="stat-value">{stats?.total_messages || 0}</div>
            <div className="stat-label">Всего сообщений</div>
          </div>
          <div className="stat-card-large">
            <div className="stat-value">{stats?.conversion_rate || 0}%</div>
            <div className="stat-label">Конверсия в лиды</div>
          </div>
        </div>
      </div>

      {/* Табы */}
      <div className="page-tabs">
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
          Все диалоги ({totalSessions})
        </button>
        <button
          className={`tab-btn ${activeTab === 'leads' ? 'active' : ''}`}
          onClick={() => setActiveTab('leads')}
        >
          Лиды ({totalLeads})
        </button>
      </div>

      {/* Контент табов */}
      <div className="tab-content">
        {activeTab === 'overview' && (
          <div className="overview-tab">
            <div className="recent-sessions-section">
              <h3>Последние диалоги</h3>
              <div className="sessions-grid">
                {sessions.map(session => (
                  <div
                    key={session.id}
                    className="session-card"
                    onClick={() => {
                      setActiveTab('sessions');
                      loadSessionMessages(session.id);
                    }}
                  >
                    <div className="session-card-header">
                      <span className="session-name">{session.lead_name}</span>
                      <span className="session-time">{formatShortDate(session.created_at)}</span>
                    </div>
                    <div className="session-contacts">
                      {session.lead_phone && <span> {session.lead_phone}</span>}
                      {session.lead_email && <span> {session.lead_email}</span>}
                      {!session.lead_phone && !session.lead_email && (
                        <span className="no-contacts"> Аноним</span>
                      )}
                    </div>
                    <div className="session-preview">
                      {session.last_message || 'Нет сообщений'}
                    </div>
                    <div className="session-footer">
                      <span className="message-count">{session.messages_count} сообщ.</span>
                    </div>
                  </div>
                ))}
              </div>
              <button
                className="view-all-btn"
                onClick={() => setActiveTab('sessions')}
              >
                Все диалоги →
              </button>
            </div>
          </div>
        )}

        {activeTab === 'sessions' && (
          <div className="sessions-tab">
            <div className="sessions-list-full">
              {sessions.map(session => (
                <div
                  key={session.id}
                  className={`session-item-full ${selectedSession === session.id ? 'selected' : ''}`}
                  onClick={() => loadSessionMessages(session.id)}
                >
                  <div className="session-item-header">
                    <div className="session-title">
                      <span className="session-name">{session.lead_name}</span>
                      {session.has_contacts ? (
                        <span className="contact-badge"> Есть контакты</span>
                      ) : (
                        <span className="anonymous-badge">Аноним</span>
                      )}
                    </div>
                    <span className="session-date">{formatDate(session.created_at)}</span>
                  </div>
                  <div className="session-contacts-full">
                    {session.lead_phone && <span> {session.lead_phone}</span>}
                    {session.lead_email && <span> {session.lead_email}</span>}
                  </div>
                  <div className="session-preview-full">
                    {session.preview}
                  </div>
                  <div className="session-stats">
                    <span>{session.messages_count} сообщений</span>
                    <span>Обновлено: {formatShortDate(session.updated_at)}</span>
                  </div>
                </div>
              ))}
            </div>

            {selectedSession && (
              <div className="session-messages-panel">
                <div className="messages-panel-header">
                  <h3>Сообщения диалога</h3>
                  <button onClick={() => setSelectedSession(null)} className="close-panel-btn">✕</button>
                </div>
                <div className="messages-list-panel">
                  {sessionMessages.map(msg => (
                    <div key={msg.id} className={`message-bubble ${msg.is_from_lead ? 'from-lead' : 'from-bot'}`}>
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
            <table className="leads-table-full">
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
                    <td>
                      {lead.lead_phone ? (
                        <a href={`tel:${lead.lead_phone}`} className="contact-link">
                          {lead.lead_phone}
                        </a>
                      ) : '—'}
                    </td>
                    <td>
                      {lead.lead_email ? (
                        <a href={`mailto:${lead.lead_email}`} className="contact-link">
                          {lead.lead_email}
                        </a>
                      ) : '—'}
                    </td>
                    <td>{formatDate(lead.created_at)}</td>
                    <td>{lead.messages_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Модальное окно для баланса */}
      {showBalanceModal && (
        <div className="balance-modal">
          <div className="balance-modal-content">
            <h3>{balanceAction === 'add' ? 'Пополнить баланс' : 'Списать сообщения'}</h3>
            <input
              type="number"
              value={balanceAmount}
              onChange={(e) => setBalanceAmount(e.target.value)}
              placeholder="Введите количество"
              autoFocus
            />
            <div className="balance-modal-actions">
              <button onClick={() => setShowBalanceModal(false)} className="cancel-btn">
                Отмена
              </button>
              <button onClick={handleBalanceAction} className="confirm-btn">
                {balanceAction === 'add' ? 'Пополнить' : 'Списать'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default TenantDetailPage;