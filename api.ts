import * as SecureStore from 'expo-secure-store';
import {LiveResponse, SetupResponse} from './types';

const TOKEN_KEY = 'fifa-night-controller-token-v1';
const rawBaseUrl = process.env.EXPO_PUBLIC_API_URL ?? '';
export const API_URL = rawBaseUrl.replace(/\/$/, '');

async function tokenHeader(): Promise<Record<string,string>> {
  const token = await SecureStore.getItemAsync(TOKEN_KEY);
  return token ? {Authorization:`Bearer ${token}`} : {};
}

async function jsonRequest<T>(path:string, init:RequestInit={}):Promise<T> {
  if (!API_URL) throw new Error('Brak EXPO_PUBLIC_API_URL.');
  const auth = await tokenHeader();
  const headers:Record<string,string> = {'Content-Type':'application/json', ...auth, ...((init.headers as Record<string,string>) ?? {})};
  const r = await fetch(`${API_URL}${path}`, {...init, headers});
  let data:any = null;
  try { data = await r.json(); } catch {}
  if (!r.ok) throw new Error(data?.detail ?? `Błąd API (${r.status})`);
  return data as T;
}

async function formRequest<T>(path:string, form:FormData):Promise<T> {
  if (!API_URL) throw new Error('Brak EXPO_PUBLIC_API_URL.');
  const auth = await tokenHeader();
  const r = await fetch(`${API_URL}${path}`, {method:'POST', headers:auth, body:form});
  let data:any = null;
  try { data = await r.json(); } catch {}
  if (!r.ok) throw new Error(data?.detail ?? `Błąd API (${r.status})`);
  return data as T;
}

