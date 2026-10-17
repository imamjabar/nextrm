/** Public application configuration. Share concurrent reads; never cache user identity. */
export interface AppConfig {
  authProvider:string;
  demoMode:boolean;
  firebaseApiKey:string|null;
  firebaseAuthDomain:string|null;
  firebaseProjectId:string|null;
  googleMapsApiKey?:string|null;
  googleMapsMapId?:string|null;
}
let pending:Promise<AppConfig>|undefined;
export function getAppConfig():Promise<AppConfig>{
  if(!pending){
    const request=fetch('/api/config',{cache:'no-store'}).then(async response=>{
      if(!response.ok)throw new Error('Application configuration unavailable');
      return await response.json() as AppConfig;
    });
    pending=request;
    // Keep no settled configuration cache: runtime changes are read on the next call.
    request.then(()=>{if(pending===request)pending=undefined;},()=>{if(pending===request)pending=undefined;});
  }
  return pending;
}
