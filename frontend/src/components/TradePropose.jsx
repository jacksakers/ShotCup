// src/components/TradePropose.jsx
import { useState } from 'react';
import { proposeTrade } from '../api';

export default function TradePropose({ currentUser, teams, onProposed }) {
  const [offered, setOffered] = useState([]);
  const [requested, setRequested] = useState([]);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const myTeams = teams.filter((t) => t.owner_id === currentUser?.id);
  const otherTeams = teams.filter(
    (t) => t.owner_id && t.owner_id !== currentUser?.id
  );

  const handleToggleOffered = (id) => {
    if (offered.includes(id)) {
      setOffered(offered.filter((x) => x !== id));
    } else {
      if (offered.length >= 2) {
        setError('You can offer at most 2 teams.');
        return;
      }
      setError('');
      setOffered([...offered, id]);
    }
  };

  const handleToggleRequested = (id) => {
    if (requested.includes(id)) {
      setRequested(requested.filter((x) => x !== id));
    } else {
      setRequested([...requested, id]);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (offered.length === 0) {
      setError('Please select at least 1 team to offer.');
      return;
    }
    if (requested.length === 0) {
      setError('Please select at least 1 team to request.');
      return;
    }
    setError('');
    setSuccess('');
    setSubmitting(true);

    try {
      await proposeTrade({
        proposer_id: currentUser.id,
        offered_team_ids: offered,
        requested_team_ids: requested,
      });
      setSuccess('Trade proposal posted successfully!');
      setOffered([]);
      setRequested([]);
      if (onProposed) onProposed();
    } catch (err) {
      setError(err.message ?? 'Failed to propose trade.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && <div className="p-3 bg-red-50 text-red-700 rounded-xl text-sm font-medium">{error}</div>}
      {success && <div className="p-3 bg-green-50 text-green-700 rounded-xl text-sm font-medium">{success}</div>}

      <div>
        <h3 className="text-sm font-bold text-gray-700 mb-1">
          1. Select Your Team(s) to Offer (Max 2)
        </h3>
        {myTeams.length === 0 ? (
          <p className="text-xs text-gray-400 italic">You do not own any teams to trade.</p>
        ) : (
          <div className="max-h-40 overflow-y-auto border border-gray-100 rounded-xl p-2 bg-white space-y-1">
            {myTeams.map((t) => {
              const isSel = offered.includes(t.id);
              return (
                <button
                  type="button"
                  key={t.id}
                  onClick={() => handleToggleOffered(t.id)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-xs font-semibold flex items-center justify-between transition-colors ${
                    isSel ? 'bg-emerald-50 border border-emerald-300 text-emerald-800' : 'bg-gray-50 text-gray-700 border border-transparent hover:bg-gray-100'
                  }`}
                >
                  <span>{t.name}</span>
                  <span className="text-emerald-600 font-bold">{isSel ? '✓ Offered' : '+ Offer'}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      <div>
        <h3 className="text-sm font-bold text-gray-700 mb-1">
          2. Select Team(s) in Return (Any will satisfy)
        </h3>
        {otherTeams.length === 0 ? (
          <p className="text-xs text-gray-400 italic">No other teams available to request.</p>
        ) : (
          <div className="max-h-48 overflow-y-auto border border-gray-100 rounded-xl p-2 bg-white space-y-1">
            {otherTeams.map((t) => {
              const isSel = requested.includes(t.id);
              return (
                <button
                  type="button"
                  key={t.id}
                  onClick={() => handleToggleRequested(t.id)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-xs font-semibold flex items-center justify-between transition-colors ${
                    isSel ? 'bg-indigo-50 border border-indigo-300 text-indigo-800' : 'bg-gray-50 text-gray-700 border border-transparent hover:bg-gray-100'
                  }`}
                >
                  <div>
                    <span className="block font-bold">{t.name}</span>
                    <span className="block text-[10px] text-gray-400 font-normal">Owner: {t.owner_username}</span>
                  </div>
                  <span className="text-indigo-600 font-bold">{isSel ? '✓ Requested' : '+ Request'}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      <button
        type="submit"
        disabled={submitting || myTeams.length === 0}
        className="w-full bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-bold py-3 px-4 rounded-xl shadow transition-colors disabled:opacity-50"
      >
        {submitting ? 'Proposing...' : 'Post Trade Offer 🔄'}
      </button>
    </form>
  );
}