export const api = {
  health:()=>jsonRequest<any>('/api/v1/health'),
  live:()=>jsonRequest<LiveResponse>('/api/v1/live'),
  setupOptions:()=>jsonRequest<any>('/api/v1/config'),
  setup:(tid:string)=>jsonRequest<SetupResponse>(`/api/v1/tournaments/${encodeURIComponent(tid)}/setup`),

  // The screen uses a friendly payload; normalize it here to the API contract.
  createTournament:(payload:any)=>jsonRequest<any>('/api/v1/tournaments',{
    method:'POST',
    body:JSON.stringify(payload?.players ? {
      player_names: payload.players.map((p:any)=>String(p.name||'')),
      player_count: Number(payload.player_count),
      format_key: String(payload.format_key||''),
      is_test: Boolean(payload.is_test),
      stake_per_player: Number(payload.stake_per_player||0),
      cash_flags: payload.players.map((p:any)=>Boolean(p.cash)),
    } : payload),
  }),
  createDuel:(payload:any)=>jsonRequest<any>('/api/v1/duels',{
    method:'POST',
    body:JSON.stringify(payload?.player1 !== undefined ? {
      player_names:[String(payload.player1||''),String(payload.player2||'')],
      team_names:[String(payload.team1||''),String(payload.team2||'')],
      stake_per_player:Number(payload.stake_per_player||0),
      cash_flags:[Boolean(payload.cash1),Boolean(payload.cash2)],
    } : payload),
  }),

  draftReveal:(tid:string)=>jsonRequest<SetupResponse>(`/api/v1/tournaments/${tid}/draft/reveal`,{method:'POST'}),
  draftReroll:(tid:string)=>jsonRequest<SetupResponse>(`/api/v1/tournaments/${tid}/draft/reroll`,{method:'POST'}),
  draftConfirm:(tid:string)=>jsonRequest<SetupResponse>(`/api/v1/tournaments/${tid}/draft/confirm`,{method:'POST'}),
  draftPick:(tid:string,payload:any)=>jsonRequest<SetupResponse>(`/api/v1/tournaments/${tid}/draft/pick`,{method:'POST',body:JSON.stringify(payload)}),
  teamReveal:(tid:string)=>jsonRequest<any>(`/api/v1/tournaments/${tid}/teams/reveal`,{method:'POST'}),
  wildcard:(tid:string,payload:any)=>jsonRequest<any>(`/api/v1/tournaments/${tid}/wildcard/confirm`,{method:'POST',body:JSON.stringify(payload)}),
  structureStart:(tid:string)=>jsonRequest<SetupResponse>(`/api/v1/tournaments/${tid}/teams/finish`,{method:'POST'}),
  structureReveal:(tid:string)=>jsonRequest<SetupResponse>(`/api/v1/tournaments/${tid}/structure/reveal`,{method:'POST'}),
  structureReroll:(tid:string)=>jsonRequest<SetupResponse>(`/api/v1/tournaments/${tid}/structure/reroll`,{method:'POST'}),
  structureConfirm:(tid:string)=>jsonRequest<LiveResponse>(`/api/v1/tournaments/${tid}/structure/confirm`,{method:'POST'}),
  specialReveal:(tid:string,kind:string)=>jsonRequest<any>(`/api/v1/tournaments/${tid}/special/${encodeURIComponent(kind)}/reveal`,{method:'POST'}),
  specialAck:(tid:string,kind:string)=>jsonRequest<LiveResponse>(`/api/v1/tournaments/${tid}/special/${encodeURIComponent(kind)}/ack`,{method:'POST'}),

  scorerOptions:(tid:string,no:number)=>jsonRequest<any>(`/api/v1/tournaments/${tid}/matches/${no}/scorer-options`),
  addScorer:(tid:string,no:number,side:'home'|'away',name:string)=>jsonRequest<any>(`/api/v1/tournaments/${tid}/matches/${no}/scorers`,{method:'POST',body:JSON.stringify({side,name})}),
  saveResult:(tid:string,no:number,payload:any)=>jsonRequest<LiveResponse>(`/api/v1/tournaments/${tid}/matches/${no}/result`,{method:'POST',body:JSON.stringify(payload)}),
  undo:(tid:string)=>jsonRequest<any>(`/api/v1/tournaments/${tid}/undo-last`,{method:'POST'}),
  defer:(tid:string,no:number)=>jsonRequest<LiveResponse>(`/api/v1/tournaments/${tid}/matches/${no}/defer`,{method:'POST'}),
  skip:(tid:string,no:number)=>jsonRequest<LiveResponse>(`/api/v1/tournaments/${tid}/matches/${no}/skip`,{method:'POST'}),
  setMode:(tid:string,is_test:boolean)=>jsonRequest<LiveResponse>(`/api/v1/tournaments/${tid}/test-mode`,{method:'POST',body:JSON.stringify({is_test})}),
  reset:(tid:string)=>jsonRequest<LiveResponse>(`/api/v1/tournaments/${tid}/reset`,{method:'POST'}),
  abandon:(tid:string)=>jsonRequest<any>(`/api/v1/tournaments/${tid}/abandon`,{method:'POST'}),
  startNew:(tid:string)=>jsonRequest<LiveResponse>(`/api/v1/tournaments/${tid}/new`,{method:'POST'}),

  scanMatch:async(tid:string,no:number,uris:string[])=>{
    const form = new FormData();
    uris.forEach((uri,i)=>form.append('images',{uri,name:`ea-fc-${i+1}.jpg`,type:'image/jpeg'} as any));
    return formRequest<any>(`/api/v1/tournaments/${tid}/matches/${no}/scan-preview`,form);
  },

  playerStats:()=>jsonRequest<any>('/api/v1/stats/players'),
  records:()=>jsonRequest<any>('/api/v1/stats/records'),
  teamStats:()=>jsonRequest<any>('/api/v1/stats/teams'),
  scorerStats:()=>jsonRequest<any>('/api/v1/stats/scorers'),
  player:(id:string)=>jsonRequest<any>(`/api/v1/players/${encodeURIComponent(id)}`),
  history:(includeTests=false)=>jsonRequest<any>(`/api/v1/history?include_tests=${includeTests?'true':'false'}`),
  historyDetail:(id:string)=>jsonRequest<any>(`/api/v1/history/${encodeURIComponent(id)}`),
  deleteHistory:(id:string)=>jsonRequest<any>(`/api/v1/history/${encodeURIComponent(id)}`,{method:'DELETE'}),
  finance:()=>jsonRequest<any>('/api/v1/finance/tournaments'),
  settlement:(ids:string[])=>jsonRequest<any>('/api/v1/finance/settlement',{method:'POST',body:JSON.stringify({tournament_ids:ids})}),
  markSettled:(ids:string[],settled=true)=>jsonRequest<any>('/api/v1/finance/settled',{method:'POST',body:JSON.stringify({tournament_ids:ids,settled})}),
  awards:(year:number)=>jsonRequest<any>(`/api/v1/awards/${year}`),
  milestones:()=>jsonRequest<any>('/api/v1/milestones'),

  login:async(password:string)=>{
    const d=await jsonRequest<{token:string}>('/api/v1/auth/controller',{method:'POST',body:JSON.stringify({password})});
    await SecureStore.setItemAsync(TOKEN_KEY,d.token);
    return d;
  },
  me:()=>jsonRequest<any>('/api/v1/auth/me'),
  logout:()=>SecureStore.deleteItemAsync(TOKEN_KEY),
  hasToken:async()=>Boolean(await SecureStore.getItemAsync(TOKEN_KEY)),
  token:()=>SecureStore.getItemAsync(TOKEN_KEY),
};

export async function authHeaders(){return tokenHeader();}
