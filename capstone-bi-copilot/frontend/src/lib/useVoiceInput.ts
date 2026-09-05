import { useEffect,useRef,useState } from "react";
import { transcribeVoice } from "./api";
export type VoiceInputState="idle"|"listening"|"processing"|"error";
export function useVoiceInput(onTranscript:(text:string)=>void){
  const [state,setState]=useState<VoiceInputState>("idle"),[error,setError]=useState("");
  const recorder=useRef<MediaRecorder|null>(null),stream=useRef<MediaStream|null>(null),chunks=useRef<Blob[]>([]);
  function cleanup(){stream.current?.getTracks().forEach(track=>track.stop());stream.current=null;recorder.current=null;}
  async function start(){
    setError("");
    if(!navigator.mediaDevices?.getUserMedia||typeof MediaRecorder==="undefined"){setState("error");setError("Microphone recording is unavailable in this browser.");return}
    try{
      stream.current=await navigator.mediaDevices.getUserMedia({audio:true}); chunks.current=[];
      const preferred=MediaRecorder.isTypeSupported("audio/webm;codecs=opus")?"audio/webm;codecs=opus":"audio/webm";
      const current=new MediaRecorder(stream.current,{mimeType:preferred}); recorder.current=current;
      current.ondataavailable=event=>{if(event.data.size)chunks.current.push(event.data)};
      current.onstop=async()=>{const audio=new Blob(chunks.current,{type:current.mimeType});cleanup();if(!audio.size){setState("error");setError("No speech was recorded.");return}setState("processing");try{onTranscript(await transcribeVoice(audio));setState("idle")}catch(reason){setState("error");setError(reason instanceof Error?reason.message:"Speech could not be transcribed.")}};
      current.start();setState("listening");
    }catch(reason){cleanup();setState("error");setError(reason instanceof DOMException&&reason.name==="NotAllowedError"?"Microphone permission was denied.":"The microphone could not be started.")}
  }
  function stop(){if(recorder.current?.state==="recording")recorder.current.stop()}
  useEffect(()=>cleanup,[]);
  return {state,error,start,stop};
}
