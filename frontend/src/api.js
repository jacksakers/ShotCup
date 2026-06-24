// src/api.js
// All API calls go through here. During dev, Vite proxies /api -> :8000.
// In production, set VITE_API_URL to your Tailscale URL.

const BASE = import.meta.env.VITE_API_URL ?? '';

function getHeaders(tokenKey = 'site_token') {
  const token = localStorage.getItem(tokenKey);
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function request(method, path, body, tokenKey = 'site_token') {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: getHeaders(tokenKey),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Request failed');
  }
  return res.json();
}

// Auth
export const siteLogin = (password) =>
  request('POST', '/api/auth/site', { password });

export const adminLogin = (password) =>
  request('POST', '/api/auth/admin', { password });

// Users
export const getUsers = () => request('GET', '/api/users');
export const createUser = (username) =>
  request('POST', '/api/users', { username });
export const getUser = (id) => request('GET', `/api/users/${id}`);

// Teams
export const getTeams = () => request('GET', '/api/teams');
export const getTeam = (id) => request('GET', `/api/teams/${id}`);

// Leaderboard
export const getLeaderboard = () => request('GET', '/api/leaderboard');

// Admin
export const runDraft = () =>
  request('POST', '/api/admin/draft', undefined, 'admin_token');

export const parseStandings = (raw_text) =>
  request('POST', '/api/admin/parse-standings', { raw_text }, 'admin_token');

export const submitMatchResult = (data) =>
  request('POST', '/api/admin/match-result', data, 'admin_token');

export const overrideTeam = (id, data) =>
  request('PUT', `/api/admin/teams/${id}`, data, 'admin_token');

export const overrideUserPoints = (id, total_points) =>
  request('PUT', `/api/admin/users/${id}/points`, { total_points }, 'admin_token');

// Trades
export const getTrades = (params = {}) => {
  const qs = new URLSearchParams(
    Object.fromEntries(Object.entries(params).filter(([, v]) => v != null))
  ).toString();
  return request('GET', `/api/trades${qs ? `?${qs}` : ''}`);
};

export const proposeTrade = (data) => request('POST', '/api/trades', data);

export const respondToTrade = (id, user_id, action) =>
  request('PUT', `/api/trades/${id}/respond`, { user_id, action });

export const vetoTrade = (id) =>
  request('DELETE', `/api/admin/trades/${id}`, undefined, 'admin_token');
