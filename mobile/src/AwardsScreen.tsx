import React,{useEffect,useMemo,useState} from 'react';
import {Alert,Pressable,ScrollView,StyleSheet,Text,View} from 'react-native';
import {api} from './api';
import {getPng} from './export';
import {colors} from './theme';
import {Btn,Card,Chip,ErrorBox,HScroll,Metric,Muted,Pill} from './ui';

type Mode='awards'|'classifications'|'milestones'|'gala';
const fmtDay=(v:any)=>{const s=String(v||'');if(!s)return 'Bez daty';const d=s.slice(0,10).split('-');return d.length===3?`${d[2]}-${d[1]}-${d[0]}`:s.slice(0,10)};
const AWARD_QUIPS:Record<string,string>={
  player_year:'Tu wymówki kończą się na wejściu.',
  offensive:'Obrona rywala miała inne plany.',
  defense:'Parking autobusu, tylko skuteczny.',
  clutch:'Tu zaczyna się futbol bez drugiej szansy.',
  comeback_king:'Najpierw problem, potem kino.',
  late_king:'90. minuta to sugestia, nie koniec meczu.',
  sharpest:'Sędzia też ma swoją tabelę.',
  fair_play:'Da się grać bez kolekcjonowania kartek.',
  spectacle:'Spokojne 1:0? Nie tutaj.',
  finance:'Excel też potrafi boleć.',
  match_year:'Ten mecz jeszcze długo będzie wracał przy stole.',
  minimalist:'Po co strzelać pięć, skoro jeden wystarczy?',
  unlucky:'Prawie się nie liczy. Niestety.',
  simulator:'Kontakt był. Oczywiście że był.',
  penaldo:'Wapno znalezione, reszta to formalność.',
  own_goals:'Czasem trzeba pomóc przeciwnikowi.',
  penalty_misses:'Presja? Jaka presja?',
};

function CategoryCards({categories,award}:{categories:any[];award:boolean}){
  if(!categories.length)return <Card><Text style={s.empty}>Na razie pusto. Sezon jeszcze zbiera materiał.</Text></Card>;
  return <View style={{gap:10}}>{categories.map((c:any)=><Card key={c.key}>
    <View style={s.between}><Text style={s.cardTitle}>{c.title}</Text><Pill text={award?'KANDYDACI • TOP 5':'BEZ STATUETKI'} tone={award?'green':'muted'}/></View>
    {award&&c.engraving?<Text style={s.engraving}>🏷️ GRAWER • {c.engraving}</Text>:null}
    <Muted>{c.description}</Muted>
    {AWARD_QUIPS[c.key]?<Text style={s.quip}>{AWARD_QUIPS[c.key]}</Text>:null}
    {(c.candidates||[]).length?(c.candidates||[]).slice(0,5).map((x:any,i:number)=><View key={`${x.id}-${i}`} style={s.candidate}><Text style={s.pos}>{i+1}</Text><View style={{flex:1}}><Text style={s.name}>{x.name}</Text>{x.reason?<Text style={s.reason}>{x.reason}</Text>:null}</View></View>):<Text style={s.reason}>Jeszcze za mało danych, żeby ustawić kolejność.</Text>}
    {c.secondary?<Text style={s.secondary}>{c.key==='finance'?'📉 Drugi koniec tabeli':c.key==='team_best'?'📉 Na drugim biegunie':'Druga strona'}: <Text style={{fontWeight:'900'}}>{c.secondary.name}</Text>{c.secondary.reason?` • ${c.secondary.reason}`:''}</Text>:null}
  </Card>)}</View>;
}

