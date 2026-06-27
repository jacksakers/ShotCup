// src/components/TradeInbox.jsx
import { useState } from 'react';
import { respondToTrade } from '../api';

export default function TradeInbox({ currentUser, trades, teams, onAction }) {
  const [selectedAccepted, setSelectedAccepted] = useState({}); // tradeId -> teamId
  const [actionError, setActionError] = useState('');
  const [submittingId, setSubmittingId] = useState(null);

  // Incoming: pending trades where current user owns at least one requested team, and is not proposer
  const incoming = trades.filter((t) => {
    if (t.status !== 'Pending' || t.proposer_id === currentUser?.id) return false;
    // Check if current user owns any of the requested team ids
    return t.requested_team_ids.some((id) => {
      const team = teams.find((x) => x.id === id);
      return team && team.owner_id === currentUser?.id;
    });
  });

  // Outgoing: pending trades proposed by current user
  const outgoing = trades.filter(
    (t) => t.status === 'Pending' && t.proposer_id === currentUser?.id
  );

  const handleRespond = async (tradeId, action) => {
    setActionError('');
    setSubmittingId(tradeId);

    try {
      let acceptedId = selectedAccepted[tradeId];
      if (action === 'accept') {
        const trade = trades.find((t) => t.id === tradeId);
        // Find which requested teams are owned by the current user
        const ownedReq = trade.requested_team_ids.filter((id) => {
          const team = teams.find((x) => x.id === id);
          return team && team.owner_id === currentUser?.id;
        });

        if (!acceptedId) {
          if (ownedReq.length === 1) {
            acceptedId = ownedReq[0];
          } else if (ownedReq.length > 1) {
            setActionError('Please select which country you want to trade away.');
            setSubmittingId(null);
            return;
          } else {
            setActionError('You no longer own any of the requested teams.');
            setSubmittingId(null);
            return;
          }
        }
      }

      await respondToTrade(tradeId, currentUser.id, action, acceptedId);
      if (onAction) onAction();
    } catch (err) {
      setActionError(err.message ?? 'Response failed.');
    } finally {
      setSubmittingId(null);
    }
  };

  return (
    <div className="space-y-6">
      {actionError && <div className="p-3 bg-red-50 text-red-700 rounded-xl text-sm font-medium">{actionError}</div>}

      {/* Incoming */}
      <div>
        <h3 className="text-sm font-bold text-gray-700 mb-2">📥 Incoming Offers ({incoming.length})</h3>
        {incoming.length === 0 ? (
          <p className="text-xs text-gray-400 italic bg-white rounded-xl border p-4 text-center">
            No pending incoming trade offers.
          </p>
        ) : (
          <div className="space-y-3">
            {incoming.map((trade) => {
              const ownedReq = trade.requested_team_ids.filter((id) => {
                const team = teams.find((x) => x.id === id);
                return team && team.owner_id === currentUser?.id;
              });

              const currentChoice = selectedAccepted[trade.id] || (ownedReq.length === 1 ? ownedReq[0] : '');

              return (
                <div key={trade.id} className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm space-y-3">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-xs font-bold text-emerald-600">Offer from {trade.proposer_username}</p>
                      <p className="text-[10px] text-gray-400">Proposed {new Date(trade.created_at).toLocaleDateString()}</p>
                    </div>
                  </div>

                  <div className="text-xs space-y-1">
                    <p className="text-gray-600">
                      <span className="font-bold text-gray-800">Giving You:</span> {trade.offered_team_names.join(' & ')}
                    </p>
                    <p className="text-gray-600">
                      <span className="font-bold text-gray-800">In Exchange For:</span> {trade.requested_team_names.join(' OR ')}
                    </p>
                  </div>

                  {ownedReq.length > 1 && (
                    <div className="space-y-1 bg-gray-50 p-2.5 rounded-lg border">
                      <label className="block text-[10px] font-bold text-gray-500">
                        Choose which of your countries to trade away:
                      </label>
                      <select
                        value={currentChoice}
                        onChange={(e) => setSelectedAccepted({ ...selectedAccepted, [trade.id]: parseInt(e.target.value) })}
                        className="w-full text-xs border rounded p-1 focus:outline-none focus:ring focus:ring-emerald-200"
                      >
                        <option value="">-- Select Team --</option>
                        {ownedReq.map((id) => {
                          const t = teams.find((x) => x.id === id);
                          return (
                            <option key={id} value={id}>
                              {t?.name}
                            </option>
                          );
                        })}
                      </select>
                    </div>
                  )}

                  <div className="flex gap-2 pt-1">
                    <button
                      onClick={() => handleRespond(trade.id, 'accept')}
                      disabled={submittingId !== null}
                      className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold py-2 rounded-lg transition-colors"
                    >
                      {submittingId === trade.id ? 'Loading...' : 'Accept'}
                    </button>
                    <button
                      onClick={() => handleRespond(trade.id, 'reject')}
                      disabled={submittingId !== null}
                      className="flex-1 bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-bold py-2 rounded-lg transition-colors"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Outgoing */}
      <div>
        <h3 className="text-sm font-bold text-gray-700 mb-2">📤 Sent Offers ({outgoing.length})</h3>
        {outgoing.length === 0 ? (
          <p className="text-xs text-gray-400 italic bg-white rounded-xl border p-4 text-center">
            No active sent trade offers.
          </p>
        ) : (
          <div className="space-y-3">
            {outgoing.map((trade) => (
              <div key={trade.id} className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm space-y-2">
                <div className="flex justify-between items-start">
                  <div>
                    <p className="text-xs font-bold text-gray-500">To: Any owner of {trade.requested_team_names.join('/')}</p>
                    <p className="text-[10px] text-gray-400">Proposed {new Date(trade.created_at).toLocaleDateString()}</p>
                  </div>
                  <span className="bg-yellow-100 text-yellow-800 text-[9px] font-bold px-2 py-0.5 rounded-full">
                    Pending
                  </span>
                </div>

                <div className="text-xs space-y-1">
                  <p className="text-gray-600">
                    <span className="font-bold text-gray-800">You Offer:</span> {trade.offered_team_names.join(' & ')}
                  </p>
                  <p className="text-gray-600">
                    <span className="font-bold text-gray-800">You Request:</span> {trade.requested_team_names.join(' OR ')}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
