// src/pages/SiteLogin.jsx
import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';

export default function SiteLogin() {
  const { loginSite } = useAuth();
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await loginSite(password);
      navigate('/pick-user');
    } catch (err) {
      setError(err.message || 'Wrong password — try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-emerald-600 flex items-center justify-center p-6">
      <div className="bg-white rounded-3xl shadow-2xl w-full max-w-sm p-8 text-center">
        <div className="text-6xl mb-4">🏆</div>
        <h1 className="text-3xl font-extrabold text-gray-900 mb-1">ShotCup</h1>
        <p className="text-gray-500 text-sm mb-8">World Cup Family Fantasy</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="password"
            placeholder="Family password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full border border-gray-200 rounded-xl px-4 py-3 text-center text-lg tracking-widest focus:outline-none focus:ring-2 focus:ring-emerald-500"
            autoFocus
          />
          {error && (
            <p className="text-red-500 text-sm">{error}</p>
          )}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 rounded-xl bg-emerald-600 text-white font-bold text-lg hover:bg-emerald-700 transition-colors disabled:opacity-50"
          >
            {loading ? 'Entering…' : 'Enter'}
          </button>
        </form>
      </div>
    </div>
  );
}
