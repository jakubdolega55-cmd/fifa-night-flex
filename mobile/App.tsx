import '@expo/metro-runtime';
import React, {useCallback, useEffect, useRef, useState} from 'react';
import {
  ActivityIndicator,
  Alert,
  Pressable,
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  View,
  Platform,
} from 'react-native';
import {useKeepAwake} from 'expo-keep-awake';
import FifaScreen from './src/FifaScreen';
import StatsScreen from './src/StatsScreen';
import AwardsScreen from './src/AwardsScreen';
import {api, API_URL} from './src/api';
import {LiveResponse} from './src/types';
import {colors} from './src/theme';
import {Btn, Card, ErrorBox, Muted, Pill, ToggleRow} from './src/ui';
import {getStoredItem,setStoredItem} from './src/storage';
import {installWebCompat} from './src/webCompat';

installWebCompat();

type RootTab = 'fifa' | 'stats' | 'awards' | 'settings';
const KEEP_AWAKE_KEY = 'fifa-night-keep-awake-v1';
const APP_VERSION = '1.0.1';

function KeepAwakeGate() {
  useKeepAwake('fifa-night-controller');
  return null;
}

function Header({controller, refreshing, onRefresh}: {controller:boolean; refreshing:boolean; onRefresh:()=>void}) {
  return (
    <View style={s.header}>
      <View>
        <Text style={s.brandTop}>FIFA NIGHT</Text>
        <Text style={s.brand}>FLEX</Text>
      </View>
      <View style={s.headerRight}>
        <Pill text={controller ? '🎮 STEROWANIE' : '👁 PODGLĄD'} tone={controller ? 'green' : 'muted'} />
        <Pressable disabled={refreshing} style={s.refreshBtn} onPress={onRefresh}>
          <Text style={s.refreshText}>{refreshing ? '…' : '↻'}</Text>
        </Pressable>
      </View>
    </View>
  );
}

function SettingsScreen({
  controller,
  setController,
  keepAwake,
  setKeepAwake,
  connectionError,
  onRefresh,
}: {
  controller:boolean;
  setController:(v:boolean)=>void;
  keepAwake:boolean;
  setKeepAwake:(v:boolean)=>void;
  connectionError:string;
  onRefresh:()=>Promise<void>;
}) {
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  const login = async () => {
    if (!password.trim()) return;
    setBusy(true); setMessage('');
    try {
      await api.login(password);
      await api.me();
      setController(true);
      setPassword('');
      setMessage('Sterowanie jest aktywne na tym urządzeniu.');
      await onRefresh();
    } catch (e:any) {
      Alert.alert('Nie udało się włączyć sterowania', e?.message ?? String(e));
    } finally { setBusy(false); }
  };
  const logout = async () => {
    await api.logout();
    setController(false);
    setMessage('To urządzenie działa teraz w trybie podglądu.');
  };
  const changeKeepAwake = async (value:boolean) => {
    setKeepAwake(value);
    await setStoredItem(KEEP_AWAKE_KEY, value ? '1' : '0');
  };

  return (
    <ScrollView contentContainerStyle={s.pad} keyboardShouldPersistTaps="handled">
      <Text style={s.pageTitle}>Ustawienia</Text>
      <Card>
        <View style={s.between}>
          <View style={{flex:1}}>
            <Text style={s.cardTitle}>🎮 Sterowanie</Text>
            <Muted>{controller ? 'Możesz prowadzić oficjalny FIFA Night z tego telefonu.' : 'Podgląd działa bez hasła. Sterowanie jest potrzebne do oficjalnych turniejów i zmian administracyjnych.'}</Muted>
          </View>
          <Pill text={controller ? 'AKTYWNE' : 'PODGLĄD'} tone={controller ? 'green' : 'muted'} />
        </View>
        {!controller ? <>
          <TextInput
            value={password}
            onChangeText={setPassword}
            placeholder="Hasło sterowania"
            placeholderTextColor="#5f748b"
            secureTextEntry
            autoCapitalize="none"
            style={s.input}
            onSubmitEditing={login}
          />
          <Btn title={busy ? 'WŁĄCZAM…' : '🎮 WŁĄCZ STEROWANIE'} disabled={busy || !password.trim()} onPress={login}/>
        </> : <Btn title="WYŁĄCZ STEROWANIE NA TYM URZĄDZENIU" tone="secondary" onPress={logout}/>}        
        {message ? <Text style={s.ok}>{message}</Text> : null}
      </Card>

      <Card>
        <Text style={s.cardTitle}>📱 Ekran telefonu</Text>
        <ToggleRow
          label="Nie wygaszaj ekranu podczas turnieju"
          sub="Działa tylko wtedy, gdy trwa FIFA Night i ten telefon ma sterowanie."
          value={keepAwake}
          onChange={changeKeepAwake}
        />
      </Card>

      <Card>
        <Text style={s.cardTitle}>🌐 Połączenie</Text>
        <View style={s.statusLine}><Text style={s.statusDot}>{connectionError ? '🔴' : '🟢'}</Text><Text style={s.statusText}>{connectionError ? 'Brak połączenia' : 'API działa'}</Text></View>
        {connectionError ? <ErrorBox message={connectionError}/> : null}
        <Muted>{API_URL || 'Brak adresu API'}</Muted>
        <Btn title="↻ SPRAWDŹ TERAZ" tone="secondary" onPress={()=>void onRefresh()}/>
      </Card>

      <Card>
        <Text style={s.cardTitle}>ℹ️ FIFA Night</Text>
        <Muted>Aplikacja {APP_VERSION} • {Platform.OS==='web'?'iPhone / PWA':'Android'}</Muted>
        <Muted>Wyniki i historia są wspólne z wersją Streamlit. Telefon jest pilotem, Neon pamięta resztę.</Muted>
        {Platform.OS==='web'?<><Muted>Na iPhonie otwórz FIFA Night w Safari → Udostępnij → Dodaj do ekranu początkowego. Po instalacji uruchamiaj aplikację z ikony.</Muted><Muted>Wersja web wymaga internetu. Niewygaszanie ekranu zależy od obsługi przez Safari/iOS.</Muted></>:null}
      </Card>
    </ScrollView>
  );
}

