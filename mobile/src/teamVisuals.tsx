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
const ENGLAND_FLAG='\u{1F3F4}\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}';
const FLAGS:Record<string,string>={
 'hiszpania':'🇪🇸','spain':'🇪🇸','anglia':ENGLAND_FLAG,'england':ENGLAND_FLAG,'brazylia':'🇧🇷','brazil':'🇧🇷','niemcy':'🇩🇪','germany':'🇩🇪','portugalia':'🇵🇹','portugal':'🇵🇹',
 'włochy':'🇮🇹','wlochy':'🇮🇹','italy':'🇮🇹','argentyna':'🇦🇷','argentina':'🇦🇷','holandia':'🇳🇱','netherlands':'🇳🇱','belgia':'🇧🇪','belgium':'🇧🇪',
 'chorwacja':'🇭🇷','croatia':'🇭🇷','dania':'🇩🇰','denmark':'🇩🇰','maroko':'🇲🇦','morocco':'🇲🇦','turcja':'🇹🇷','turkey':'🇹🇷','szwajcaria':'🇨🇭','switzerland':'🇨🇭',
};
const norm=(v:any)=>String(v||'').trim().toLowerCase().replace(/\s+/g,' ');
export const teamLogoUrl=(team:any)=>{const d=CLUBS[norm(team)];return d?`https://football-logos.cc/logos/${d[0]}/256x256/${d[1]}.png`:null};
export const teamFlag=(team:any)=>FLAGS[norm(team)]||null;
const initials=(team:any)=>{const x=String(team||'').replace(/-/g,' ').trim().split(/\s+/).filter(Boolean);return x.length>1?x.slice(0,3).map(y=>y[0]).join('').toUpperCase():(x[0]||'FC').slice(0,3).toUpperCase()};

export function TeamVisual({team,size=52}:{team?:string|null;size?:number}){
 const [failed,setFailed]=useState(false);const flag=teamFlag(team);const url=teamLogoUrl(team);
 if(flag)return <View style={[s.box,{width:size,height:size}]}><Text style={{fontSize:Math.round(size*.65),lineHeight:size}}>{flag}</Text></View>;
 if(url&&!failed)return <View style={[s.box,s.logoShadow,{width:size,height:size}]}><Image accessibilityLabel={`Herb ${team||''}`} source={{uri:url,cache:'force-cache'}} resizeMode="contain" onError={()=>setFailed(true)} style={{width:size,height:size}}/></View>;
 return <View style={[s.fallback,{width:size,height:size,borderRadius:size/2}]}><Text style={[s.fallbackText,{fontSize:Math.max(10,Math.round(size*.23))}]}>{initials(team)}</Text></View>;
}
const s=StyleSheet.create({box:{alignItems:'center',justifyContent:'center'},logoShadow:{shadowColor:'#000',shadowOpacity:.28,shadowRadius:5,shadowOffset:{width:0,height:3},elevation:3},fallback:{alignItems:'center',justifyContent:'center',backgroundColor:'#14263a',borderWidth:1,borderColor:'#31506b'},fallbackText:{color:'#dbeafe',fontWeight:'900'}});
