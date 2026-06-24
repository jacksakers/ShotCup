// src/pages/Teams.jsx
import { useState, useEffect } from 'react';
import { getTeams } from '../api';

export default function Teams() {
  const [teams, setTeams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all'); // all | active | eliminated

  useEffect(() => {
    getTeams()
      .then(setTeams)
      .catch(() => setError('Failed to load teams.'))
      .finally(() => setLoading(false));
  }, []);

  const visible = teams.filter((t) => {
    const matchesSearch = t.name.toLowerCase().includes(search.toLowerCase()) ||
      (t.owner_username ?? '').toLowerCase().includes(search.toLowerCase());
    const matchesFilter =
      filter === 'all' ||
      (filter === 'active' && t.status === 'Active') ||
      (filter === 'eliminated' && t.status === 'Eliminated');
    return matchesSearch && matchesFilter;
  });

  if (loading) return <p className="text-center text-gray-400 mt-16">Loading…</p>;
  if (error) return <p className="text-center text-red-500 mt-16">{error}</p>;

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-gray-900">All Teams</h2>

      {/* Search */}
      <input
        type="text"
        placeholder="Search team or player…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
      />

      {/* Filter tabs */}
      <div className="flex gap-2">
        {['all', 'active', 'eliminated'].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`flex-1 py-1.5 rounded-lg text-sm font-medium capitalize transition-colors ${
              filter === f
                ? 'bg-emerald-600 text-white'
                : 'bg-white text-gray-500 border border-gray-200 hover:border-emerald-300'
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      <p className="text-xs text-gray-400">{visible.length} teams</p>

      <div className="space-y-2">
        {visible.map((team) => (
          <div
            key={team.id}
            className={`bg-white rounded-xl border px-4 py-3 shadow-sm flex items-center gap-3 ${
              team.status === 'Eliminated' ? 'opacity-50' : 'border-gray-100'
            }`}
          >
            <span
              className={`w-2.5 h-2.5 rounded-full shrink-0 ${
                team.status === 'Active' ? 'bg-emerald-400' : 'bg-gray-300'
              }`}
            />
            <div className="flex-1 min-w-0">
              <p className={`font-semibold text-sm ${team.status === 'Eliminated' ? 'line-through text-gray-400' : 'text-gray-800'}`}>
                {team.name}
                {team.won_tournament && ' 🏆'}
              </p>
              <p className="text-xs text-gray-400">
                {team.owner_username ?? <span className="italic">Unowned</span>}
              </p>
            </div>
            <div className="text-right shrink-0 space-y-0.5">
              <p className="text-sm font-bold text-emerald-700">{team.points_earned} pts</p>
              <p className="text-xs text-gray-400">
                {team.wins}W {team.draws}D {team.losses}L
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
