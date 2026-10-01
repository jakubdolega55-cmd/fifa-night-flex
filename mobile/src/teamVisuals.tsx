import React,{useState} from 'react';
import {Image,StyleSheet,Text,View} from 'react-native';

const CLUBS:Record<string,[string,string]>={
 'real madryt':['spain','real-madrid'],'real madrid':['spain','real-madrid'],
 'psg':['france','paris-saint-germain'],'paris saint-germain':['france','paris-saint-germain'],
 'bayern monachium':['germany','bayern-munchen'],'bayern munich':['germany','bayern-munchen'],'bayern münchen':['germany','bayern-munchen'],
 'fc barcelona':['spain','barcelona'],'barcelona':['spain','barcelona'],
 'arsenal':['england','arsenal'],'manchester city':['england','manchester-city'],
 'liverpool':['england','liverpool'],'liverpool fc':['england','liverpool'],
 'atletico':['spain','atletico-madrid'],'atletico madrid':['spain','atletico-madrid'],'atlético':['spain','atletico-madrid'],'atlético madrid':['spain','atletico-madrid'],'atlético de madrid':['spain','atletico-madrid'],
 'inter':['italy','inter'],'inter milan':['italy','inter'],'lombardia fc':['italy','inter'],'man united':['england','manchester-united'],'man utd':['england','manchester-united'],'manchester utd':['england','manchester-united'],'manchester united':['england','manchester-united'],
 'bvb':['germany','borussia-dortmund'],'bvb 09':['germany','borussia-dortmund'],'borussia dortmund':['germany','borussia-dortmund'],
 'napoli':['italy','napoli'],'chelsea':['england','chelsea'],'tottenham':['england','tottenham'],'tottenham hotspur':['england','tottenham'],
 'ac milan':['italy','milan'],'milan':['italy','milan'],'bayer leverkusen':['germany','bayer-leverkusen'],
};
const FLAG_ASSETS={
 spain:require('../assets/teams/flags/spain.png'),england:require('../assets/teams/flags/england.png'),brazil:require('../assets/teams/flags/brazil.png'),germany:require('../assets/teams/flags/germany.png'),portugal:require('../assets/teams/flags/portugal.png'),
 italy:require('../assets/teams/flags/italy.png'),argentina:require('../assets/teams/flags/argentina.png'),netherlands:require('../assets/teams/flags/netherlands.png'),belgium:require('../assets/teams/flags/belgium.png'),croatia:require('../assets/teams/flags/croatia.png'),
 denmark:require('../assets/teams/flags/denmark.png'),morocco:require('../assets/teams/flags/morocco.png'),turkey:require('../assets/teams/flags/turkey.png'),switzerland:require('../assets/teams/flags/switzerland.png'),
} as const;
const FLAGS:Record<string,any>={
 'hiszpania':FLAG_ASSETS.spain,'spain':FLAG_ASSETS.spain,'anglia':FLAG_ASSETS.england,'england':FLAG_ASSETS.england,'brazylia':FLAG_ASSETS.brazil,'brazil':FLAG_ASSETS.brazil,'niemcy':FLAG_ASSETS.germany,'germany':FLAG_ASSETS.germany,'portugalia':FLAG_ASSETS.portugal,'portugal':FLAG_ASSETS.portugal,
 'włochy':FLAG_ASSETS.italy,'wlochy':FLAG_ASSETS.italy,'italy':FLAG_ASSETS.italy,'argentyna':FLAG_ASSETS.argentina,'argentina':FLAG_ASSETS.argentina,'holandia':FLAG_ASSETS.netherlands,'netherlands':FLAG_ASSETS.netherlands,'belgia':FLAG_ASSETS.belgium,'belgium':FLAG_ASSETS.belgium,
 'chorwacja':FLAG_ASSETS.croatia,'croatia':FLAG_ASSETS.croatia,'dania':FLAG_ASSETS.denmark,'denmark':FLAG_ASSETS.denmark,'maroko':FLAG_ASSETS.morocco,'morocco':FLAG_ASSETS.morocco,'turcja':FLAG_ASSETS.turkey,'turkey':FLAG_ASSETS.turkey,'szwajcaria':FLAG_ASSETS.switzerland,'switzerland':FLAG_ASSETS.switzerland,
};

const norm=(v:any)=>String(v||'').trim().toLowerCase().replace(/\s+/g,' ');
export const teamLogoUrl=(team:any)=>{const d=CLUBS[norm(team)];return d?`https://football-logos.cc/logos/${d[0]}/256x256/${d[1]}.png`:null};
export const teamFlag=(team:any)=>FLAGS[norm(team)]||null;
const initials=(team:any)=>{const x=String(team||'').replace(/-/g,' ').trim().split(/\s+/).filter(Boolean);return x.length>1?x.slice(0,3).map(y=>y[0]).join('').toUpperCase():(x[0]||'FC').slice(0,3).toUpperCase()};

export function TeamVisual({team,size=52}:{team?:string|null;size?:number}){
 const [failed,setFailed]=useState(false);const flag=teamFlag(team);const url=teamLogoUrl(team);
 if(flag)return <View style={[s.box,s.logoShadow,{width:size,height:size}]}><Image accessibilityLabel={`Flaga ${team||''}`} source={flag} resizeMode="contain" style={{width:size,height:size}}/></View>;
 if(url&&!failed)return <View style={[s.box,s.logoShadow,{width:size,height:size}]}><Image accessibilityLabel={`Herb ${team||''}`} source={{uri:url,cache:'force-cache'}} resizeMode="contain" onError={()=>setFailed(true)} style={{width:size,height:size}}/></View>;
 return <View style={[s.fallback,{width:size,height:size,borderRadius:size/2}]}><Text style={[s.fallbackText,{fontSize:Math.max(10,Math.round(size*.23))}]}>{initials(team)}</Text></View>;
}
const s=StyleSheet.create({box:{alignItems:'center',justifyContent:'center'},logoShadow:{shadowColor:'#000',shadowOpacity:.28,shadowRadius:5,shadowOffset:{width:0,height:3},elevation:3},fallback:{alignItems:'center',justifyContent:'center',backgroundColor:'#14263a',borderWidth:1,borderColor:'#31506b'},fallbackText:{color:'#dbeafe',fontWeight:'900'}});
