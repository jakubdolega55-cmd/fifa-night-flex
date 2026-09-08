import * as SecureStore from 'expo-secure-store';

const TOKEN_KEY = 'fifa-night-controller-token-v1';
const rawBaseUrl = process.env.EXPO_PUBLIC_API_URL ?? '';
export const API_URL = rawBaseUrl.replace(/\/$/, '');

export type Match = {
  match_no: number;
  stage: string;
  stage_label: string;
  group_name?: string | null;
  home_player_id?: string | null;
  away_player_id?: string | null;
  home_name?: string | null;
  away_name?: string | null;
  home_team?: string | null;
  away_team?: string | null;
  home_score?: number | null;
  away_score?: number | null;
  home_penalties?: number | null;
  away_penalties?: number | null;
  played_at?: string | null;
  match_status: string;
  ready: boolean;
};

export type LiveTournament = {
  id: string;
  status: string;
  phase: string;
  is_test: boolean;
  player_count: number;
  format_key: string;
  format_label: string;
  format_matches: string;
  current_match?: Match | null;
  current_context?: any;
  next_match?: Match | null;
  schedule: Match[];
  standings: Record<string, any[]>;
  live_scorers: {name: string; goals: number}[];
  summary?: {champion?: string | null; runner_up?: string | null} | null;
};

export type LiveResponse = {
  server_time: string;
  api_version: string;
  tournament?: LiveTournament | null;
};

async function request<T>(path: string, init: RequestInit = {}, controller = false): Promise<T> {
  if (!API_URL) throw new Error('Brak EXPO_PUBLIC_API_URL. Ustaw adres API w pliku .env.');
  const headers: Record<string, string> = {'Content-Type': 'application/json', ...(init.headers as Record<string, string> ?? {})};
  if (controller) {
    const token = await SecureStore.getItemAsync(TOKEN_KEY);
    if (!token) throw new Error('To urządzenie jest w trybie podglądu.');
    headers.Authorization = `Bearer ${token}`;
  }
  const response = await fetch(`${API_URL}${path}`, {...init, headers});
  let data: any = null;
  try { data = await response.json(); } catch { /* no-op */ }
  if (!response.ok) throw new Error(data?.detail ?? `Błąd API (${response.status})`);
  return data as T;
}

export const api = {
  live: () => request<LiveResponse>('/api/v1/live'),
  playerStats: () => request<any>('/api/v1/stats/players'),
  playerProfile: (playerId: string) => request<any>(`/api/v1/players/${encodeURIComponent(playerId)}`),
  awards: (year: number) => request<any>(`/api/v1/awards/${year}`),
  scorerOptions: (tid: string, no: number) => request<any>(`/api/v1/tournaments/${encodeURIComponent(tid)}/matches/${no}/scorer-options`),
  loginController: async (password: string) => {
    const data = await request<{token: string; expires_at: number}>('/api/v1/auth/controller', {method: 'POST', body: JSON.stringify({password})});
    await SecureStore.setItemAsync(TOKEN_KEY, data.token);
    return data;
  },
  validateController: () => request<{controller: boolean}>('/api/v1/auth/me', {}, true),
  logoutController: () => SecureStore.deleteItemAsync(TOKEN_KEY),
  hasControllerToken: async () => Boolean(await SecureStore.getItemAsync(TOKEN_KEY)),
  saveResult: (tid: string, no: number, payload: any) => request<LiveResponse>(`/api/v1/tournaments/${encodeURIComponent(tid)}/matches/${no}/result`, {method: 'POST', body: JSON.stringify(payload)}, true),
  undoLast: (tid: string) => request<LiveResponse & {undone_match_no?: number}>(`/api/v1/tournaments/${encodeURIComponent(tid)}/undo-last`, {method: 'POST'}, true),
};