function AwardsYear({year,mode}:{year:number;mode:'awards'|'classifications'}){
  const [d,setD]=useState<any>(null),[err,setErr]=useState('');
  useEffect(()=>{setD(null);setErr('');api.awards(year).then(setD).catch(x=>setErr(x.message))},[year]);
  const png=async(which:'awards'|'year',action:'save'|'share')=>{try{await getPng(which==='awards'?`/api/v1/exports/year/${year}/awards.png`:`/api/v1/exports/year/${year}/summary.png`,which==='awards'?`fifa-night-awards-${year}.png`:`fifa-night-${year}-rok.png`,action)}catch(e:any){Alert.alert('Błąd',e.message)}};
  const cats=(d?.categories||[]).filter((c:any)=>mode==='awards'?c.award!==false:c.award===false);
  return <View style={{gap:10}}>{err?<ErrorBox message={err}/>:null}{d?<>
    {mode==='awards'?<Card style={s.hero}><Pill text={`AWARDS ${year}`} tone="amber"/><Text style={s.heroTitle}>🏅 Kandydaci LIVE — TOP 5</Text><Muted>TOP 5 układają wyniki. Laureata wybiera organizator. VAR-u, komisji odwoławczej i protestów po ceremonii nie przewidziano 😎</Muted></Card>:<Card style={s.classHero}><Pill text="KLASYFIKACJE" tone="purple"/><Text style={s.heroTitle}>Dodatkowe tabele sezonu</Text><Muted>Bez statuetek i bez napinki. Za to z samobójami, karnymi, Wild Cardami i innymi rzeczami, które liczby pamiętają aż za dobrze.</Muted></Card>}
    <View style={s.metrics}><Metric value={d.overview?.tournaments??0} label="Turnieje"/><Metric value={d.overview?.matches??0} label="Mecze"/><Metric value={d.overview?.goals??0} label="Gole"/><Metric value={d.overview?.players??0} label="Gracze"/></View>
    <CategoryCards categories={cats} award={mode==='awards'}/>
    {mode==='awards'?<Card><Text style={s.cardTitle}>🖼️ Grafiki roczne</Text><View style={s.rowWrap}><View style={s.half}><Btn title="💾 ZAPISZ ROK" tone="secondary" onPress={()=>png('year','save')}/></View><View style={s.half}><Btn title="📤 UDOSTĘPNIJ ROK" tone="secondary" onPress={()=>png('year','share')}/></View><View style={s.half}><Btn title="💾 ZAPISZ AWARDS" tone="secondary" onPress={()=>png('awards','save')}/></View><View style={s.half}><Btn title="📤 UDOSTĘPNIJ AWARDS" tone="secondary" onPress={()=>png('awards','share')}/></View></View><Muted>Grafika Awards pokaże laureatów wybranych przez organizatora w wersji webowej.</Muted></Card>:null}
  </>:<Text style={s.reason}>Ładowanie…</Text>}</View>;
}

function GalaControl({year}:{year:number}){
  const [d,setD]=useState<any>(null),[err,setErr]=useState(''),[busy,setBusy]=useState(false);
  const load=async()=>{try{setErr('');setD(await api.gala(year))}catch(e:any){setErr(e?.message||String(e))}};
  useEffect(()=>{setD(null);void load();const t=setInterval(()=>void load(),1000);return()=>clearInterval(t)},[year]);
  const act=async(fn:()=>Promise<any>)=>{if(busy)return;setBusy(true);try{setErr('');setD(await fn())}catch(e:any){setErr(e?.message||String(e))}finally{setBusy(false)}};
  const status=String(d?.status||'idle'),phase=String(d?.display_phase||status);
  const current=d?.current_category;
  const idx=Number(d?.current_index??-1);
  const total=Number(d?.total_categories||18);
  const hold=phase==='winner_hold';
  const canMain=status==='idle'||status==='finished'||status==='finale'||hold;
  const mainTitle=status==='idle'||status==='finished'?'▶ START GALI':status==='finale'?(d?.next_label||'ZAMKNIJ GALĘ'):hold?(d?.next_label||'NASTĘPNA KATEGORIA'):'PREZENTACJA W TOKU…';
  const phaseLabel=phase==='intro'?'Zapowiedź kategorii':phase==='nominees'?`Nominowani ${d?.nominees_revealed||0}/3`:phase==='suspense'?'Chwila napięcia…':phase==='winner_animation'?'Odsłaniamy laureata…':phase==='winner_hold'?'Laureat na ekranie TV':status==='finale'?'Finał gali':status==='finished'?'Gala zakończona':'Gala gotowa do startu';
  const main=()=>status==='idle'||status==='finished'?act(()=>api.galaStart(year)):act(()=>api.galaNext(year));
  return <View style={{gap:10}}>{err?<ErrorBox message={err}/>:null}{!d?<Text style={s.reason}>Ładowanie sterowania gali…</Text>:<>
    <Card style={s.galaHero}><View style={s.between}><Pill text={`GALA ${year}`} tone="amber"/><Pill text={d.test_mode?'TRYB TESTOWY':d.ready?'GOTOWA':'OCZEKUJE'} tone={d.test_mode?'purple':d.ready?'green':'muted'}/></View><Text style={s.heroTitle}>🎬 Pilot Gali Awards</Text><Muted>Telefon tylko uruchamia kolejną kategorię. Zapowiedź, TOP3, suspense i reveal lecą automatycznie na telewizorze.</Muted><Text style={s.reason}>{Number(d.selected_count||0)} / {Number(d.required_count||18)} laureatów wybranych{(d.unavailable||[]).length?` • ${(d.unavailable||[]).length} kategorii bez kandydatów`:''}</Text>{d.test_mode&&((d.missing_selection_details||[]).length||(d.unavailable||[]).length)?<Text style={s.galaTestNote}>Próba techniczna: brakujące wybory dostają zamrożonego lidera rankingu, a kategorie bez kandydatów są pomijane.</Text>:null}</Card>
    {status==='running'&&current?<Card><View style={s.between}><Pill text={`${idx+1} / ${total}`} tone="green"/><Text style={s.galaPhase}>{phaseLabel}</Text></View><Text style={s.galaCategory}>{current.title||current.key}</Text>{hold&&current.winner?<><Text style={s.galaWinnerLabel}>NA EKRANIE</Text><Text style={s.galaWinner}>{current.winner?.gala?.display_name||current.winner?.name||'—'}</Text></>:<Muted>{phase==='nominees'?`Pokazano ${d?.nominees_revealed||0} z 3 nominowanych.`:'Nie musisz nic klikać — czekamy na koniec cyklu.'}</Muted>}</Card>:null}
    {status==='finale'?<Card><Text style={s.galaCategory}>🏆 Wszystkie 18 kategorii pokazane</Text><Muted>Na telewizorze trwa ekran finałowy. Zamknij galę, kiedy będziecie gotowi.</Muted></Card>:null}
    {status==='finished'?<Card><Text style={s.galaCategory}>✅ Gala zakończona</Text><Muted>Możesz uruchomić ją od początku ponownie.</Muted></Card>:null}
    <Btn title={busy?'CHWILA…':mainTitle} disabled={busy||!canMain||!d.available} onPress={main}/>
    {status==='running'&&hold?<View style={s.rowWrap}><View style={s.half}><Btn title="↻ POWTÓRZ KATEGORIĘ" tone="secondary" small onPress={()=>void act(()=>api.galaReplay(year))}/></View><View style={s.half}><Btn title="🧹 RESET" tone="danger" small onPress={()=>Alert.alert('Reset gali','Wrócić do stanu przed startem gali?',[{text:'Anuluj',style:'cancel'},{text:'Resetuj',style:'destructive',onPress:()=>void act(()=>api.galaReset(year))}])}/></View></View>:null}
    {!d.available?<Card><Muted>Gala jest zablokowana do czasu wybrania laureatów wszystkich wymaganych kategorii.</Muted></Card>:null}
  </>}</View>;
}

