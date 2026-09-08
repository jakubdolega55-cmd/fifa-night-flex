import React, {useCallback, useEffect, useMemo, useState} from 'react';
import {
  ActivityIndicator,
  Alert,
  Modal,
  Pressable,
  RefreshControl,
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import {api, API_URL, LiveResponse, LiveTournament, Match} from './src/api';
import {colors} from './src/theme';

type Tab = 'live' | 'schedule' | 'stats' | 'awards' | 'more';

type ScorerRow = {name: string; goals: number};

type ScoreModalProps = {
  visible: boolean;
  tournament: LiveTournament | null;
  match: Match | null;
  onClose: () => void;
  onSaved: (data: LiveResponse) => void;
};

const stageIcons: Record<string, string> = {
  GROUP: '◉', LEAGUE: '◉', QF: '◆', BARRAGE: '◆', SF: '◆', FINAL: '★',
  WB: 'W', WB_FINAL: 'W', LB: 'L', LB_FINAL: 'L', DUEL: '⚔', RESET_FINAL: '★',
};

function ErrorBox({message}: {message: string}) {
  return <View style={styles.errorBox}><Text style={styles.errorText}>{message}</Text></View>;
}

function Card({children, style}: {children: React.ReactNode; style?: any}) {
  return <View style={[styles.card, style]}>{children}</View>;
}

function Pill({text, tone = 'muted'}: {text: string; tone?: 'green'|'blue'|'amber'|'red'|'muted'|'purple'}) {
  const bg = tone === 'green' ? '#103a31' : tone === 'blue' ? '#142f50' : tone === 'amber' ? '#3b2e0c' : tone === 'red' ? '#401b29' : tone === 'purple' ? '#332044' : '#182638';
  const fg = tone === 'green' ? colors.green : tone === 'blue' ? colors.blue : tone === 'amber' ? colors.amber : tone === 'red' ? colors.red : tone === 'purple' ? colors.purple : colors.muted;
  return <View style={[styles.pill, {backgroundColor: bg}]}><Text style={[styles.pillText, {color: fg}]}>{text}</Text></View>;
}

function Header({controller}: {controller: boolean}) {
  return (
    <View style={styles.header}>
      <View>
        <Text style={styles.brandEyebrow}>FIFA NIGHT</Text>
        <Text style={styles.brand}>FLEX</Text>
      </View>
      <Pill text={controller ? '🎮 STEROWANIE' : '👁 PODGLĄD'} tone={controller ? 'green' : 'muted'} />
    </View>
  );
}

function EmptyState({title, text}: {title: string; text: string}) {
  return (
    <Card style={styles.emptyCard}>
      <Text style={styles.emptyIcon}>⚽</Text>
      <Text style={styles.sectionTitle}>{title}</Text>
      <Text style={styles.mutedCenter}>{text}</Text>
    </Card>
  );
}

function MatchNames({match, large = false}: {match: Match; large?: boolean}) {
  return (
    <View style={styles.matchTeamsRow}>
      <View style={styles.matchSide}>
        <Text numberOfLines={1} style={large ? styles.playerLarge : styles.player}>{match.home_name ?? '—'}</Text>
        <Text numberOfLines={1} style={styles.team}>{match.home_team ?? '—'}</Text>
      </View>
      <Text style={large ? styles.vsLarge : styles.vs}>VS</Text>
      <View style={styles.matchSide}>
        <Text numberOfLines={1} style={large ? styles.playerLarge : styles.player}>{match.away_name ?? '—'}</Text>
        <Text numberOfLines={1} style={styles.team}>{match.away_team ?? '—'}</Text>
      </View>
    </View>
  );
}

function Standings({standings}: {standings: Record<string, any[]>}) {
  const groups = Object.entries(standings ?? {});
  if (!groups.length) return null;
  return (
    <View style={{gap: 12}}>
      {groups.map(([group, rows]) => (
        <Card key={group}>
          <Text style={styles.cardTitle}>{group === 'L' ? '📊 Tabela' : `📊 Grupa ${group}`}</Text>
          <View style={styles.tableHeader}>
            <Text style={[styles.tableCell, {flex: .35}]}>#</Text><Text style={[styles.tableCell, {flex: 2.1}]}>Gracz</Text><Text style={styles.tableCell}>M</Text><Text style={styles.tableCell}>Pkt</Text><Text style={styles.tableCell}>BR</Text>
          </View>
          {rows.map((r: any, idx: number) => (
            <View style={styles.tableRow} key={String(r.player_id ?? idx)}>
              <Text style={[styles.tableCellStrong, {flex: .35}]}>{idx + 1}</Text>
              <View style={{flex: 2.1}}><Text numberOfLines={1} style={styles.tableCellStrong}>{r.name}</Text><Text numberOfLines={1} style={styles.tableSub}>{r.team}</Text></View>
              <Text style={styles.tableCell}>{r.m ?? 0}</Text><Text style={styles.tableCellStrong}>{r.pts ?? 0}</Text><Text style={styles.tableCell}>{r.gd > 0 ? '+' : ''}{r.gd ?? 0}</Text>
            </View>
          ))}
        </Card>
      ))}
    </View>
  );
}

function LiveScreen({data, controller, refreshing, refresh, openScore}: {data: LiveResponse | null; controller: boolean; refreshing: boolean; refresh: () => void; openScore: () => void}) {
  const t = data?.tournament ?? null;
  if (!t) return <ScrollView refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={colors.green}/>} contentContainerStyle={styles.screenPad}><EmptyState title="Brak aktywnego FIFA Night" text="Gdy organizator uruchomi turniej w Streamlit lub później w aplikacji, ekran LIVE pojawi się tutaj automatycznie." /></ScrollView>;
  const m = t.current_match ?? null;
  const ctx = t.current_context ?? null;

  return (
    <ScrollView refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={colors.green}/>} contentContainerStyle={styles.screenPad}>
      <View style={styles.liveHero}>
        <View style={styles.rowBetween}>
          <Pill text={t.is_test ? '🧪 TEST' : '🏆 OFICJALNY'} tone={t.is_test ? 'amber' : 'green'} />
          <Pill text={`${t.player_count} GRACZY`} tone="blue" />
        </View>
        <Text style={styles.liveFormat}>{t.format_label}</Text>
        <Text style={styles.liveMeta}>{t.format_matches}</Text>
      </View>

      {t.status === 'completed' ? (
        <Card style={styles.championCard}>
          <Text style={styles.championSmall}>MISTRZ FIFA NIGHT</Text>
          <Text style={styles.championIcon}>🏆</Text>
          <Text style={styles.champion}>{t.summary?.champion ?? '—'}</Text>
          {t.summary?.runner_up ? <Text style={styles.mutedCenter}>Finalista: {t.summary.runner_up}</Text> : null}
        </Card>
      ) : m ? (
        <>
          <Text style={styles.kicker}>▶ TERAZ</Text>
          <Card style={styles.currentMatchCard}>
            <View style={styles.rowBetween}>
              <Text style={styles.matchNo}>MECZ {m.match_no}</Text>
              <Pill text={m.stage_label} tone={m.stage === 'FINAL' ? 'amber' : 'purple'} />
            </View>
            <MatchNames match={m} large />
            {ctx ? (
              <View style={styles.contextBox}>
                <Text style={styles.contextText}>H2H: {m.home_name} {ctx.home_wins ?? 0}–{ctx.away_wins ?? 0} {m.away_name} · remisy {ctx.draws ?? 0}</Text>
                <Text style={styles.contextText}>Forma: {m.home_name} {(ctx.home_form ?? []).join('') || '—'} · {m.away_name} {(ctx.away_form ?? []).join('') || '—'}</Text>
              </View>
            ) : null}
            {controller ? <Pressable style={styles.primaryButton} onPress={openScore}><Text style={styles.primaryButtonText}>WPISZ WYNIK</Text></Pressable> : <View style={styles.viewerNote}><Text style={styles.viewerNoteText}>Tryb podglądu · wynik wpisuje urządzenie ze sterowaniem</Text></View>}
          </Card>
        </>
      ) : (
        <EmptyState title="Czekamy na kolejny mecz" text="Para pojawi się automatycznie po rozstrzygnięciu wcześniejszego etapu." />
      )}

      {t.next_match ? (
        <Card>
          <Text style={styles.cardEyebrow}>⏭ NASTĘPNY</Text>
          <MatchNames match={t.next_match} />
        </Card>
      ) : null}

      {t.live_scorers?.length ? (
        <Card>
          <Text style={styles.cardTitle}>⚽ Strzelcy tego FIFA Night</Text>
          <View style={styles.scorerStrip}>
            {t.live_scorers.slice(0, 5).map((s, i) => <View style={styles.scorerTile} key={`${s.name}-${i}`}><Text style={styles.scorerRank}>{i + 1}</Text><Text numberOfLines={1} style={styles.scorerName}>{s.name}</Text><Text style={styles.scorerGoals}>{s.goals}</Text></View>)}
          </View>
        </Card>
      ) : null}

      <Standings standings={t.standings} />
      <Text style={styles.pollHint}>LIVE odświeża się automatycznie co 5 sekund.</Text>
    </ScrollView>
  );
}

