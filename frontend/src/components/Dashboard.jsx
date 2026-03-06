// src/components/Dashboard.js
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Area,
  AreaChart,
  ComposedChart,
  Bar
} from 'recharts';
import './Dashboard.css';

function Dashboard({ token, company }) {
  const [stats, setStats] = useState(null);
  const [chartData, setChartData] = useState([]);
  const [recentSessions, setRecentSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [period, setPeriod] = useState(7);

  useEffect(() => {
    if (company) {
      loadDashboardData();
    }
  }, [company, period]);

  const loadDashboardData = async () => {
    setLoading(true);
    setError(null);

    try {
      const statsResponse = await axios.get(
        `http://localhost:8000/api/v1/dashboard/${company.id}/stats?period_days=${period}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );
      setStats(statsResponse.data);

      const sessionsResponse = await axios.get(
        `http://localhost:8000/api/v1/dashboard/${company.id}/all-sessions?include_anonymous=true`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      const allSessions = sessionsResponse.data.sessions || sessionsResponse.data;
      const chartData = generateChartData(allSessions, period);
      setChartData(chartData);

      const recentResponse = await axios.get(
        `http://localhost:8000/api/v1/dashboard/${company.id}/recent-sessions?hours=${period * 24}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );
      setRecentSessions(recentResponse.data.slice(0, 5));

    } catch (error) {
      console.error('Ошибка загрузки статистики:', error);
      setError(error.response?.data?.detail || error.message);
    } finally {
      setLoading(false);
    }
  };

  const generateChartData = (sessions, days) => {
    const data = [];
    const now = new Date();

    for (let i = days - 1; i >= 0; i--) {
      const date = new Date(now);
      date.setDate(date.getDate() - i);
      date.setHours(0, 0, 0, 0);

      const nextDate = new Date(date);
      nextDate.setDate(nextDate.getDate() + 1);

      const daySessions = sessions.filter(session => {
        const sessionDate = new Date(session.first_message_at);
        return sessionDate >= date && sessionDate < nextDate;
      });

      const leads = daySessions.filter(s => s.lead_phone || s.lead_email).length;

      data.push({
        date: date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' }),
        fullDate: date.toISOString().split('T')[0],
        sessions: daySessions.length,
        leads: leads,
        anonymous: daySessions.length - leads
      });
    }

    return data;
  };

  const formatNumber = (num) => {
    return new Intl.NumberFormat('ru-RU').format(num || 0);
  };

  const formatDateTime = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="recharts-default-tooltip">
          <p className="recharts-tooltip-label">{label}</p>
          {payload.map((entry, index) => (
            <p key={index} className="recharts-tooltip-item">
              <span className="recharts-tooltip-item-name">{entry.name}: </span>
              <span className="recharts-tooltip-item-value">{entry.value}</span>
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  if (loading) {
    return <div className="dashboard-loading">Загрузка статистики...</div>;
  }

  if (error) {
    return (
      <div className="dashboard-error">
        <p>Ошибка загрузки: {error}</p>
        <button onClick={loadDashboardData} className="refresh-btn">
            Попробовать снова
        </button>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h2> Статистика: {company.company_name}</h2>
        <div className="period-selector">
          <span>Период:</span>
          <select value={period} onChange={(e) => setPeriod(Number(e.target.value))}>
            <option value={1}>Сегодня</option>
            <option value={3}>3 дня</option>
            <option value={7}>7 дней</option>
            <option value={14}>14 дней</option>
            <option value={30}>30 дней</option>
            <option value={90}>90 дней</option>
          </select>
        </div>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-value">{formatNumber(stats?.total_sessions)}</div>
          <div className="stat-label">Всего диалогов</div>
        </div>

        <div className="stat-card">
          <div className="stat-value">{formatNumber(stats?.total_leads)}</div>
          <div className="stat-label">Всего лидов</div>
        </div>

        <div className="stat-card">
          <div className="stat-value">{formatNumber(stats?.sessions_last_period)}</div>
          <div className="stat-label">Диалогов за период</div>
        </div>

        <div className="stat-card">
          <div className="stat-value">{formatNumber(stats?.leads_last_period)}</div>
          <div className="stat-label">Лидов за период</div>
        </div>

        <div className="stat-card">
          <div className="stat-value">{formatNumber(stats?.messages_last_period)}</div>
          <div className="stat-label">Сообщений</div>
        </div>

        <div className="stat-card">
          <div className="stat-value">{formatNumber(stats?.active_sessions)}</div>
          <div className="stat-label">Активных сейчас</div>
        </div>

        <div className="stat-card">
          <div className="stat-value">{stats?.conversion_rate?.toFixed(1) || 0}%</div>
          <div className="stat-label">Конверсия в лиды</div>
        </div>
      </div>

      <div className="chart-section">
        <div className="chart-header">
          <h3>Динамика диалогов и лидов</h3>
          <div className="chart-legend">
            <div className="legend-item">
              <span className="legend-color sessions"></span>
              <span>Диалоги</span>
            </div>
            <div className="legend-item">
              <span className="legend-color leads"></span>
              <span>Лиды</span>
            </div>
          </div>
        </div>

        <div className="chart-container">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart
              data={chartData}
              margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" opacity={0.3} />
              <XAxis
                dataKey="date"
                stroke="var(--text-muted)"
                tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
              />
              <YAxis
                stroke="var(--text-muted)"
                tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                allowDecimals={false}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Area
                type="monotone"
                dataKey="sessions"
                name="Диалоги"
                stroke="var(--accent-success)"
                fill="var(--accent-success)"
                fillOpacity={0.1}
                strokeWidth={2}
              />
              <Line
                type="monotone"
                dataKey="leads"
                name="Лиды"
                stroke="var(--accent-primary)"
                strokeWidth={2}
                dot={{ r: 4, fill: 'var(--accent-primary)' }}
                activeDot={{ r: 6 }}
              />
              <Bar
                dataKey="anonymous"
                name="Анонимные"
                fill="var(--text-muted)"
                opacity={0.3}
                barSize={20}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>
        <div className="recent-sessions-section">
          <div className="recent-sessions-header">
            <h3>Последние диалоги</h3>
            <Link to="/dialogs" className="view-all-link">
              Все диалоги →
            </Link>
          </div>

          <div className="recent-sessions-list">
            {recentSessions.length === 0 ? (
              <div className="no-data">Нет диалогов за выбранный период</div>
            ) : (
              recentSessions.map((session) => (
                <div key={session.session_id} className="recent-session-item">
                  <div className="session-info">
                    <span className="session-name">{session.lead_name || "Аноним"}</span>
                    <span className="session-contact">
                      {session.lead_phone && <span>{session.lead_phone}</span>}
                      {session.lead_email && !session.lead_phone && <span>{session.lead_email}</span>}
                    </span>
                    <span className="session-time">{formatDateTime(session.last_message_at)}</span>
                  </div>
                  <div className="session-preview" title={session.preview_message}>
                    {session.preview_message || 'Нет сообщений'}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

      <div className="dashboard-actions">
        <button onClick={loadDashboardData} className="refresh-btn">
           Обновить данные
        </button>
      </div>
    </div>
  );
}

export default Dashboard;