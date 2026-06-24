// src/pages/Admin.jsx
import { useState } from 'react';
import { runDraft, parseStandings, submitMatchResult, overrideTeam, overrideUserPoints, vetoTrade } from '../api';

// ─── Reusable card ──────────────────────────────────────────────────────────
function Section({ title, children }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 space-y-4">
      <h3 className="font-bold text-gray-800 text-base">{title}</h3>
      {children}
    </div>
  );
}

// ─── Status banner ──────────────────────────────────────────────────────────
function StatusBanner({ status }) {
  if (!status) return null;
  const isError = status.type === 'error';
  return (
    <div
      className={`rounded-xl px-4 py-3 text-sm ${
        isError ? 'bg-red-50 text-red-700' : 'bg-emerald-50 text-emerald-800'
      }`}
    >
      {status.message}
    </div>
  );
}

// ─── Draft ──────────────────────────────────────────────────────────────────
function DraftSection() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleDraft() {
    if (!confirm('Run the draft? This randomly assigns all teams and cannot be undone.')) return;
    setLoading(true);
    setStatus(null);
    try {
      const res = await runDraft();
      setStatus({
        type: 'ok',
        message: `Draft done! ${res.teams_distributed} teams split between ${res.players} players (${res.teams_per_player} each${res.extra_teams > 0 ? `, ${res.extra_teams} extra` : ''}).`,
      });
    } catch (err) {
      setStatus({ type: 'error', message: err.message });
    } finally {
      setLoading(false);
    }
  }

  return (
    <Section title="🎲 Run Draft">
      <p className="text-sm text-gray-500">
        Randomly distributes all active teams among registered players. Can only be run once.
      </p>
      <StatusBanner status={status} />
      <button
        onClick={handleDraft}
        disabled={loading}
        className="w-full py-3 rounded-xl bg-emerald-600 text-white font-bold hover:bg-emerald-700 transition-colors disabled:opacity-50"
      >
        {loading ? 'Running…' : 'Run Draft'}
      </button>
    </Section>
  );
}

// ─── Standings parser ────────────────────────────────────────────────────────
function StandingsSection() {
  const [text, setText] = useState('');
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleParse(e) {
    e.preventDefault();
    setLoading(true);
    setStatus(null);
    try {
      const res = await parseStandings(text);
      setStatus({
        type: 'ok',
        message: `Updated ${res.count} team(s): ${res.updated_teams.join(', ')}${
          res.skipped_teams.length > 0 ? `. Skipped: ${res.skipped_teams.join(', ')}` : ''
        }`,
      });
    } catch (err) {
      setStatus({ type: 'error', message: err.message });
    } finally {
      setLoading(false);
    }
  }

  return (
    <Section title="📋 Import Standings">
      <p className="text-sm text-gray-500">
        Paste raw text from the FIFA standings page. All scores will recalculate automatically.
      </p>
      <form onSubmit={handleParse} className="space-y-3">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={7}
          placeholder={'Paste FIFA standings text here…\n\nExample:\nArgentina 3 3 0 0 9 0 +9 9\nFrance 3 2 1 0 7 2 +5 7'}
          className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500 resize-none"
        />
        <StatusBanner status={status} />
        <button
          type="submit"
          disabled={loading || !text.trim()}
          className="w-full py-3 rounded-xl bg-emerald-600 text-white font-bold hover:bg-emerald-700 transition-colors disabled:opacity-50"
        >
          {loading ? 'Parsing…' : 'Parse & Update'}
        </button>
      </form>
    </Section>
  );
}