function ScheduleScreen({tournament, refreshing, refresh}: {tournament: LiveTournament | null; refreshing: boolean; refresh: () => void}) {
  return (
    <ScrollView refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={colors.green}/>} contentContainerStyle={styles.screenPad}>
      <Text style={styles.pageTitle}>Terminarz</Text>
      <Text style={styles.pageSub}>Kolejność jest dynamiczna i pokazuje faktyczną kolejność gry.</Text>
      {!tournament ? <EmptyState title="Brak turnieju" text="Terminarz pojawi się po uruchomieniu FIFA Night." /> : tournament.schedule.map((m, idx) => {
        const played = m.home_score !== null && m.home_score !== undefined;
        const skipped = m.match_status === 'skipped';
        const locked = !m.home_player_id || !m.away_player_id;
        const status = played ? 'ROZEGRANY' : skipped ? 'POMINIĘTY' : locked ? 'CZEKA' : idx === tournament.schedule.findIndex(x => x.ready) ? 'TERAZ' : 'GOTOWY';
        return (
          <Card key={m.match_no} style={status === 'TERAZ' ? styles.scheduleNow : undefined}>
            <View style={styles.rowBetween}>
              <Text style={styles.matchNo}>MECZ {m.match_no} · {m.stage_label}</Text>
              <Pill text={status} tone={status === 'TERAZ' ? 'green' : played ? 'blue' : skipped ? 'red' : locked ? 'muted' : 'purple'} />
            </View>
            {locked ? <Text style={styles.lockedText}>🔒 Para zależy od wcześniejszego wyniku</Text> : <MatchNames match={m} />}
            {played ? <Text style={styles.scoreLine}>{m.home_score}:{m.away_score}{m.home_penalties !== null && m.home_penalties !== undefined ? `  (k. ${m.home_penalties}:${m.away_penalties})` : ''}</Text> : null}
          </Card>
        );
      })}
    </ScrollView>
  );
}

