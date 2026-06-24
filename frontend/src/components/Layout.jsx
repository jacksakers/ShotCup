// src/components/Layout.jsx
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import AdminModal from './AdminModal';
import { useState, useRef } from 'react';

export default function Layout() {
  const { currentUser, adminAuthed, logoutAll } = useAuth();
  const [showAdminModal, setShowAdminModal] = useState(false);
  const navigate = useNavigate();
  const headerPressTimer = useRef(null);

  // Long-press the header title (500ms) to reveal admin login
  function handleHeaderMouseDown() {
    headerPressTimer.current = setTimeout(() => setShowAdminModal(true), 500);
  }
  function handleHeaderMouseUp() {
    clearTimeout(headerPressTimer.current);
  }

  function handleLogout() {
    logoutAll();
    navigate('/');
  }

  const navCls = ({ isActive }) =>
    `flex-1 py-3 text-center text-sm font-medium transition-colors ${
      isActive
        ? 'text-emerald-600 border-t-2 border-emerald-500'
        : 'text-gray-500 border-t-2 border-transparent'
    }`;

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <header className="bg-emerald-600 text-white shadow-md">
        <div className="max-w-md mx-auto px-4 py-3 flex items-center justify-between">
          <h1
            className="text-xl font-bold tracking-tight select-none cursor-default"
            onMouseDown={handleHeaderMouseDown}
            onMouseUp={handleHeaderMouseUp}
            onTouchStart={handleHeaderMouseDown}
            onTouchEnd={handleHeaderMouseUp}
          >
            🏆 ShotCup
          </h1>
          <div className="flex items-center gap-3 text-sm">
            {adminAuthed && (
              <span className="bg-yellow-400 text-yellow-900 text-xs font-semibold px-2 py-0.5 rounded-full">
                Admin
              </span>
            )}
            {currentUser && (
              <span className="opacity-80">
                {currentUser.username}
              </span>
            )}
            <button
              onClick={handleLogout}
              className="opacity-70 hover:opacity-100 transition-opacity text-xs underline"
            >
              Exit
            </button>
          </div>
        </div>
      </header>

      {/* Page content */}
      <main className="flex-1 max-w-md mx-auto w-full px-4 py-6">
        <Outlet />
      </main>

      {/* Bottom nav */}
      <nav className="bg-white border-t border-gray-200 sticky bottom-0">
        <div className="max-w-md mx-auto flex">
          <NavLink to="/leaderboard" className={navCls}>
            🏅 Standings
          </NavLink>
          <NavLink to="/teams" className={navCls}>
            ⚽ Teams
          </NavLink>
          <NavLink to="/profile" className={navCls}>
            👤 Me
          </NavLink>
          {adminAuthed && (
            <NavLink to="/admin" className={navCls}>
              ⚙️ Admin
            </NavLink>
          )}
        </div>
      </nav>

      {showAdminModal && (
        <AdminModal onClose={() => setShowAdminModal(false)} />
      )}
    </div>
  );
}
