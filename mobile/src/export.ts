import {Alert} from 'react-native';
import * as FileSystem from 'expo-file-system/legacy';
import * as Sharing from 'expo-sharing';
import {Asset,requestPermissionsAsync} from 'expo-media-library';
import {API_URL,authHeaders} from './api';

export async function getPng(path:string,filename:string,mode:'share'|'save'){
  if(!API_URL)throw new Error('Brak adresu API.');
  const dir=FileSystem.cacheDirectory;
  if(!dir)throw new Error('Brak katalogu tymczasowego.');
  const target=`${dir}${filename}`;
  const headers=await authHeaders();
  const result=await FileSystem.downloadAsync(`${API_URL}${path}`,target,{headers});
  if(result.status<200||result.status>=300)throw new Error(`Nie udało się pobrać PNG (${result.status}).`);
  const info=await FileSystem.getInfoAsync(result.uri);
  if(!info.exists||('size' in info&&Number(info.size||0)<=0))throw new Error('Pobrana grafika jest pusta.');
  if(mode==='share'){
    const ok=await Sharing.isAvailableAsync();
    if(!ok)throw new Error('Udostępnianie nie jest dostępne na tym urządzeniu.');
    await Sharing.shareAsync(result.uri,{mimeType:'image/png',dialogTitle:'FIFA Night'});
  }else{
    const perm=await requestPermissionsAsync(true);
    if(perm.status!=='granted')throw new Error('Brak zgody na zapis grafiki do galerii.');
    await Asset.create(result.uri);
    Alert.alert('Zapisano','Grafika FIFA Night została zapisana w galerii.');
  }
  return result.uri;
}