function ProfileModal({profileData, onClose}: {profileData: any; onClose: () => void}) {
  const p = profileData?.profile;
  const ach = profileData?.achievement;
  return (
    <Modal visible={Boolean(profileData)} animationType="slide" onRequestClose={onClose}>
      <SafeAreaView style={styles.modalPage}>
        <ScrollView contentContainerStyle={styles.screenPad}>
          <View style={styles.rowBetween}><View><Text style={styles.cardEyebrow}>PROFIL GRACZA</Text><Text style={styles.modalTitle}>{p?.name ?? ''}</Text></View><Pressable style={styles.iconButton} onPress={onClose}><Text style={styles.iconButtonText}>✕</Text></Pressable></View>
          {p ? <>
            <View style={styles.metricGrid}>
              <Metric value={p.titles ?? 0} label="Tytuły" />
              <Metric value={p.finals ?? 0} label="Finały" />
              <Metric value={p.matches ?? 0} label="Mecze" />
              <Metric value={`${p.win_pct ?? 0}%`} label="W%" />
            </View>
            <Card><Text style={styles.cardTitle}>🏆 Gablota</Text><Text style={styles.gablotLine}>🏆 Mistrz FIFA Night ×{p.titles ?? 0}</Text><Text style={styles.gablotLine}>🥈 Finał ×{p.finals ?? 0}</Text><Text style={styles.gablotLine}>🏅 Odznaki ×{ach?.count ?? 0}</Text>{profileData?.awards?.map((a: any, i: number) => <Text key={i} style={styles.gablotLine}>✨ {a.name ?? a.category ?? 'FIFA Night Award'} {a.year ? `· ${a.year}` : ''}</Text>)}</Card>
            {ach?.unlocked?.length ? <Card><Text style={styles.cardTitle}>🏅 Odznaki</Text><View style={styles.badgeWrap}>{ach.unlocked.map((a: any) => <View style={styles.badge} key={a.key}><Text style={styles.badgeIcon}>{a.icon}</Text><Text style={styles.badgeText}>{a.name}</Text></View>)}</View></Card> : null}
            {p.teams?.length ? <Card><Text style={styles.cardTitle}>👕 Najczęstsze drużyny</Text>{p.teams.slice(0, 5).map((x: any) => <View key={x.team} style={styles.profileRow}><Text style={styles.profileRowMain}>{x.team}</Text><Text style={styles.profileRowValue}>{x.matches} M · {x.win_pct}% W</Text></View>)}</Card> : null}
            <Card><Text style={styles.cardTitle}>⚔ Rywale</Text><Text style={styles.gablotLine}>Najczęściej: {p.most_frequent?.name ?? '—'}</Text><Text style={styles.gablotLine}>Nemesis: {p.nemesis?.name ?? '—'}</Text><Text style={styles.gablotLine}>Ulubiony rywal: {p.favorite?.name ?? '—'}</Text></Card>
          </> : null}
        </ScrollView>
      </SafeAreaView>
    </Modal>
  );
}

function Metric({value, label}: {value: any; label: string}) {
  return <View style={styles.metric}><Text style={styles.metricValue}>{value}</Text><Text style={styles.metricLabel}>{label}</Text></View>;
}

function StatsScreen() {
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [profile, setProfile] = useState<any>(null);
  const load = useCallback(async () => {
    setError('');
    try { const data = await api.playerStats(); setRows(data.players ?? []); } catch (e: any) { setError(e.message); } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  const openProfile = async (id: string) => {
    try { setProfile(await api.playerProfile(id)); } catch (e: any) { Alert.alert('Błąd', e.message); }
  };
  return (
    <ScrollView contentContainerStyle={styles.screenPad} refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor={colors.green}/>}>
      <Text style={styles.pageTitle}>Statystyki</Text><Text style={styles.pageSub}>Klasyfikacja wszech czasów · oficjalne mecze</Text>
      {error ? <ErrorBox message={error} /> : null}
      {rows.map((r, idx) => (
        <Pressable key={r.player_id} onPress={() => openProfile(r.player_id)}>
          <Card style={styles.playerRankCard}>
            <Text style={styles.rankNo}>{idx + 1}</Text>
            <View style={{flex: 1}}><Text style={styles.rankName}>{r.name}</Text><Text style={styles.tableSub}>{r.matches} M · {r.w}-{r.d}-{r.l} · bilans {r.gd > 0 ? '+' : ''}{r.gd}</Text></View>
            <View style={{alignItems: 'flex-end'}}><Text style={styles.rankTitles}>🏆 {r.titles}</Text><Text style={styles.rankWin}>{r.win_pct}% W</Text></View>
          </Card>
        </Pressable>
      ))}
      <ProfileModal profileData={profile} onClose={() => setProfile(null)} />
    </ScrollView>
  );
}

function AwardsScreen() {
  const year = new Date().getFullYear();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const load = useCallback(async () => { setError(''); try { setData(await api.awards(year)); } catch (e: any) { setError(e.message); } finally { setLoading(false); } }, [year]);
  useEffect(() => { load(); }, [load]);
  return (
    <ScrollView contentContainerStyle={styles.screenPad} refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor={colors.green}/>}>
      <Text style={styles.pageTitle}>AWARDS {year}</Text><Text style={styles.pageSub}>Rankingi LIVE · wybór laureatów nadal zostaje po stronie organizatora.</Text>
      {error ? <ErrorBox message={error} /> : null}
      {data?.categories?.map((c: any) => (
        <Card key={c.key}>
          <Text style={styles.cardTitle}>{c.title ?? c.name ?? 'Nagroda'}</Text>
          {c.description ? <Text style={styles.awardDesc}>{c.description}</Text> : null}
          {(c.candidates ?? []).slice(0, 3).map((x: any, i: number) => <View key={`${c.key}-${i}`} style={styles.awardRow}><Text style={styles.awardPos}>{i + 1}</Text><View style={{flex: 1}}><Text style={styles.awardName}>{x.name}</Text>{(x.reason ?? x.detail) ? <Text style={styles.tableSub}>{x.reason ?? x.detail}</Text> : null}</View></View>)}
          {!(c.candidates ?? []).length ? <Text style={styles.tableSub}>Brak zakwalifikowanych.</Text> : null}
        </Card>
      ))}
    </ScrollView>
  );
}

