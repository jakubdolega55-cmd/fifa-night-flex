const g=globalThis as any;
export async function getStoredItem(key:string):Promise<string|null>{
  try{return g?.localStorage?.getItem(key) ?? null}catch{return null}
}
export async function setStoredItem(key:string,value:string):Promise<void>{
  try{g?.localStorage?.setItem(key,value)}catch{}
}
export async function deleteStoredItem(key:string):Promise<void>{
  try{g?.localStorage?.removeItem(key)}catch{}
}