function Milestones(){
  const [d,setD]=useState<any>(null),[err,setErr]=useState(''),[open,setOpen]=useState<Record<string,boolean>>({});
  useEffect(()=>{api.milestones().then(setD).catch(x=>setErr(x.message))},[]);
  const groups=useMemo(()=>{const out:Record<string,any[]>={};for(const x of d?.timeline||[]){const day=fmtDay(x.earned_at);(out[day]??=[]).push(x)}return Object.entries(out)},[d]);
  return <View style={{gap:10}}>{err?<ErrorBox message={err}/>:null}{d?<>
    <Card style={s.hero}><Pill text="KAMIENIE MILOWE" tone="purple"/><Text style={s.heroTitle}>Historia całego FIFA Night</Text><Muted>Jubileusze, pierwsze razy i momenty, po których statystyki już nigdy nie były takie same.</Muted></Card>
    {(d.next||[]).length?<><Text style={s.kicker}>🎯 NASTĘPNE JUBILEUSZE</Text><View style={s.metrics}>{(d.next||[]).map((x:any)=><Metric key={x.name} value={`${x.current} / ${x.target}`} label={`${x.name} • zostało ${x.left}`}/>)}</View></>:null}
    <Text style={s.kicker}>💎 OŚ HISTORII</Text>
    {groups.length?groups.map(([day,items],idx)=><Card key={day}><Pressable onPress={()=>setOpen(z=>({...z,[day]:!(z[day]??idx===0)}))}><View style={s.between}><Text style={s.day}>📅 {day}</Text><Text style={s.arrow}>{(open[day]??idx===0)?'⌃':'⌄'}</Text></View></Pressable>{(open[day]??idx===0)?items.map((x:any,i:number)=><View key={`${x.key}-${i}`} style={s.timeline}><Text style={s.timelineIcon}>{x.icon||'💎'}</Text><View style={{flex:1}}><Text style={s.name}>{x.title}</Text><Text style={s.reason}>{String(x.earned_at||'').slice(11,16)}{x.detail?` • ${x.detail}`:''}</Text></View></View>):<Muted>{items.length} wpisów — dotknij, żeby rozwinąć.</Muted>}</Card>):<Card><Text style={s.empty}>Pierwsze kamienie pojawią się po oficjalnych meczach.</Text></Card>}
  </>:<Text style={s.reason}>Ładowanie…</Text>}</View>;
}