function MoreScreen({controller, setController, tournament, onLiveChanged}: {controller: boolean; setController: (v: boolean) => void; tournament: LiveTournament | null; onLiveChanged: (d: LiveResponse) => void}) {
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const unlock = async () => {
    if (!password.trim()) return;
    setBusy(true); setError('');
    try { await api.loginController(password); setController(true); setPassword(''); } catch (e: any) { setError(e.message); } finally { setBusy(false); }
  };
  const logout = async () => { await api.logoutController(); setController(false); };
  const undo = () => {
    if (!tournament) return;
    Alert.alert('Cofnąć ostatni wynik?', 'Cofnięty zostanie ostatni faktycznie rozegrany mecz.', [
      {text: 'Anuluj', style: 'cancel'},
      {text: 'Cofnij', style: 'destructive', onPress: async () => { try { const d = await api.undoLast(tournament.id); onLiveChanged(d); } catch (e: any) { Alert.alert('Nie udało się cofnąć', e.message); } }},
    ]);
  };
  return (
    <ScrollView contentContainerStyle={styles.screenPad}>
      <Text style={styles.pageTitle}>Więcej</Text><Text style={styles.pageSub}>Ustawienia urządzenia i sterowanie.</Text>
      <Card>
        <Text style={styles.cardTitle}>🎮 Sterowanie na tym urządzeniu</Text>
        {controller ? <>
          <Pill text="STEROWANIE AKTYWNE" tone="green" />
          <Text style={styles.settingsText}>To urządzenie może wpisywać wyniki. Token sterowania jest zapisany w bezpiecznym magazynie Androida.</Text>
          <Pressable onPress={logout} style={styles.secondaryButton}><Text style={styles.secondaryButtonText}>WYŁĄCZ STEROWANIE</Text></Pressable>
        </> : <>
          <Text style={styles.settingsText}>Domyślnie aplikacja jest tylko do podglądu. Hasło administratora odblokowuje sterowanie na tym urządzeniu.</Text>
          <TextInput value={password} onChangeText={setPassword} secureTextEntry placeholder="Hasło administratora" placeholderTextColor="#61768f" style={styles.input} />
          {error ? <Text style={styles.inlineError}>{error}</Text> : null}
          <Pressable disabled={busy} onPress={unlock} style={[styles.primaryButton, busy && styles.disabled]}><Text style={styles.primaryButtonText}>{busy ? 'SPRAWDZAM…' : 'ODBLOKUJ STEROWANIE'}</Text></Pressable>
        </>}
      </Card>
      {controller && tournament?.status === 'active' ? <Card><Text style={styles.cardTitle}>↩️ Bieżący turniej</Text><Text style={styles.settingsText}>Awaryjne cofnięcie ostatniego faktycznie rozegranego meczu.</Text><Pressable onPress={undo} style={styles.dangerButton}><Text style={styles.dangerButtonText}>COFNIJ OSTATNI WYNIK</Text></Pressable></Card> : null}
      <Card><Text style={styles.cardTitle}>🔌 Połączenie</Text><Text style={styles.settingsText}>API: {API_URL || 'nie ustawiono'}</Text><Text style={styles.settingsText}>Aplikacja: Mobile v0.1</Text><Text style={styles.settingsText}>Odświeżanie LIVE: 5 s</Text></Card>
    </ScrollView>
  );
}

function Stepper({value, onChange, min = 0, max = 99, big = false}: {value: number; onChange: (v: number) => void; min?: number; max?: number; big?: boolean}) {
  return <View style={styles.stepper}><Pressable style={styles.stepButton} onPress={() => onChange(Math.max(min, value - 1))}><Text style={styles.stepButtonText}>−</Text></Pressable><Text style={big ? styles.bigScore : styles.stepValue}>{value}</Text><Pressable style={styles.stepButton} onPress={() => onChange(Math.min(max, value + 1))}><Text style={styles.stepButtonText}>+</Text></Pressable></View>;
}

