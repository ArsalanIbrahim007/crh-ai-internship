import { useEffect, useState } from "react";

export interface VoicePreferences { commands:boolean; wakePhrase:boolean; replies:boolean; autoSend:boolean }
const key="business-agent.voice-preferences";
const defaults:VoicePreferences={commands:true,wakePhrase:false,replies:true,autoSend:false};
function read():VoicePreferences { try{return {...defaults,...JSON.parse(localStorage.getItem(key)||"{}")} as VoicePreferences}catch{return defaults} }
export function useVoicePreferences(){
  const [preferences,setLocal]=useState(read);
  useEffect(()=>{const sync=()=>setLocal(read());window.addEventListener("voice-preferences",sync);return()=>window.removeEventListener("voice-preferences",sync)},[]);
  function setPreferences(next:VoicePreferences){localStorage.setItem(key,JSON.stringify(next));setLocal(next);window.dispatchEvent(new Event("voice-preferences"));}
  return {preferences,setPreferences};
}
