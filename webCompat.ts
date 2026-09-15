import {Alert, Platform} from 'react-native';

let installed=false;
export function installWebCompat(){
  const g=globalThis as any;
  if(installed||Platform.OS!=='web'||!g?.window)return;
  installed=true;
  (Alert as any).alert=(title?:string,message?:string,buttons?:Array<{text?:string;style?:string;onPress?:()=>void}>)=>{
    const body=[title,message].filter(Boolean).join('\n\n');
    const items=Array.isArray(buttons)?buttons:[];
    if(items.length<=1){
      g.window.alert(body);
      items[0]?.onPress?.();
      return;
    }
    const cancel=items.find(x=>x.style==='cancel'||/anuluj|nie|cancel/i.test(String(x.text||'')));
    const affirmative=[...items].reverse().find(x=>x!==cancel) || items[items.length-1];
    if(g.window.confirm(body)) affirmative?.onPress?.();
    else cancel?.onPress?.();
  };
}