function ScorerEditor({title, rows, setRows, suggestions}: {title: string; rows: ScorerRow[]; setRows: (r: ScorerRow[]) => void; suggestions: any[]}) {
  const patch = (i: number, v: Partial<ScorerRow>) => setRows(rows.map((r, idx) => idx === i ? {...r, ...v} : r));
  const addSuggestion = (name: string) => {
    const idx = rows.findIndex(r => !r.name.trim());
    if (idx >= 0) patch(idx, {name});
  };
  return <View style={styles.scorerEditor}><Text style={styles.scorerEditorTitle}>{title}</Text>{suggestions?.length ? <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.suggestionRow}>{suggestions.slice(0, 8).map((x: any) => <Pressable key={x.name} onPress={() => addSuggestion(x.name)} style={styles.suggestionChip}><Text style={styles.suggestionText}>{x.name}</Text></Pressable>)}</ScrollView> : null}{rows.map((r, i) => <View key={i} style={styles.scorerInputRow}><TextInput value={r.name} onChangeText={name => patch(i, {name})} placeholder={`Strzelec ${i + 1}`} placeholderTextColor="#61768f" style={[styles.input, {flex: 1, marginBottom: 0}]} /><Stepper value={r.goals} onChange={goals => patch(i, {goals})} max={20} /></View>)}</View>;
}

function ScoreModal({visible, tournament, match, onClose, onSaved}: ScoreModalProps) {
  const wbBonus = Boolean(tournament?.format_key?.startsWith('double') && match?.stage === 'FINAL');
  const [hs, setHs] = useState(wbBonus ? 1 : 0);
  const [as, setAs] = useState(0);
  const [hp, setHp] = useState(4);
  const [ap, setAp] = useState(3);
  const [homeRows, setHomeRows] = useState<ScorerRow[]>([{name: '', goals: 0}, {name: '', goals: 0}, {name: '', goals: 0}]);
  const [awayRows, setAwayRows] = useState<ScorerRow[]>([{name: '', goals: 0}, {name: '', goals: 0}, {name: '', goals: 0}]);
  const [options, setOptions] = useState<any>({home: {options: []}, away: {options: []}});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!visible || !tournament || !match) return;
    setHs(wbBonus ? 1 : 0); setAs(0); setHp(4); setAp(3); setError('');
    setHomeRows([{name: '', goals: 0}, {name: '', goals: 0}, {name: '', goals: 0}]);
    setAwayRows([{name: '', goals: 0}, {name: '', goals: 0}, {name: '', goals: 0}]);
    api.scorerOptions(tournament.id, match.match_no).then(setOptions).catch(() => setOptions({home:{options:[]}, away:{options:[]}}));
  }, [visible, tournament?.id, match?.match_no, wbBonus]);

  if (!match || !tournament) return null;
  const knockout = !['GROUP', 'LEAGUE'].includes(match.stage);
  const needsPens = knockout && hs === as;
  const payloadRows = (rows: ScorerRow[]) => rows.filter(r => r.name.trim() && r.goals > 0).map(r => ({name: r.name.trim(), goals: r.goals}));
  const save = async () => {
    if (needsPens && hp === ap) { setError('Karne muszą wskazać zwycięzcę.'); return; }
    setBusy(true); setError('');
    try {
      const data = await api.saveResult(tournament.id, match.match_no, {
        home_score: hs, away_score: as,
        home_penalties: needsPens ? hp : null,
        away_penalties: needsPens ? ap : null,
        scorers: {
          home: {team: match.home_team ?? '', items: payloadRows(homeRows)},
          away: {team: match.away_team ?? '', items: payloadRows(awayRows)},
        },
      });
      onSaved(data); onClose();
    } catch (e: any) { setError(e.message); } finally { setBusy(false); }
  };

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <SafeAreaView style={styles.modalPage}>
        <ScrollView contentContainerStyle={styles.scoreModalPad} keyboardShouldPersistTaps="handled">
          <View style={styles.rowBetween}><View><Text style={styles.cardEyebrow}>MECZ {match.match_no} · {match.stage_label}</Text><Text style={styles.modalTitle}>Wpisz wynik</Text></View><Pressable style={styles.iconButton} onPress={onClose}><Text style={styles.iconButtonText}>✕</Text></Pressable></View>
          <Card style={styles.scoreCard}>
            <View style={styles.scoreNameRow}><Text numberOfLines={1} style={styles.scorePlayerName}>{match.home_name}</Text><Text style={styles.scoreColon}>:</Text><Text numberOfLines={1} style={styles.scorePlayerName}>{match.away_name}</Text></View>
            <View style={styles.scoreSteppers}><Stepper big value={hs} min={wbBonus ? 1 : 0} onChange={setHs}/><Stepper big value={as} onChange={setAs}/></View>
            {wbBonus ? <Text style={styles.wbNote}>Winners Bracket daje gospodarzowi startowe 1:0. Bonus nie ma strzelca.</Text> : null}
          </Card>
          {needsPens ? <Card><Text style={styles.cardTitle}>🥅 Karne</Text><View style={styles.scoreSteppers}><Stepper value={hp} max={30} onChange={setHp}/><Stepper value={ap} max={30} onChange={setAp}/></View></Card> : null}
          <Text style={styles.sectionTitle}>⚽ Strzelcy <Text style={styles.optional}>opcjonalnie</Text></Text>
          <ScorerEditor title={match.home_team ?? match.home_name ?? 'Gospodarze'} rows={homeRows} setRows={setHomeRows} suggestions={options?.home?.options ?? []}/>
          <ScorerEditor title={match.away_team ?? match.away_name ?? 'Goście'} rows={awayRows} setRows={setAwayRows} suggestions={options?.away?.options ?? []}/>
          {error ? <ErrorBox message={error} /> : null}
          <Pressable disabled={busy} onPress={save} style={[styles.primaryButton, styles.saveButton, busy && styles.disabled]}><Text style={styles.primaryButtonText}>{busy ? 'ZAPISUJĘ…' : needsPens ? 'ZAPISZ WYNIK I KARNE' : 'ZAPISZ WYNIK'}</Text></Pressable>
          <Text style={styles.pollHint}>Po zapisie Neon, aplikacje znajomych i Streamlit TV zobaczą ten sam wynik.</Text>
        </ScrollView>
      </SafeAreaView>
    </Modal>
  );
}

