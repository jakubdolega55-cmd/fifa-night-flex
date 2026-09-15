import {API_URL,authHeaders} from './api';

const g=globalThis as any;
function downloadBlob(blob:any,filename:string){
  const url=g.URL.createObjectURL(blob);
  const a=g.document.createElement('a');
  a.href=url;
  a.download=filename;
  a.rel='noopener';
  g.document.body.appendChild(a);
  a.click();
  a.remove();
  g.setTimeout(()=>g.URL.revokeObjectURL(url),1500);
}

export async function getPng(path:string,filename:string,mode:'share'|'save'){
  if(!API_URL)throw new Error('Brak adresu API.');
  const headers=await authHeaders();
  const response=await fetch(`${API_URL}${path}`,{headers});
  if(!response.ok)throw new Error(`Nie udało się pobrać PNG (${response.status}).`);
  const blob=await response.blob();
  const FileCtor=g.File;
  const file=FileCtor?new FileCtor([blob],filename,{type:'image/png'}):null;
  const nav=g.navigator;
  if(mode==='share' && file && nav?.share){
    const payload={files:[file],title:'FIFA Night'};
    if(!nav.canShare || nav.canShare(payload)){
      try{await nav.share(payload);return filename}catch(e:any){if(e?.name==='AbortError')return filename;}
    }
  }
  downloadBlob(blob,filename);
  return filename;
}
