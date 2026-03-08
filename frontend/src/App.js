// src/App.js
import React, { useState, useEffect } from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import axios from 'axios';
import './App.css';

// Импортируем компоненты для пользователя
import LoginForm from './components/LoginForm';
import RegisterForm from './components/RegisterForm';
import Dashboard from './components/Dashboard';
import DialogList from './components/DialogList';
import LeadsList from './components/LeadsList';
import CompanySettings from './components/CompanySettings';
import WidgetSettings from './components/WidgetSettings';

// Импортируем компоненты для админа
import AdminLogin from './components/Admin/AdminLogin';
import AdminDashboard from './components/Admin/AdminDashboard';
import TenantDetailPage from './components/Admin/TenantDetailPage';

import { NotificationProvider } from './components/NotificationManager';
import AddCompanyModal from './components/AddCompanyModal';
import ThemeToggle from './components/ThemeToggle';
import { ThemeProvider } from './contexts/ThemeContext';

// Импортируем кастомный селект
import CustomSelect from './components/CustomSelect';

// Основной контент для пользователя
function MainAppContent({ token, setToken }) {
  const navigate = useNavigate();
  const [companies, setCompanies] = useState([]);
  const [selectedCompany, setSelectedCompany] = useState(null);
  const [user, setUser] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [currentPath, setCurrentPath] = useState(window.location.pathname);

  const loadUserData = async () => {
    setIsLoading(true);
    try {
      const userResponse = await axios.get('/api/v1/auth/me', {
        headers: { Authorization: `Bearer ${token}` },
      });
      setUser(userResponse.data);

      if (!userResponse.data.email_verified) {
        alert('Пожалуйста, подтвердите email перед входом');
        handleLogout();
        return;
      }

      await loadCompanies();
    } catch (error) {
      console.error('Ошибка загрузки данных:', error);
      if (error.response?.status === 401) {
        handleLogout();
      }
    } finally {
      setIsLoading(false);
    }
  };

  const loadCompanies = async () => {
    try {
      const response = await axios.get('/api/v1/tenants/', {
        headers: { Authorization: `Bearer ${token}` },
      });
      setCompanies(response.data);
      if (response.data.length > 0 && !selectedCompany) {
        setSelectedCompany(response.data[0]);
      }
    } catch (error) {
      console.error('Ошибка загрузки компаний:', error);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setToken(null);
    setCompanies([]);
    setSelectedCompany(null);
    setUser(null);
    navigate('/');
  };

  const updateCompany = (updatedCompany) => {
    setCompanies(companies.map(c =>
      c.id === updatedCompany.id ? updatedCompany : c
    ));
    setSelectedCompany(updatedCompany);
  };

  const handleAddCompany = async (companyName, website) => {
    try {
      const response = await axios.post(
        '/api/v1/tenants/',
        {
          company_name: companyName,
          website_url: website || ''
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      setCompanies(prevCompanies => [...prevCompanies, response.data]);
      setSelectedCompany(response.data);
      setIsModalOpen(false);
      console.log('Компания создана:', response.data);
    } catch (error) {
      console.error('Ошибка при создании компании:', error);
      throw error;
    }
  };

  const handleNavigate = (path) => {
    setCurrentPath(path);
    navigate(path);
  };

  useEffect(() => {
    if (token) {
      loadUserData();
    }
  }, [token]);

  if (isLoading) {
    return (
      <div className="loading-container">
        <div className="loading-spinner"></div>
        <p>Загрузка...</p>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <h1>Агелар - Личный кабинет</h1>
        </div>
        <div className="header-right">
          {user && (
            <div className="user-info">
              <span className="user-email">{user.email}</span>
              {selectedCompany && (
                <span className="company-name">
                  {selectedCompany.company_name}
                </span>
              )}
            </div>
          )}
          <ThemeToggle />
          <button onClick={handleLogout} className="logout-btn">
            Выйти
          </button>
        </div>
      </header>

      <div className="app-container">
        <aside className="sidebar">
          <div className="company-selector">
            <h3>Компании</h3>

            {/* Заменяем старый select на новый кастомный селект */}
            <CustomSelect
              options={companies}
              value={selectedCompany?.id}
              onChange={(company) => setSelectedCompany(company)}
              placeholder="Выберите компанию"
            />

            <button
              onClick={() => setIsModalOpen(true)}
              className="add-company-btn"
            >
              + Добавить компанию
            </button>
          </div>

          <nav className="main-nav">
            <button
              onClick={() => handleNavigate('/dashboard')}
              className={`nav-link ${currentPath === '/dashboard' ? 'active' : ''}`}
              data-icon="dashboard"
            >
              Статистика
            </button>
            <button
              onClick={() => handleNavigate('/dialogs')}
              className={`nav-link ${currentPath === '/dialogs' ? 'active' : ''}`}
              data-icon="dialogs"
            >
              Диалоги
            </button>
            <button
              onClick={() => handleNavigate('/leads')}
              className={`nav-link ${currentPath === '/leads' ? 'active' : ''}`}
              data-icon="leads"
            >
              Лиды
            </button>
            <button
              onClick={() => handleNavigate('/company-settings')}
              className={`nav-link ${currentPath === '/company-settings' ? 'active' : ''}`}
              data-icon="company"
            >
              Настройки компании
            </button>
            <button
              onClick={() => handleNavigate('/widget-settings')}
              className={`nav-link ${currentPath === '/widget-settings' ? 'active' : ''}`}
              data-icon="widget"
            >
              Настройки виджета
            </button>
          </nav>

          <div className="sidebar-footer">
            <div className="balance-info">
              <span>Баланс сообщений:</span>
              <strong>{selectedCompany?.message_balance || 0}</strong>
            </div>
          </div>
        </aside>

        <main className="main-content">
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" />} />
            <Route
              path="/dashboard"
              element={
                selectedCompany ? (
                  <Dashboard token={token} company={selectedCompany} />
                ) : (
                  <div className="no-company-selected">
                    <h3>Выберите компанию</h3>
                    <p>Пожалуйста, выберите компанию из списка слева</p>
                  </div>
                )
              }
            />
            <Route
              path="/dialogs"
              element={
                selectedCompany ? (
                  <DialogList token={token} company={selectedCompany} />
                ) : (
                  <div className="no-company-selected">
                    <h3>Выберите компанию</h3>
                    <p>Пожалуйста, выберите компанию из списка слева</p>
                  </div>
                )
              }
            />
            <Route
              path="/leads"
              element={
                selectedCompany ? (
                  <LeadsList token={token} company={selectedCompany} />
                ) : (
                  <div className="no-company-selected">
                    <h3>Выберите компанию</h3>
                    <p>Пожалуйста, выберите компанию из списка слева</p>
                  </div>
                )
              }
            />
            <Route
              path="/company-settings"
              element={
                selectedCompany ? (
                  <CompanySettings
                    token={token}
                    company={selectedCompany}
                    onUpdate={updateCompany}
                  />
                ) : (
                  <div className="no-company-selected">
                    <h3>Выберите компанию</h3>
                    <p>Пожалуйста, выберите компанию из списка слева</p>
                  </div>
                )
              }
            />
            <Route
              path="/widget-settings"
              element={
                selectedCompany ? (
                  <WidgetSettings
                    token={token}
                    company={selectedCompany}
                    onUpdate={updateCompany}
                  />
                ) : (
                  <div className="no-company-selected">
                    <h3>Выберите компанию</h3>
                    <p>Пожалуйста, выберите компанию из списка слева</p>
                  </div>
                )
              }
            />
          </Routes>
        </main>
      </div>

      <AddCompanyModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onAdd={handleAddCompany}
      />
    </div>
  );
}

// Компонент для админ-панели
function AdminApp() {
  const navigate = useNavigate();
  const [admin, setAdmin] = useState(null);

  useEffect(() => {
    const savedAdmin = localStorage.getItem('admin_data');
    if (savedAdmin && savedAdmin !== 'undefined' && savedAdmin !== 'null') {
      try {
        const parsedAdmin = JSON.parse(savedAdmin);
        setAdmin(parsedAdmin);
      } catch (error) {
        console.error('Ошибка парсинга admin_data:', error);
        localStorage.removeItem('admin_data');
        localStorage.removeItem('admin_token');
      }
    }
  }, []);

  const handleAdminLogin = (adminData) => {
    setAdmin(adminData);
  };

  const handleAdminLogout = () => {
    localStorage.removeItem('admin_token');
    localStorage.removeItem('admin_data');
    setAdmin(null);
    navigate('/admin');
  };

  if (!admin) {
    return <AdminLogin onLogin={handleAdminLogin} />;
  }

  return <AdminDashboard admin={admin} onLogout={handleAdminLogout} />;
}

function App() {
  const navigate = useNavigate();
  const [token, setToken] = useState(localStorage.getItem('token'));

  const handleLogin = async (email, password) => {
    try {
      const formData = new FormData();
      formData.append('username', email);
      formData.append('password', password);

      const response = await axios.post(
        '/api/v1/auth/login',
        formData,
        { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
      );

      const data = response.data;

      if (data.requires_2fa) {
        alert('Требуется двухфакторная аутентификация');
      } else if (data.access_token) {
        localStorage.setItem('token', data.access_token);
        setToken(data.access_token);
        navigate('/dashboard');
      } else {
        alert('Неожиданный ответ от сервера');
      }
    } catch (error) {
      console.error('Login error:', error);
      alert('Ошибка входа: ' + (error.response?.data?.detail || error.message));
    }
  };

  return (
    <ThemeProvider>
      <NotificationProvider>
        <Routes>
          {/* Публичные маршруты */}
          <Route path="/" element={<LoginForm onLogin={handleLogin} />} />
          <Route path="/register" element={<RegisterForm />} />

          {/* Маршруты для админа */}
          <Route path="/admin" element={<AdminApp />} />
          <Route path="/admin/tenant/:tenantId" element={<TenantDetailPage />} />

          {/* Защищенные маршруты пользователя */}
          <Route
            path="/*"
            element={
              token ? (
                <MainAppContent token={token} setToken={setToken} />
              ) : (
                <Navigate to="/" />
              )
            }
          />
        </Routes>
      </NotificationProvider>
    </ThemeProvider>
  );
}

export default App;