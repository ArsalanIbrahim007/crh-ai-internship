import { useEffect,useRef,useState } from "react";
import { synthesizeVoice } from "./api";
export function useVoicePlayback(onState?:(speaking:boolean)=>void){
  const [state,setState]=useState<"idle"|"loading"|"speaking"|"error">("idle"),[error,setError]=useState("");
  const audioRef=useRef<HTMLAudioElement|null>(null),urlRef=useRef("");
  function stop(){audioRef.current?.pause();audioRef.current=null;if(urlRef.current)URL.revokeObjectURL(urlRef.current);urlRef.current="";setState("idle");onState?.(false)}
  async function play(text:string){stop();setError("");setState("loading");try{const blob=await synthesizeVoice(text);urlRef.current=URL.createObjectURL(blob);const audio=new Audio(urlRef.current);audioRef.current=audio;audio.onended=stop;audio.onerror=()=>{stop();setState("error");setError("Audio playback failed.")};await audio.play();setState("speaking");onState?.(true)}catch(reason){stop();setState("error");setError(reason instanceof Error?reason.message:"Voice playback failed.")}}
  useEffect(()=>stop,[]);
  return {state,error,play,stop};
}
