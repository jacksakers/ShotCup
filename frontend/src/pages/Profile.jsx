// src/pages/Profile.jsx
import { useState, useEffect } from 'react';
import { getTeams, getLeaderboard } from '../api';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';

export default function Profile() {
  const { currentUser, selectUser } = useAuth();
  const navigate = useNavigate();
  const [myTeams, setMyTeams] = useState([]);
  const [rank, setRank] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!currentUser) return;
    Promise.all([getTeams(), getLeaderboard()])
      .then(([teams, lb]) => {
        setMyTeams(teams.filter((t) => t.owner_id === currentUser.id).sort((a, b) => b.points_earned - a.points_earned));
        const me = lb.find((e) => e.user_id === currentUser.id);
        setRank(me ?? null);
      })
      .finally(() => setLoading(false));
  }, [currentUser]);

  if (!currentUser) {
    return (
      <div className="text-center mt-16 space-y-4">
        <p className="text-gray-500">You haven't selected a profile yet.</p>
        <button
          onClick={() => navigate('/pick-user')}
          className="px-6 py-2 bg-emerald-600 text-white rounded-lg font-semibold hover:bg-emerald-700 transition-colors"
        >
          Pick a profile
        </button>
      </div>
    );
  }

  function handleSwitch() {
    selectUser(null);
    navigate('/pick-user');
  }

  if (loading) return <p className="text-center text-gray-400 mt-16">Loading…</p>;

  const totalPts = rank?.total_points ?? 0;
  const rankNum = rank?.rank ?? '–';

  return (
    <div className="space-y-5">
      {/* Profile card */}
      <div className="bg-emerald-600 rounded-2xl text-white p-6 text-center shadow-md">
        <div className="text-5xl mb-2">👤</div>
        <h2 className="text-2xl font-extrabold">{currentUser.username}</h2>
        <div className="flex justify-center gap-8 mt-4">
          <div>
            <p className="text-3xl font-bold">{totalPts}</p>
            <p className="text-xs opacity-75 uppercase tracking-wide">Points</p>
          </div>
          <div>
            <p className="text-3xl font-bold">#{rankNum}</p>
            <p className="text-xs opacity-75 uppercase tracking-wide">Rank</p>
          </div>
          <div>
            <p className="text-3xl font-bold">{myTeams.length}</p>
            <p className="text-xs opacity-75 uppercase tracking-wide">Teams</p>
          </div>
        </div>
      </div>

      {/* Teams */}
      <h3 className="font-bold text-gray-700">My Teams</h3>
      {myTeams.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-4">
          No teams yet — the draft hasn't run.
        </p>
      ) : (
        <div className="space-y-2">
          {myTeams.map((team) => (
            <div
              key={team.id}
              className={`bg-white rounded-xl border shadow-sm px-4 py-3 flex items-center gap-3 ${
                team.status === 'Eliminated' ? 'opacity-50 border-gray-100' : 'border-gray-100'
              }`}
            >
              <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${team.status === 'Active' ? 'bg-emerald-400' : 'bg-gray-300'}`} />
              <div className="flex-1">
                <p className={`font-semibold text-sm ${team.status === 'Eliminated' ? 'line-through text-gray-400' : 'text-gray-800'}`}>
                  {team.name}
                  {team.won_tournament && ' 🏆'}
                </p>
                <p className="text-xs text-gray-400">
                  {team.wins}W {team.draws}D {team.losses}L &middot; {team.goals_for} GF
                  {team.clean_sheets > 0 && ` · ${team.clean_sheets} CS`}
                </p>
              </div>
              <span className="text-emerald-700 font-bold text-sm">{team.points_earned} pts</span>
            </div>
          ))}
        </div>
      )}

      <button
        onClick={handleSwitch}
        className="w-full py-3 rounded-xl border border-gray-200 text-gray-500 text-sm hover:border-emerald-400 hover:text-emerald-600 transition-colors"
      >
        Switch profile
      </button>
    </div>
  );
}
