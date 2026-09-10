import React from 'react';
import {Pressable, ScrollView, StyleSheet, Text, TextInput, View} from 'react-native';
import {colors} from './theme';

export function Card({children,style}:{children:React.ReactNode;style?:any}){return <View style={[s.card,style]}>{children}</View>}
export function Pill({text,tone='muted'}:{text:string;tone?:'green'|'blue'|'amber'|'red'|'purple'|'muted'}){
 const bg:any={green:'#103a31',blue:'#142f50',amber:'#3b2e0c',red:'#401b29',purple:'#332044',muted:'#182638'};
 const fg:any={green:colors.green,blue:colors.blue,amber:colors.amber,red:colors.red,purple:colors.purple,muted:colors.muted};
 return <View style={[s.pill,{backgroundColor:bg[tone]}]}><Text style={[s.pillText,{color:fg[tone]}]}>{text}</Text></View>
}
export function Btn({title,onPress,tone='primary',disabled=false,small=false}:{title:string;onPress:()=>void;tone?:'primary'|'secondary'|'danger'|'ghost';disabled?:boolean;small?:boolean}){
 return <Pressable onPress={onPress} disabled={disabled} style={({pressed}:{pressed:boolean})=>[s.btn,small&&s.btnSmall,tone==='primary'?s.primary:tone==='danger'?s.danger:tone==='ghost'?s.ghost:s.secondary,(pressed||disabled)&&{opacity:.55}]}><Text style={[s.btnText,tone==='primary'&&{color:'#052017'},tone==='danger'&&{color:colors.red}]}>{title}</Text></Pressable>
}
export function Chip({label,active=false,onPress,disabled=false}:{label:string;active?:boolean;onPress?:()=>void;disabled?:boolean}){
 return <Pressable disabled={!onPress||disabled} onPress={onPress} style={[s.chip,active&&s.chipActive,disabled&&{opacity:.5}]}><Text style={[s.chipText,active&&s.chipTextActive]}>{label}</Text></Pressable>
}
export function HScroll({children}:{children:React.ReactNode}){return <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{gap:8,paddingVertical:4}}>{children}</ScrollView>}
export function Input(p:any){return <TextInput placeholderTextColor="#5f748b" {...p} style={[s.input,p.style]} />}
export function SectionTitle({children}:{children:React.ReactNode}){return <Text style={s.sectionTitle}>{children}</Text>}
export function Muted({children,center=false}:{children:React.ReactNode;center?:boolean}){return <Text style={[s.muted,center&&{textAlign:'center'}]}>{children}</Text>}
export function ErrorBox({message}:{message:string}){return <View style={s.errorBox}><Text style={s.errorText}>{message}</Text></View>}
export function Loading(){return <View style={{padding:28}}><Text style={{color:colors.muted,textAlign:'center'}}>Ładowanie…</Text></View>}
export function ToggleRow({label,value,onChange,sub}:{label:string;value:boolean;onChange:(v:boolean)=>void;sub?:string}){return <Pressable onPress={()=>onChange(!value)} style={s.toggleRow}><View style={{flex:1}}><Text style={s.toggleLabel}>{label}</Text>{sub?<Text style={s.toggleSub}>{sub}</Text>:null}</View><View style={[s.toggle,{backgroundColor:value?colors.green:'#27394d'}]}><View style={[s.knob,{alignSelf:value?'flex-end':'flex-start'}]}/></View></Pressable>}
export function Metric({value,label}:{value:any;label:string}){return <View style={s.metric}><Text style={s.metricValue}>{value}</Text><Text style={s.metricLabel}>{label}</Text></View>}
const s=StyleSheet.create({
 card:{backgroundColor:colors.panel,borderRadius:19,borderWidth:1,borderColor:colors.border,padding:15,gap:9},
 pill:{paddingHorizontal:9,paddingVertical:5,borderRadius:999,alignSelf:'flex-start'},pillText:{fontSize:10,fontWeight:'900',letterSpacing:.6},
 btn:{minHeight:48,borderRadius:14,alignItems:'center',justifyContent:'center',paddingHorizontal:13,borderWidth:1},btnSmall:{minHeight:38,paddingHorizontal:10},
 primary:{backgroundColor:colors.green,borderColor:colors.green},secondary:{backgroundColor:'#112238',borderColor:'#314a65'},danger:{backgroundColor:'#391b27',borderColor:'#6b263d'},ghost:{backgroundColor:'transparent',borderColor:'transparent'},btnText:{color:colors.text,fontWeight:'900',fontSize:12,letterSpacing:.25,textAlign:'center'},
 chip:{backgroundColor:'#122338',borderWidth:1,borderColor:'#263d57',borderRadius:999,paddingHorizontal:12,paddingVertical:8},chipActive:{backgroundColor:'#103a31',borderColor:'#2d9a74'},chipText:{color:'#9db0c4',fontSize:11,fontWeight:'800'},chipTextActive:{color:colors.green},
 input:{backgroundColor:'#081522',borderWidth:1,borderColor:'#284058',color:colors.text,minHeight:46,borderRadius:13,paddingHorizontal:12,fontSize:14},
 sectionTitle:{color:colors.text,fontSize:19,fontWeight:'900'},muted:{color:colors.muted,fontSize:12,lineHeight:18},
 errorBox:{backgroundColor:'#3b1723',borderWidth:1,borderColor:'#6f293e',borderRadius:13,padding:11},errorText:{color:'#fda4af',fontSize:12,lineHeight:18},
 toggleRow:{flexDirection:'row',alignItems:'center',gap:12,paddingVertical:7},toggleLabel:{color:colors.text,fontWeight:'800',fontSize:13},toggleSub:{color:colors.muted,fontSize:10,marginTop:3,lineHeight:14},toggle:{width:44,height:25,borderRadius:999,padding:3,justifyContent:'center'},knob:{width:19,height:19,borderRadius:10,backgroundColor:'#fff'},
 metric:{width:'48%',backgroundColor:colors.panel,borderWidth:1,borderColor:colors.border,borderRadius:15,padding:12},metricValue:{color:colors.text,fontSize:21,fontWeight:'900'},metricLabel:{color:colors.muted,fontSize:10,marginTop:2},
});
export {s as common};
