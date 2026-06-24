// src/pages/Leaderboard.jsx
import { useState, useEffect } from 'react';
import { getLeaderboard, getTeams } from '../api';
import { useAuth } from '../context/AuthContext';

const MEDALS = ['🥇', '🥈', '🥉'];

export default function Leaderboard() {
  const { currentUser } = useAuth();
  const [leaderboard, setLeaderboard] = useState([]);
  const [teams, setTeams] = useState([]);
  const [expanded, setExpanded] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([getLeaderboard(), getTeams()])
      .then(([lb, t]) => {
        setLeaderboard(lb);
        setTeams(t);
      })
      .catch(() => setError('Failed to load leaderboard.'))
      .finally(() => setLoading(false));
  }, []);

  function teamsForUser(userId) {
    return teams
      .filter((t) => t.owner_id === userId)
      .sort((a, b) => b.points_earned - a.points_earned);
  }

  if (loading) return <p className="text-center text-gray-400 mt-16">Loading…</p>;
  if (error) return <p className="text-center text-red-500 mt-16">{error}</p>;

  return (
    <div className="space-y-3">
      <h2 className="text-xl font-bold text-gray-900">Leaderboard</h2>

      {leaderboard.map((entry) => {
        const isMe = currentUser?.id === entry.user_id;
        const isOpen = expanded === entry.user_id;
        const userTeams = teamsForUser(entry.user_id);
        const medal = MEDALS[entry.rank - 1] ?? `#${entry.rank}`;

        return (
          <div
            key={entry.user_id}
            className={`bg-white rounded-2xl shadow-sm border transition-all ${
              isMe ? 'border-emerald-400' : 'border-gray-100'
            }`}
          >
            <button
              className="w-full flex items-center gap-3 px-4 py-4 text-left"
              onClick={() => setExpanded(isOpen ? null : entry.user_id)}
            >
              <span className="text-2xl w-8 text-center shrink-0">{medal}</span>
              <div className="flex-1 min-w-0">
                <p className={`font-bold text-gray-900 truncate ${isMe ? 'text-emerald-700' : ''}`}>
                  {entry.username}
                  {isMe && <span className="ml-2 text-xs font-normal text-emerald-500">(you)</span>}
                </p>
                <p className="text-xs text-gray-400">{entry.team_count} teams</p>
              </div>
              <div className="text-right shrink-0">
                <p className="text-2xl font-extrabold text-gray-900">{entry.total_points}</p>
                <p className="text-xs text-gray-400">pts</p>
              </div>
              <span className="text-gray-400 text-sm ml-1">{isOpen ? '▲' : '▼'}</span>
            </button>

            {isOpen && (
              <div className="border-t border-gray-100 px-4 pb-4 pt-2 space-y-1">
                {userTeams.length === 0 ? (
                  <p className="text-xs text-gray-400 text-center py-2">No teams yet</p>
                ) : (
                  userTeams.map((team) => (
                    <div key={team.id} className="flex items-center justify-between py-1.5 text-sm">
                      <div className="flex items-center gap-2">
                        <span
                          className={`w-2 h-2 rounded-full shrink-0 ${
                            team.status === 'Active' ? 'bg-emerald-400' : 'bg-gray-300'
                          }`}
                        />
                        <span className={team.status === 'Eliminated' ? 'text-gray-400 line-through' : 'text-gray-700'}>
                          {team.name}
                        </span>
                        {team.won_tournament && <span title="Champions">🏆</span>}
                        {team.reached_final && !team.won_tournament && <span title="Finalist">🥈</span>}
                        {team.reached_semis && !team.reached_final && <span title="Semi-finalists">4️⃣</span>}
                      </div>
                      <span className="font-semibold text-emerald-700">{team.points_earned} pts</span>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
