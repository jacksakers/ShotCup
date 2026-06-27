// src/pages/Trading.jsx
import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { getTeams, getTrades } from '../api';
import TradePropose from '../components/TradePropose';
import TradeInbox from '../components/TradeInbox';

export default function Trading() {
  const { currentUser } = useAuth();
  const [teams, setTeams] = useState([]);
  const [trades, setTrades] = useState([]);
  const [tab, setTab] = useState('propose'); // propose | inbox | history
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const refreshData = async () => {
    try {
      const [tData, trData] = await Promise.all([getTeams(), getTrades()]);
      setTeams(tData);
      setTrades(trData);
      setError('');
    } catch {
      setError('Failed to fetch trades or teams data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshData();
  }, []);

  if (loading) return <p className="text-center text-gray-400 mt-16">Loading trade market…</p>;
  if (error) return <p className="text-center text-red-500 mt-16">{error}</p>;

  // Count incoming offers for notification badge
  const incomingCount = trades.filter((t) => {
    if (t.status !== 'Pending' || t.proposer_id === currentUser?.id) return false;
    return t.requested_team_ids.some((id) => {
      const team = teams.find((x) => x.id === id);
      return team && team.owner_id === currentUser?.id;
    });
  }).length;

  const historyTrades = trades.filter((t) => t.status !== 'Pending');

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-gray-900">Trading Market</h2>
        <button
          onClick={() => {
            setLoading(true);
            refreshData();
          }}
          className="text-xs text-emerald-600 font-bold hover:underline"
        >
          Refresh ↻
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-2">
        <button
          onClick={() => setTab('propose')}
          className={`flex-1 py-2 rounded-lg text-xs font-bold transition-colors ${
            tab === 'propose' ? 'bg-emerald-600 text-white shadow' : 'bg-white text-gray-500 border border-gray-100 hover:bg-gray-50'
          }`}
        >
          🔄 Propose Offer
        </button>
        <button
          onClick={() => setTab('inbox')}
          className={`flex-1 py-2 rounded-lg text-xs font-bold transition-colors relative ${
            tab === 'inbox' ? 'bg-emerald-600 text-white shadow' : 'bg-white text-gray-500 border border-gray-100 hover:bg-gray-50'
          }`}
        >
          📥 Inbox
          {incomingCount > 0 && (
            <span className="absolute -top-1 -right-1 bg-red-500 text-white text-[9px] font-bold h-4 w-4 rounded-full flex items-center justify-center animate-pulse">
              {incomingCount}
            </span>
          )}
        </button>
        <button
          onClick={() => setTab('history')}
          className={`flex-1 py-2 rounded-lg text-xs font-bold transition-colors ${
            tab === 'history' ? 'bg-emerald-600 text-white shadow' : 'bg-white text-gray-500 border border-gray-100 hover:bg-gray-50'
          }`}
        >
          📜 History
        </button>
      </div>

      <div className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm">
        {tab === 'propose' && (
          <TradePropose currentUser={currentUser} teams={teams} onProposed={refreshData} />
        )}

        {tab === 'inbox' && (
          <TradeInbox currentUser={currentUser} trades={trades} teams={teams} onAction={refreshData} />
        )}

        {tab === 'history' && (
          <div className="space-y-3">
            <h3 className="text-sm font-bold text-gray-700 mb-2">📜 Completed & Past Trades ({historyTrades.length})</h3>
            {historyTrades.length === 0 ? (
              <p className="text-xs text-gray-400 italic text-center py-4">No completed trades found.</p>
            ) : (
              <div className="space-y-3">
                {historyTrades.map((t) => (
                  <div key={t.id} className="p-3 bg-gray-50 rounded-xl border border-gray-100 space-y-1 text-xs">
                    <div className="flex justify-between items-center">
                      <span className="font-bold text-gray-800">Trade #{t.id}</span>
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                          t.status === 'Accepted'
                            ? 'bg-green-100 text-green-800'
                            : t.status === 'Vetoed'
                            ? 'bg-orange-100 text-orange-800'
                            : 'bg-red-100 text-red-800'
                        }`}
                      >
                        {t.status}
                      </span>
                    </div>
                    {t.status === 'Accepted' ? (
                      <p className="text-gray-600">
                        <span className="font-semibold text-emerald-700">{t.proposer_username}</span> received{' '}
                        <span className="font-bold">{t.accepted_team_name}</span> in exchange for sending{' '}
                        <span className="font-bold">{t.offered_team_names.join(' & ')}</span> to{' '}
                        <span className="font-semibold text-emerald-700">{t.receiver_username}</span>.
                      </p>
                    ) : t.status === 'Vetoed' ? (
                      <p className="text-gray-500 italic">
                        Trade by {t.proposer_username} was vetoed by Admin.
                      </p>
                    ) : (
                      <p className="text-gray-500">
                        <span className="font-semibold">{t.proposer_username}</span>'s offer to trade{' '}
                        <span className="font-bold">{t.offered_team_names.join(' & ')}</span> for{' '}
                        <span className="font-bold">{t.requested_team_names.join('/')}</span> was rejected.
                      </p>
                    )}
                    <p className="text-[10px] text-gray-400">Processed {new Date(t.created_at).toLocaleDateString()}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