// ─── Match result ────────────────────────────────────────────────────────────
function MatchResultSection() {
  const [form, setForm] = useState({
    home_team: '',
    away_team: '',
    home_goals: '',
    away_goals: '',
    is_knockout: false,
    winner_team: '',
  });
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  function set(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  const isDrawn = form.home_goals !== '' && form.away_goals !== '' &&
    Number(form.home_goals) === Number(form.away_goals);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setStatus(null);
    try {
      const payload = {
        home_team: form.home_team,
        away_team: form.away_team,
        home_goals: Number(form.home_goals),
        away_goals: Number(form.away_goals),
        is_knockout: form.is_knockout,
        winner_team: form.winner_team || null,
      };
      await submitMatchResult(payload);
      setStatus({ type: 'ok', message: `Result recorded: ${form.home_team} ${form.home_goals}–${form.away_goals} ${form.away_team}` });
      setForm({ home_team: '', away_team: '', home_goals: '', away_goals: '', is_knockout: false, winner_team: '' });
    } catch (err) {
      setStatus({ type: 'error', message: err.message });
    } finally {
      setLoading(false);
    }
  }

  return (
    <Section title="⚽ Record Match Result">
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Home team</label>
            <input
              type="text"
              value={form.home_team}
              onChange={(e) => set('home_team', e.target.value)}
              placeholder="France"
              required
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Away team</label>
            <input
              type="text"
              value={form.away_team}
              onChange={(e) => set('away_team', e.target.value)}
              placeholder="Brazil"
              required
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Home goals</label>
            <input
              type="number"
              min="0"
              value={form.home_goals}
              onChange={(e) => set('home_goals', e.target.value)}
              required
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Away goals</label>
            <input
              type="number"
              min="0"
              value={form.away_goals}
              onChange={(e) => set('away_goals', e.target.value)}
              required
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>
        </div>

        <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
          <input
            type="checkbox"
            checked={form.is_knockout}
            onChange={(e) => set('is_knockout', e.target.checked)}
            className="accent-emerald-600"
          />
          Knockout round (loser is eliminated)
        </label>

        {/* Penalty winner — only show for drawn knockout */}
        {form.is_knockout && isDrawn && (
          <div>
            <label className="block text-xs text-gray-500 mb-1">
              Penalty winner (scores are equal)
            </label>
            <input
              type="text"
              value={form.winner_team}
              onChange={(e) => set('winner_team', e.target.value)}
              placeholder="Winner team name"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>
        )}

        <StatusBanner status={status} />
        <button
          type="submit"
          disabled={loading}
          className="w-full py-3 rounded-xl bg-emerald-600 text-white font-bold hover:bg-emerald-700 transition-colors disabled:opacity-50"
        >
          {loading ? 'Saving…' : 'Record Result'}
        </button>
      </form>
    </Section>
  );
}

// ─── Manual overrides ────────────────────────────────────────────────────────
function OverridesSection() {
  const [teamId, setTeamId] = useState('');
  const [field, setField] = useState('wins');
  const [value, setValue] = useState('');
  const [userId, setUserId] = useState('');
  const [userPts, setUserPts] = useState('');
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  const TEAM_FIELDS = ['wins', 'draws', 'losses', 'goals_for', 'goals_against', 'clean_sheets', 'status'];

  async function handleTeamOverride(e) {
    e.preventDefault();
    setLoading(true);
    setStatus(null);
    try {
      let v = value;
      if (['wins','draws','losses','goals_for','goals_against','clean_sheets'].includes(field)) {
        v = Number(value);
      }
      await overrideTeam(Number(teamId), { [field]: v });
      setStatus({ type: 'ok', message: `Team #${teamId} updated.` });
    } catch (err) {
      setStatus({ type: 'error', message: err.message });
    } finally {
      setLoading(false);
    }
  }

  async function handleUserOverride(e) {
    e.preventDefault();
    setLoading(true);
    setStatus(null);
    try {
      await overrideUserPoints(Number(userId), Number(userPts));
      setStatus({ type: 'ok', message: `Player #${userId} points set to ${userPts}.` });
    } catch (err) {
      setStatus({ type: 'error', message: err.message });
    } finally {
      setLoading(false);
    }
  }

  return (
    <Section title="🔧 Manual Overrides">
      <p className="text-xs text-gray-400 uppercase tracking-wide font-semibold">Team stat</p>
      <form onSubmit={handleTeamOverride} className="space-y-2">
        <div className="grid grid-cols-3 gap-2">
          <input type="number" placeholder="Team ID" value={teamId} onChange={(e) => setTeamId(e.target.value)} required
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500" />
          <select value={field} onChange={(e) => setField(e.target.value)}
            className="border border-gray-200 rounded-lg px-2 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500">
            {TEAM_FIELDS.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
          <input type="text" placeholder="Value" value={value} onChange={(e) => setValue(e.target.value)} required
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500" />
        </div>
        <button type="submit" disabled={loading}
          className="w-full py-2 rounded-lg bg-amber-500 text-white font-semibold text-sm hover:bg-amber-600 transition-colors disabled:opacity-50">
          Update Team
        </button>
      </form>

      <hr className="border-gray-100" />

      <p className="text-xs text-gray-400 uppercase tracking-wide font-semibold">Player points</p>
      <form onSubmit={handleUserOverride} className="space-y-2">
        <div className="grid grid-cols-2 gap-2">
          <input type="number" placeholder="Player ID" value={userId} onChange={(e) => setUserId(e.target.value)} required
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500" />
          <input type="number" placeholder="Total points" value={userPts} onChange={(e) => setUserPts(e.target.value)} required
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500" />
        </div>
        <button type="submit" disabled={loading}
          className="w-full py-2 rounded-lg bg-amber-500 text-white font-semibold text-sm hover:bg-amber-600 transition-colors disabled:opacity-50">
          Update Player Points
        </button>
      </form>

      <StatusBanner status={status} />
    </Section>
  );
}

// ─── Main page ───────────────────────────────────────────────────────────────
export default function Admin() {
  return (
    <div className="space-y-5">
      <h2 className="text-xl font-bold text-gray-900">Admin Panel</h2>
      <DraftSection />
      <StandingsSection />
      <MatchResultSection />
      <OverridesSection />
    </div>
  );
}
