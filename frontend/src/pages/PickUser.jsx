// src/pages/PickUser.jsx
import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { getUsers, createUser } from '../api';

export default function PickUser() {
  const { selectUser } = useAuth();
  const navigate = useNavigate();
  const [users, setUsers] = useState([]);
  const [newName, setNewName] = useState('');
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    getUsers()
      .then(setUsers)
      .catch(() => setError('Could not load players.'))
      .finally(() => setLoading(false));
  }, []);

  function handlePick(user) {
    selectUser(user);
    navigate('/leaderboard');
  }

  async function handleAdd(e) {
    e.preventDefault();
    const name = newName.trim();
    if (!name) return;
    setAdding(true);
    setError('');
    try {
      const user = await createUser(name);
      setUsers((prev) => [...prev, user]);
      setNewName('');
    } catch (err) {
      setError(err.message);
    } finally {
      setAdding(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-start pt-12 p-4">
      <div className="w-full max-w-sm">
        <h2 className="text-2xl font-bold text-gray-900 mb-1 text-center">Who are you?</h2>
        <p className="text-gray-500 text-sm text-center mb-6">Tap your name to enter</p>

        {loading ? (
          <p className="text-center text-gray-400">Loading…</p>
        ) : (
          <div className="space-y-2 mb-6">
            {users.length === 0 && (
              <p className="text-center text-gray-400 text-sm">
                No players yet — add the first one below!
              </p>
            )}
            {users.map((user) => (
              <button
                key={user.id}
                onClick={() => handlePick(user)}
                className="w-full text-left px-5 py-4 bg-white rounded-xl shadow-sm border border-gray-100 hover:border-emerald-400 hover:shadow-md transition-all flex items-center justify-between"
              >
                <span className="font-semibold text-gray-800">{user.username}</span>
                <span className="text-emerald-500 text-lg">→</span>
              </button>
            ))}
          </div>
        )}

        {/* Add new player */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
          <p className="text-xs text-gray-500 font-medium mb-3 uppercase tracking-wide">
            Add a player
          </p>
          <form onSubmit={handleAdd} className="flex gap-2">
            <input
              type="text"
              placeholder="Your name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
            <button
              type="submit"
              disabled={adding}
              className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-semibold hover:bg-emerald-700 transition-colors disabled:opacity-50"
            >
              {adding ? '…' : 'Add'}
            </button>
          </form>
          {error && <p className="text-red-500 text-xs mt-2">{error}</p>}
        </div>
      </div>
    </div>
  );
}