export default function AwardsScreen({controller=false}:{controller?:boolean}){
  const [mode,setMode]=useState<Mode>('awards');const [year,setYear]=useState(new Date().getFullYear());
  const [galaVisible,setGalaVisible]=useState(false);
  useEffect(()=>{let alive=true;if(!controller){setGalaVisible(false);return()=>{alive=false}};api.gala(year).then(x=>{if(alive)setGalaVisible(!!x.available)}).catch(()=>{if(alive)setGalaVisible(false)});return()=>{alive=false}},[controller,year]);
  useEffect(()=>{if(mode==='gala'&&!galaVisible)setMode('awards')},[galaVisible,mode]);
  return <ScrollView contentContainerStyle={s.pad}>
    <View style={s.between}><Text style={s.pageTitle}>Awards</Text><View style={{flexDirection:'row',gap:5}}><Pressable style={s.yearBtn} onPress={()=>setYear(y=>y-1)}><Text style={s.yearText}>−</Text></Pressable><Text style={s.year}>{year}</Text><Pressable style={s.yearBtn} onPress={()=>setYear(y=>y+1)}><Text style={s.yearText}>+</Text></Pressable></View></View>
    <HScroll><Chip label="🏆 AWARDS" active={mode==='awards'} onPress={()=>setMode('awards')}/><Chip label="🎯 KLASYFIKACJE" active={mode==='classifications'} onPress={()=>setMode('classifications')}/><Chip label="🏛️ KAMIENIE MILOWE" active={mode==='milestones'} onPress={()=>setMode('milestones')}/>{controller&&galaVisible?<Chip label="🎬 GALA" active={mode==='gala'} onPress={()=>setMode('gala')}/>:null}</HScroll>
    {mode==='gala'?<GalaControl year={year}/>:mode==='milestones'?<Milestones/>:<AwardsYear year={year} mode={mode}/>} 
  </ScrollView>;
}

const s=StyleSheet.create({
  pad:{padding:15,paddingBottom:48,gap:11},between:{flexDirection:'row',alignItems:'center',justifyContent:'space-between',gap:9},pageTitle:{color:colors.text,fontSize:27,fontWeight:'900'},galaHero:{backgroundColor:'#22190b',borderColor:'#6f5518'},galaPhase:{color:colors.amber,fontSize:10,fontWeight:'900',textAlign:'right',flex:1},galaCategory:{color:colors.text,fontSize:20,fontWeight:'900',lineHeight:25},galaWinnerLabel:{color:colors.muted,fontSize:9,fontWeight:'900',letterSpacing:1.5,marginTop:5},galaWinner:{color:colors.green,fontSize:27,fontWeight:'900'},galaTestNote:{color:colors.amber,fontSize:10,lineHeight:15,marginTop:6},year:{color:colors.text,fontSize:15,fontWeight:'900',alignSelf:'center'},yearBtn:{width:32,height:32,borderRadius:10,backgroundColor:colors.panel,alignItems:'center',justifyContent:'center'},yearText:{color:colors.green,fontSize:20,fontWeight:'900'},hero:{backgroundColor:'#251f0c',borderColor:'#695a16'},classHero:{backgroundColor:'#25182f',borderColor:'#54316a'},heroTitle:{color:colors.text,fontSize:19,fontWeight:'900'},metrics:{flexDirection:'row',flexWrap:'wrap',gap:8},cardTitle:{color:colors.text,fontSize:15,fontWeight:'900',flex:1},engraving:{color:'#f0c85a',fontSize:10.5,fontWeight:'900',letterSpacing:.4,marginTop:2},candidate:{flexDirection:'row',gap:10,alignItems:'flex-start',paddingVertical:8,borderTopWidth:1,borderTopColor:'#182a3d'},pos:{color:colors.green,fontSize:18,fontWeight:'900',width:24},name:{color:colors.text,fontSize:13,fontWeight:'900'},reason:{color:colors.muted,fontSize:10,lineHeight:15,marginTop:2},quip:{color:'#d5dfeb',fontSize:10.5,fontStyle:'italic',lineHeight:15},secondary:{color:colors.muted,fontSize:10.5,lineHeight:16,borderTopWidth:1,borderTopColor:'#182a3d',paddingTop:8},rowWrap:{flexDirection:'row',flexWrap:'wrap',gap:8},half:{width:'48%'},kicker:{color:colors.green,fontSize:11,fontWeight:'900',letterSpacing:1.2},day:{color:colors.text,fontSize:15,fontWeight:'900'},arrow:{color:colors.muted,fontSize:21},timeline:{flexDirection:'row',gap:9,paddingVertical:8,borderTopWidth:1,borderTopColor:'#182a3d'},timelineIcon:{fontSize:20},empty:{color:colors.muted,fontSize:12,lineHeight:18,textAlign:'center'},
});
