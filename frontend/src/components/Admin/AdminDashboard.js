import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import CreateAdminModal from './CreateAdminModal';
import './Admin.css';

function AdminDashboard({ admin, onLogout }) {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [tenants, setTenants] = useState([]);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateAdmin, setShowCreateAdmin] = useState(false);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      const token = localStorage.getItem('admin_token');
      const response = await axios.get(
        'http://localhost:8000/api/v1/admin/dashboard',
        { headers: { Authorization: `Bearer ${token}` } }
      );
      console.log('Dashboard data:', response.data);
      setStats(response.data);
      setTenants(response.data.top_tenants || []);
      setLogs(response.data.recent_logs || []);
    } catch (error) {
      console.error('Ошибка загрузки данных:', error);
    } finally {
      setLoading(false);
    }
  };

  const toggleTenant = async (tenantId, currentStatus) => {
    try {
      const token = localStorage.getItem('admin_token');
      await axios.post(
        `http://localhost:8000/api/v1/admin/tenants/${tenantId}/toggle`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      loadDashboardData();
    } catch (error) {
      alert('Ошибка: ' + (error.response?.data?.detail || error.message));
    }
  };

  const addBalance = async (tenantId) => {
    const amount = prompt('Сколько сообщений добавить?', '100');
    if (!amount) return;

    try {
      const token = localStorage.getItem('admin_token');
      await axios.post(
        `http://localhost:8000/api/v1/admin/tenants/${tenantId}/balance?amount=${amount}`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      loadDashboardData();
    } catch (error) {
      alert('Ошибка: ' + (error.response?.data?.detail || error.message));
    }
  };

  const deductBalance = async (tenantId) => {
    const amount = prompt('Сколько сообщений списать?', '10');
    if (!amount) return;

    try {
      const token = localStorage.getItem('admin_token');
      await axios.post(
        `http://localhost:8000/api/v1/admin/tenants/${tenantId}/deduct-balance?amount=${amount}`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      loadDashboardData();
    } catch (error) {
      alert('Ошибка: ' + (error.response?.data?.detail || error.message));
    }
  };

  const viewTenantDetails = (tenantId) => {
    navigate(`/admin/tenant/${tenantId}`);
  };

  const handleAdminCreated = () => {
    console.log('Админ успешно создан');
  };

  if (loading) {
    return <div className="admin-loading">Загрузка панели...</div>;
  }

  return (
    <div className="admin-dashboard">
      <div className="admin-header">
        <h1>Админ-панель</h1>
        <div className="admin-header-right">
          <div className="admin-info">
            <span className="admin-email">{admin?.email}</span>
            {admin?.is_superadmin && <span className="superadmin-badge">Супер-админ</span>}
          </div>
          <div className="admin-actions">
            {admin?.is_superadmin && (
              <button
                onClick={() => setShowCreateAdmin(true)}
                className="create-admin-btn"
              >
                + Создать админа
              </button>
            )}
            <button onClick={onLogout} className="logout-btn">
              Выйти
            </button>
          </div>
        </div>
      </div>

      {stats && (
        <>
          <div className="admin-stats-grid">
            <div className="stat-card">
              <div className="stat-value">{stats.system?.total_tenants || 0}</div>
              <div className="stat-label">Всего компаний</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stats.system?.total_users || 0}</div>
              <div className="stat-label">Пользователей</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stats.system?.total_sessions || 0}</div>
              <div className="stat-label">Всего диалогов</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stats.system?.total_messages || 0}</div>
              <div className="stat-label">Всего сообщений</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stats.system?.active_tenants || 0}</div>
              <div className="stat-label">Активных компаний</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stats.system?.messages_last_24h || 0}</div>
              <div className="stat-label">Сообщений за 24ч</div>
            </div>
          </div>

          <div className="admin-tenants">
            <h3>Компании</h3>
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Компания</th>
                  <th>Владелец</th>
                  <th>Статус</th>
                  <th>Баланс</th>
                  <th>Создана</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {tenants.length === 0 ? (
                  <tr>
                    <td colSpan="6" className="no-data">Нет компаний</td>
                  </tr>
                ) : (
                  tenants.map(tenant => (
                    <tr key={tenant.id}>
                      <td>
                        <button
                          className="company-link"
                          onClick={() => viewTenantDetails(tenant.id)}
                        >
                          {tenant.company_name}
                        </button>
                      </td>
                      <td>{tenant.owner_email}</td>
                      <td>
                        <span className={`status-badge ${tenant.is_active ? 'active' : 'inactive'}`}>
                          {tenant.is_active ? 'Активна' : 'Заблокирована'}
                        </span>
                      </td>
                      <td>{tenant.message_balance}</td>
                      <td>{new Date(tenant.created_at).toLocaleDateString()}</td>
                      <td>
                        {admin?.is_superadmin && (
                          <div className="action-buttons">
                            <button
                              onClick={() => toggleTenant(tenant.id, tenant.is_active)}
                              className="btn-small"
                            >
                              {tenant.is_active ? 'Заблокировать' : 'Разблокировать'}
                            </button>
                            <button
                              onClick={() => addBalance(tenant.id)}
                              className="btn-small btn-success"
                            >
                              + Пополнить
                            </button>
                            <button
                              onClick={() => deductBalance(tenant.id)}
                              className="btn-small btn-warning"
                            >
                              - Списать
                            </button>
                            <button
                              onClick={() => viewTenantDetails(tenant.id)}
                              className="btn-small btn-info"
                            >
                              Детали
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="admin-logs">
            <h3>Последние действия</h3>
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Время</th>
                  <th>Админ</th>
                  <th>Действие</th>
                  <th>IP</th>
                </tr>
              </thead>
              <tbody>
                {logs.length === 0 ? (
                  <tr>
                    <td colSpan="4" className="no-data">Нет логов</td>
                  </tr>
                ) : (
                  logs.map(log => (
                    <tr key={log.id}>
                      <td>{new Date(log.created_at).toLocaleString()}</td>
                      <td>{log.admin_email}</td>
                      <td>{log.action}</td>
                      <td>{log.ip_address}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {showCreateAdmin && (
        <CreateAdminModal
          onClose={() => setShowCreateAdmin(false)}
          onSuccess={handleAdminCreated}
        />
      )}
    </div>
  );
}

export default AdminDashboard;