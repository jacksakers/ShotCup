// src/components/AdminModal.jsx
// Revealed by long-pressing the header title.
import { useState } from 'react';
import { useAuth } from '../context/AuthContext';

export default function AdminModal({ onClose }) {
  const { adminAuthed, loginAdmin, logoutAdmin } = useAuth();
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleLogin(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await loginAdmin(password);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleLogout() {
    logoutAdmin();
    onClose();
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6">
        <h2 className="text-lg font-bold text-gray-800 mb-4">Admin Access</h2>

        {adminAuthed ? (
          <div className="space-y-4">
            <p className="text-sm text-gray-600">You are currently logged in as admin.</p>
            <button
              onClick={handleLogout}
              className="w-full py-2 rounded-lg bg-red-100 text-red-700 font-medium hover:bg-red-200 transition-colors"
            >
              Logout Admin
            </button>
          </div>
        ) : (
          <form onSubmit={handleLogin} className="space-y-4">
            <input
              type="password"
              placeholder="Admin password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
              autoFocus
            />
            {error && <p className="text-red-500 text-sm">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-2 rounded-lg bg-emerald-600 text-white font-semibold hover:bg-emerald-700 transition-colors disabled:opacity-50"
            >
              {loading ? 'Logging in…' : 'Login'}
            </button>
          </form>
        )}

        <button
          onClick={onClose}
          className="mt-3 w-full py-2 text-sm text-gray-500 hover:text-gray-700"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