const tabs:{key:RootTab; label:string; icon:string}[] = [
  {key:'fifa', label:'FIFA NIGHT', icon:'🎮'},
  {key:'stats', label:'STATYSTYKI', icon:'📊'},
  {key:'awards', label:'AWARDS', icon:'🏆'},
  {key:'settings', label:'USTAWIENIA', icon:'⚙️'},
];

export default function App() {
  const [tab, setTab] = useState<RootTab>('fifa');
  const [live, setLive] = useState<LiveResponse|null>(null);
  const [options, setOptions] = useState<any>(null);
  const [controller, setController] = useState(false);
  const [keepAwake, setKeepAwake] = useState(true);
  const [initializing, setInitializing] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [connectionError, setConnectionError] = useState('');
  const mounted = useRef(true);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      // LIVE is the only request needed for an already active FIFA Night.  Keeping
      // /config out of the polling loop makes warm starts and phone<->TV sync much faster.
      const nextLive = await api.live();
      if (!mounted.current) return;
      setLive(nextLive);
      setConnectionError('');
    } catch (e:any) {
      if (mounted.current) setConnectionError(e?.message ?? String(e));
    } finally {
      if (mounted.current) { setRefreshing(false); setInitializing(false); }
    }
  }, []);

  const loadOptions = useCallback(async () => {
    try {
      const nextOptions=await api.setupOptions();
      if (mounted.current) setOptions(nextOptions);
    } catch (e:any) {
      // /config is only needed when starting a new night.  Do not let a slower
      // config request destabilise the fast LIVE polling loop for an active game.
      if (mounted.current) setConnectionError(prev=>prev || (e?.message ?? String(e)));
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    (async () => {
      try {
        const storedKeep = await getStoredItem(KEEP_AWAKE_KEY);
        if (storedKeep !== null && mounted.current) setKeepAwake(storedKeep !== '0');
        if (await api.hasToken()) {
          try { await api.me(); if (mounted.current) setController(true); }
          catch { await api.logout(); if (mounted.current) setController(false); }
        }
      } finally {
        // Do not make the first screen wait for the relatively heavier setup config.
        // An active tournament can render as soon as /live answers; config loads beside it.
        void loadOptions();
        await refresh();
      }
    })();
    const timer = setInterval(() => { void refresh(); }, 5000);
    return () => { mounted.current = false; clearInterval(timer); };
  }, [refresh, loadOptions]);

  const tournamentActive = live?.tournament?.status === 'active';
  const keepScreenOn = Boolean(keepAwake && controller && tournamentActive);

  return (
    <SafeAreaView style={s.root}>
      <StatusBar barStyle="light-content" backgroundColor={colors.bg}/>
      {keepScreenOn ? <KeepAwakeGate/> : null}
      <Header controller={controller} refreshing={refreshing} onRefresh={()=>void refresh()}/>
      {connectionError && live ? <View style={s.connectionBar}><Text style={s.connectionBarText}>⚠️ Chwilowo bez połączenia. Pokazuję ostatni odczyt.</Text></View> : null}
      <View style={s.content}>
        {(initializing && !live) || (live && !live.tournament && !options) ? (
          <View style={s.loader}><ActivityIndicator color={colors.green} size="large"/><Text style={s.loaderText}>{connectionError?'Próbuję ponownie połączyć…':'Łączę z FIFA Night…'}</Text><Muted center>{!connectionError?'Przy pierwszym wejściu uśpiony serwer może potrzebować chwili na start.':''}</Muted>{connectionError?<ErrorBox message={connectionError}/>:null}</View>
        ) : tab === 'fifa' ? (
          <FifaScreen live={live} options={options ?? {}} controller={controller} refresh={refresh} setBusy={setBusy}/>
        ) : tab === 'stats' ? (
          <StatsScreen controller={controller}/>
        ) : tab === 'awards' ? (
          <AwardsScreen/>
        ) : (
          <SettingsScreen controller={controller} setController={setController} keepAwake={keepAwake} setKeepAwake={setKeepAwake} connectionError={connectionError} onRefresh={refresh}/>
        )}
        {busy ? <View style={s.busyOverlay}><View style={s.busyBox}><ActivityIndicator color={colors.green}/><Text style={s.busyText}>Chwila…</Text></View></View> : null}
      </View>
      <View style={s.bottomNav}>
        {tabs.map(x => <Pressable key={x.key} onPress={()=>setTab(x.key)} style={[s.navItem, tab===x.key && s.navActive]}>
          <Text style={s.navIcon}>{x.icon}</Text><Text style={[s.navText, tab===x.key && s.navTextActive]}>{x.label}</Text>
        </Pressable>)}
      </View>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  root:{flex:1,backgroundColor:colors.bg},
  content:{flex:1},
  header:{minHeight:68,paddingHorizontal:16,paddingVertical:9,borderBottomWidth:1,borderBottomColor:'#13263a',flexDirection:'row',alignItems:'center',justifyContent:'space-between',backgroundColor:'#081421'},
  brandTop:{color:colors.green,fontSize:10,fontWeight:'900',letterSpacing:2},
  brand:{color:colors.text,fontSize:25,fontWeight:'900',letterSpacing:-1},
  headerRight:{flexDirection:'row',alignItems:'center',gap:8},
  refreshBtn:{width:35,height:35,borderRadius:12,backgroundColor:'#102238',borderWidth:1,borderColor:'#263e58',alignItems:'center',justifyContent:'center'},
  refreshText:{color:colors.text,fontSize:20,fontWeight:'800'},
  connectionBar:{backgroundColor:'#3b2e0c',paddingHorizontal:15,paddingVertical:6},
  connectionBarText:{color:colors.amber,fontSize:10,fontWeight:'800',textAlign:'center'},
  bottomNav:{minHeight:69,flexDirection:'row',backgroundColor:'#081421',borderTopWidth:1,borderTopColor:'#1b2d42',paddingHorizontal:4,paddingTop:5,paddingBottom:6},
  navItem:{flex:1,alignItems:'center',justifyContent:'center',borderRadius:12,gap:2},
  navActive:{backgroundColor:'#0e2d2a'},
  navIcon:{fontSize:18},
  navText:{color:'#71869c',fontSize:8.5,fontWeight:'900',letterSpacing:.15},
  navTextActive:{color:colors.green},
  pad:{padding:15,paddingBottom:48,gap:11},
  pageTitle:{color:colors.text,fontSize:27,fontWeight:'900'},
  cardTitle:{color:colors.text,fontSize:16,fontWeight:'900'},
  between:{flexDirection:'row',justifyContent:'space-between',alignItems:'center',gap:10},
  input:{backgroundColor:'#081522',borderWidth:1,borderColor:'#284058',color:colors.text,minHeight:48,borderRadius:13,paddingHorizontal:12,fontSize:14},
  ok:{color:colors.green,fontSize:11,lineHeight:17},
  statusLine:{flexDirection:'row',alignItems:'center',gap:8},
  statusDot:{fontSize:12},statusText:{color:colors.text,fontWeight:'800',fontSize:13},
  loader:{flex:1,padding:30,alignItems:'center',justifyContent:'center',gap:13},
  loaderText:{color:colors.muted,fontWeight:'700'},
  busyOverlay:{...StyleSheet.absoluteFill,backgroundColor:'rgba(4,10,18,.62)',alignItems:'center',justifyContent:'center',zIndex:30},
  busyBox:{backgroundColor:'#0d1a2c',borderWidth:1,borderColor:'#29435e',borderRadius:18,paddingHorizontal:25,paddingVertical:18,alignItems:'center',gap:9},
  busyText:{color:colors.text,fontWeight:'900'},
});
