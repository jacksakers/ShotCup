// src/context/AuthContext.jsx
import { createContext, useContext, useState, useEffect } from 'react';
import { siteLogin as apiSiteLogin, adminLogin as apiAdminLogin } from '../api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [siteAuthed, setSiteAuthed] = useState(
    () => !!localStorage.getItem('site_token')
  );
  const [adminAuthed, setAdminAuthed] = useState(
    () => !!localStorage.getItem('admin_token')
  );
  const [currentUser, setCurrentUser] = useState(() => {
    const stored = localStorage.getItem('current_user');
    return stored ? JSON.parse(stored) : null;
  });

  function selectUser(user) {
    setCurrentUser(user);
    if (user) {
      localStorage.setItem('current_user', JSON.stringify(user));
    } else {
      localStorage.removeItem('current_user');
    }
  }

  async function loginSite(password) {
    const data = await apiSiteLogin(password);
    localStorage.setItem('site_token', data.access_token);
    setSiteAuthed(true);
  }

  async function loginAdmin(password) {
    const data = await apiAdminLogin(password);
    localStorage.setItem('admin_token', data.access_token);
    setAdminAuthed(true);
  }

  function logoutAdmin() {
    localStorage.removeItem('admin_token');
    setAdminAuthed(false);
  }

  function logoutAll() {
    localStorage.removeItem('site_token');
    localStorage.removeItem('admin_token');
    localStorage.removeItem('current_user');
    setSiteAuthed(false);
    setAdminAuthed(false);
    setCurrentUser(null);
  }

  return (
    <AuthContext.Provider
      value={{ siteAuthed, adminAuthed, currentUser, loginSite, loginAdmin, logoutAdmin, logoutAll, selectUser }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