function BottomNav({tab, setTab}: {tab: Tab; setTab: (t: Tab) => void}) {
  const items: {key: Tab; icon: string; label: string}[] = [
    {key: 'live', icon: '●', label: 'LIVE'},
    {key: 'schedule', icon: '▦', label: 'Terminarz'},
    {key: 'stats', icon: '▥', label: 'Staty'},
    {key: 'awards', icon: '🏆', label: 'Awards'},
    {key: 'more', icon: '•••', label: 'Więcej'},
  ];
  return <View style={styles.bottomNav}>{items.map(item => <Pressable key={item.key} onPress={() => setTab(item.key)} style={styles.navItem}><Text style={[styles.navIcon, tab === item.key && styles.navActive]}>{item.icon}</Text><Text style={[styles.navLabel, tab === item.key && styles.navActive]}>{item.label}</Text></Pressable>)}</View>;
}

export default function App() {
  const [tab, setTab] = useState<Tab>('live');
  const [live, setLive] = useState<LiveResponse | null>(null);
  const [controller, setController] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [error, setError] = useState('');
  const [scoreOpen, setScoreOpen] = useState(false);

  const refresh = useCallback(async (quiet = false) => {
    if (!quiet) setRefreshing(true);
    try { const data = await api.live(); setLive(data); setError(''); } catch (e: any) { setError(e.message); } finally { setRefreshing(false); setInitialLoading(false); }
  }, []);

  useEffect(() => {
    api.hasControllerToken().then(async has => {
      if (!has) return setController(false);
      try { await api.validateController(); setController(true); } catch { await api.logoutController(); setController(false); }
    });
    refresh();
    const id = setInterval(() => refresh(true), 5000);
    return () => clearInterval(id);
  }, [refresh]);

  const t = live?.tournament ?? null;
  const content = useMemo(() => {
    if (initialLoading) return <View style={styles.loading}><ActivityIndicator color={colors.green} size="large"/><Text style={styles.loadingText}>Łączę z FIFA Night…</Text></View>;
    if (error && !live) return <View style={styles.screenPad}><ErrorBox message={error}/><Pressable onPress={() => refresh()} style={styles.primaryButton}><Text style={styles.primaryButtonText}>SPRÓBUJ PONOWNIE</Text></Pressable></View>;
    if (tab === 'schedule') return <ScheduleScreen tournament={t} refreshing={refreshing} refresh={() => refresh()} />;
    if (tab === 'stats') return <StatsScreen />;
    if (tab === 'awards') return <AwardsScreen />;
    if (tab === 'more') return <MoreScreen controller={controller} setController={setController} tournament={t} onLiveChanged={setLive} />;
    return <LiveScreen data={live} controller={controller} refreshing={refreshing} refresh={() => refresh()} openScore={() => setScoreOpen(true)} />;
  }, [initialLoading, error, live, tab, controller, refreshing, refresh, t]);

  return (
    <SafeAreaView style={styles.root}>
      <StatusBar barStyle="light-content" backgroundColor={colors.bg}/>
      <Header controller={controller}/>
      {error && live ? <View style={styles.connectionBanner}><Text style={styles.connectionBannerText}>⚠ Ostatnie odświeżenie nieudane · pokazuję poprzedni stan</Text></View> : null}
      <View style={styles.content}>{content}</View>
      <BottomNav tab={tab} setTab={setTab}/>
      <ScoreModal visible={scoreOpen} tournament={t} match={t?.current_match ?? null} onClose={() => setScoreOpen(false)} onSaved={setLive}/>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: {flex: 1, backgroundColor: colors.bg},
  content: {flex: 1},
  header: {paddingHorizontal: 18, paddingTop: 8, paddingBottom: 10, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderBottomWidth: 1, borderBottomColor: '#13263a'},
  brandEyebrow: {color: colors.green, fontSize: 11, letterSpacing: 3.2, fontWeight: '900'},
  brand: {color: colors.text, fontSize: 24, fontWeight: '900', letterSpacing: 1},
  screenPad: {padding: 16, paddingBottom: 40, gap: 12},
  scoreModalPad: {padding: 16, paddingBottom: 70, gap: 14},
  card: {backgroundColor: colors.panel, borderRadius: 20, borderWidth: 1, borderColor: colors.border, padding: 16, gap: 10},
  liveHero: {backgroundColor: '#0c2232', padding: 18, borderRadius: 24, borderWidth: 1, borderColor: '#16445a', gap: 8},
  liveFormat: {color: colors.text, fontSize: 24, lineHeight: 29, fontWeight: '900', marginTop: 8},
  liveMeta: {color: colors.muted, fontSize: 13},
  rowBetween: {flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 10},
  pill: {paddingHorizontal: 10, paddingVertical: 6, borderRadius: 999, alignSelf: 'flex-start'},
  pillText: {fontSize: 10, fontWeight: '900', letterSpacing: .8},
  kicker: {color: colors.green, fontSize: 13, fontWeight: '900', letterSpacing: 2, marginTop: 4},
  currentMatchCard: {backgroundColor: '#0f2134', borderColor: '#245178'},
  matchNo: {color: colors.muted, fontSize: 11, fontWeight: '800', letterSpacing: .6},
  matchTeamsRow: {flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8, paddingVertical: 8},
  matchSide: {flex: 1, alignItems: 'center'},
  playerLarge: {color: colors.text, fontSize: 24, fontWeight: '900', textAlign: 'center'},
  player: {color: colors.text, fontSize: 17, fontWeight: '900', textAlign: 'center'},
  team: {color: colors.muted, fontSize: 12, textAlign: 'center', marginTop: 3},
  vsLarge: {color: '#4d6680', fontSize: 18, fontWeight: '900'},
  vs: {color: '#4d6680', fontSize: 13, fontWeight: '900'},
  contextBox: {backgroundColor: '#091725', borderRadius: 14, padding: 11, gap: 5},
  contextText: {color: '#9fb3c8', fontSize: 11, lineHeight: 16},
  primaryButton: {backgroundColor: colors.green, minHeight: 50, borderRadius: 15, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 14},
  primaryButtonText: {color: '#052017', fontWeight: '900', letterSpacing: .7, fontSize: 13},
  secondaryButton: {borderWidth: 1, borderColor: '#3d5976', minHeight: 48, borderRadius: 15, alignItems: 'center', justifyContent: 'center'},
  secondaryButtonText: {color: colors.text, fontWeight: '900', fontSize: 12},
  dangerButton: {backgroundColor: '#391b27', borderWidth: 1, borderColor: '#6b263d', minHeight: 48, borderRadius: 15, alignItems: 'center', justifyContent: 'center'},
  dangerButtonText: {color: colors.red, fontWeight: '900', fontSize: 12},
  viewerNote: {padding: 11, backgroundColor: '#101a27', borderRadius: 13},
  viewerNoteText: {color: colors.muted, textAlign: 'center', fontSize: 11},
  cardEyebrow: {color: colors.cyan, fontWeight: '900', fontSize: 11, letterSpacing: 1.2},
  cardTitle: {color: colors.text, fontSize: 16, fontWeight: '900'},
  scorerStrip: {gap: 7},
  scorerTile: {flexDirection: 'row', alignItems: 'center', backgroundColor: colors.panel2, borderRadius: 12, paddingVertical: 9, paddingHorizontal: 10},
  scorerRank: {color: colors.muted, width: 24, fontWeight: '900'},
  scorerName: {color: colors.text, flex: 1, fontWeight: '800'},
  scorerGoals: {color: colors.green, fontSize: 18, fontWeight: '900'},
  tableHeader: {flexDirection: 'row', paddingBottom: 7, borderBottomWidth: 1, borderBottomColor: colors.border},
  tableRow: {flexDirection: 'row', alignItems: 'center', paddingVertical: 9, borderBottomWidth: 1, borderBottomColor: '#16273a'},
  tableCell: {flex: .8, color: colors.muted, fontSize: 11, textAlign: 'center'},
  tableCellStrong: {color: colors.text, fontSize: 12, fontWeight: '800', textAlign: 'center'},
  tableSub: {color: colors.muted, fontSize: 10, marginTop: 2},
  pollHint: {color: '#5d738c', fontSize: 10, textAlign: 'center', marginTop: 2},
  emptyCard: {alignItems: 'center', paddingVertical: 34},
  emptyIcon: {fontSize: 40, marginBottom: 3},
  sectionTitle: {color: colors.text, fontSize: 18, fontWeight: '900'},
  mutedCenter: {color: colors.muted, textAlign: 'center', lineHeight: 20},
  championCard: {backgroundColor: '#2c2409', borderColor: '#6c5913', alignItems: 'center', paddingVertical: 30},
  championSmall: {color: colors.amber, fontSize: 11, fontWeight: '900', letterSpacing: 2},
  championIcon: {fontSize: 42},
  champion: {color: colors.text, fontSize: 30, fontWeight: '900'},
  pageTitle: {color: colors.text, fontSize: 28, fontWeight: '900'},
  pageSub: {color: colors.muted, fontSize: 12, lineHeight: 18, marginBottom: 6},
  scheduleNow: {borderColor: '#2a9b74', backgroundColor: '#0d2928'},
  lockedText: {color: colors.muted, fontSize: 12, paddingVertical: 8},
  scoreLine: {color: colors.text, textAlign: 'center', fontWeight: '900', fontSize: 22},
  playerRankCard: {flexDirection: 'row', alignItems: 'center', gap: 12},
  rankNo: {color: colors.green, fontSize: 24, fontWeight: '900', width: 30},
  rankName: {color: colors.text, fontSize: 18, fontWeight: '900'},
  rankTitles: {color: colors.amber, fontWeight: '900', fontSize: 14},
  rankWin: {color: colors.green, fontWeight: '900', fontSize: 12, marginTop: 3},
  metricGrid: {flexDirection: 'row', flexWrap: 'wrap', gap: 8},
  metric: {width: '48%', backgroundColor: colors.panel, borderRadius: 16, padding: 14, borderWidth: 1, borderColor: colors.border},
  metricValue: {color: colors.text, fontSize: 23, fontWeight: '900'},
  metricLabel: {color: colors.muted, fontSize: 11, marginTop: 3},
  gablotLine: {color: '#cbd8e6', fontSize: 13, lineHeight: 21},
  badgeWrap: {flexDirection: 'row', flexWrap: 'wrap', gap: 8},
  badge: {width: '48%', backgroundColor: '#142135', borderRadius: 14, padding: 11, minHeight: 76},
  badgeIcon: {fontSize: 22},
  badgeText: {color: colors.text, fontSize: 11, fontWeight: '800', marginTop: 5},
  profileRow: {flexDirection: 'row', justifyContent: 'space-between', gap: 10, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#16273a'},
  profileRowMain: {color: colors.text, fontWeight: '800', flex: 1},
  profileRowValue: {color: colors.muted, fontSize: 11},
  awardDesc: {color: colors.muted, fontSize: 11, lineHeight: 17},
  awardRow: {flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8, borderTopWidth: 1, borderTopColor: '#16273a'},
  awardPos: {width: 26, color: colors.green, fontWeight: '900', fontSize: 18},
  awardName: {color: colors.text, fontWeight: '800', fontSize: 14},
  settingsText: {color: colors.muted, fontSize: 12, lineHeight: 19},
  input: {backgroundColor: '#081522', borderWidth: 1, borderColor: '#284058', color: colors.text, minHeight: 48, borderRadius: 14, paddingHorizontal: 13, fontSize: 14, marginBottom: 3},
  inlineError: {color: colors.red, fontSize: 12},
  connectionBanner: {backgroundColor: '#382b0d', paddingVertical: 6, paddingHorizontal: 12},
  connectionBannerText: {color: colors.amber, textAlign: 'center', fontSize: 10, fontWeight: '700'},
  bottomNav: {height: 68, borderTopWidth: 1, borderTopColor: '#172b40', backgroundColor: '#081421', flexDirection: 'row', alignItems: 'center', justifyContent: 'space-around', paddingBottom: 4},
  navItem: {flex: 1, alignItems: 'center', gap: 3},
  navIcon: {color: '#60778f', fontSize: 18, fontWeight: '900'},
  navLabel: {color: '#60778f', fontSize: 9, fontWeight: '800'},
  navActive: {color: colors.green},
  modalPage: {flex: 1, backgroundColor: colors.bg},
  modalTitle: {color: colors.text, fontSize: 28, fontWeight: '900'},
  iconButton: {width: 42, height: 42, borderRadius: 14, backgroundColor: colors.panel, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: colors.border},
  iconButtonText: {color: colors.text, fontSize: 18, fontWeight: '900'},
  scoreCard: {backgroundColor: '#0d2033'},
  scoreNameRow: {flexDirection: 'row', alignItems: 'center', gap: 8},
  scorePlayerName: {flex: 1, color: colors.text, fontSize: 16, fontWeight: '900', textAlign: 'center'},
  scoreColon: {color: colors.muted, fontSize: 20, fontWeight: '900'},
  scoreSteppers: {flexDirection: 'row', justifyContent: 'space-around', gap: 16},
  stepper: {flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10},
  stepButton: {width: 42, height: 42, borderRadius: 13, backgroundColor: '#18304a', borderWidth: 1, borderColor: '#2b4a67', alignItems: 'center', justifyContent: 'center'},
  stepButtonText: {color: colors.text, fontSize: 23, fontWeight: '900'},
  stepValue: {minWidth: 34, color: colors.text, fontSize: 23, fontWeight: '900', textAlign: 'center'},
  bigScore: {minWidth: 38, color: colors.text, fontSize: 42, fontWeight: '900', textAlign: 'center'},
  wbNote: {color: colors.amber, fontSize: 10, textAlign: 'center', lineHeight: 15},
  optional: {color: colors.muted, fontSize: 12, fontWeight: '500'},
  scorerEditor: {backgroundColor: colors.panel, borderWidth: 1, borderColor: colors.border, borderRadius: 18, padding: 13, gap: 10},
  scorerEditorTitle: {color: colors.text, fontSize: 15, fontWeight: '900'},
  suggestionRow: {gap: 7, paddingVertical: 2},
  suggestionChip: {backgroundColor: '#182b41', paddingHorizontal: 10, paddingVertical: 7, borderRadius: 999},
  suggestionText: {color: '#bfd0e1', fontSize: 10, fontWeight: '700'},
  scorerInputRow: {flexDirection: 'row', gap: 8, alignItems: 'center'},
  saveButton: {marginTop: 5, minHeight: 56},
  disabled: {opacity: .55},
  errorBox: {backgroundColor: '#3b1723', borderWidth: 1, borderColor: '#6f293e', borderRadius: 14, padding: 12},
  errorText: {color: '#fda4af', fontSize: 12, lineHeight: 18},
  loading: {flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12},
  loadingText: {color: colors.muted, fontSize: 12},
});
