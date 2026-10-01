import React from 'react';
import {Image,StyleSheet,Text,View} from 'react-native';

const CLUB_ASSETS={
 'real-madrid':require('../assets/teams/clubs/real-madrid.png'),
 'paris-saint-germain':require('../assets/teams/clubs/paris-saint-germain.png'),
 'bayern-munchen':require('../assets/teams/clubs/bayern-munchen.png'),
 'barcelona':require('../assets/teams/clubs/barcelona.png'),
 'arsenal':require('../assets/teams/clubs/arsenal.png'),
 'manchester-city':require('../assets/teams/clubs/manchester-city.png'),
 'liverpool':require('../assets/teams/clubs/liverpool.png'),
 'atletico-madrid':require('../assets/teams/clubs/atletico-madrid.png'),
 'inter':require('../assets/teams/clubs/inter.png'),
 'manchester-united':require('../assets/teams/clubs/manchester-united.png'),
 'borussia-dortmund':require('../assets/teams/clubs/borussia-dortmund.png'),
 'napoli':require('../assets/teams/clubs/napoli.png'),
 'chelsea':require('../assets/teams/clubs/chelsea.png'),
 'tottenham':require('../assets/teams/clubs/tottenham.png'),
 'milan':require('../assets/teams/clubs/milan.png'),
 'bayer-leverkusen':require('../assets/teams/clubs/bayer-leverkusen.png'),
} as const;

const CLUB_KEYS:Record<string,keyof typeof CLUB_ASSETS>={
 'real madryt':'real-madrid','real madrid':'real-madrid',
 'psg':'paris-saint-germain','paris saint-germain':'paris-saint-germain',
 'bayern monachium':'bayern-munchen','bayern munich':'bayern-munchen','bayern münchen':'bayern-munchen',
 'fc barcelona':'barcelona','barcelona':'barcelona',
 'arsenal':'arsenal','manchester city':'manchester-city',
 'liverpool':'liverpool','liverpool fc':'liverpool',
 'atletico':'atletico-madrid','atletico madrid':'atletico-madrid','atlético':'atletico-madrid','atlético madrid':'atletico-madrid','atlético de madrid':'atletico-madrid',
 'inter':'inter','inter milan':'inter','lombardia fc':'inter',
 'man united':'manchester-united','man utd':'manchester-united','manchester utd':'manchester-united','manchester united':'manchester-united',
 'bvb':'borussia-dortmund','bvb 09':'borussia-dortmund','borussia dortmund':'borussia-dortmund',
 'napoli':'napoli','chelsea':'chelsea','tottenham':'tottenham','tottenham hotspur':'tottenham',
 'ac milan':'milan','milan':'milan','bayer leverkusen':'bayer-leverkusen',
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
export const teamLogo=(team:any)=>{const key=CLUB_KEYS[norm(team)];return key?CLUB_ASSETS[key]:null};
export const teamFlag=(team:any)=>FLAGS[norm(team)]||null;
const initials=(team:any)=>{const x=String(team||'').replace(/-/g,' ').trim().split(/\s+/).filter(Boolean);return x.length>1?x.slice(0,3).map(y=>y[0]).join('').toUpperCase():(x[0]||'FC').slice(0,3).toUpperCase()};

export function TeamVisual({team,size=52}:{team?:string|null;size?:number}){
 const flag=teamFlag(team);const logo=teamLogo(team);
 if(flag)return <View style={[s.box,s.logoShadow,{width:size,height:size}]}><Image accessibilityLabel={`Flaga ${team||''}`} source={flag} resizeMode="contain" style={{width:size,height:size}}/></View>;
 if(logo)return <View style={[s.box,s.logoShadow,{width:size,height:size}]}><Image accessibilityLabel={`Herb ${team||''}`} source={logo} resizeMode="contain" style={{width:size,height:size}}/></View>;
 return <View style={[s.fallback,{width:size,height:size,borderRadius:size/2}]}><Text style={[s.fallbackText,{fontSize:Math.max(10,Math.round(size*.23))}]}>{initials(team)}</Text></View>;
}
const s=StyleSheet.create({box:{alignItems:'center',justifyContent:'center'},logoShadow:{shadowColor:'#000',shadowOpacity:.28,shadowRadius:5,shadowOffset:{width:0,height:3},elevation:3},fallback:{alignItems:'center',justifyContent:'center',backgroundColor:'#14263a',borderWidth:1,borderColor:'#31506b'},fallbackText:{color:'#dbeafe',fontWeight:'900'}});
