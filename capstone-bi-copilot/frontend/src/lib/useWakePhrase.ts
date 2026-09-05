import { useEffect,useRef,useState } from "react";

type RecognitionEvent=Event&{results:{length:number;[index:number]:{0:{transcript:string};isFinal:boolean}}};
type RecognitionLike={continuous:boolean;interimResults:boolean;lang:string;start():void;stop():void;onresult:((event:RecognitionEvent)=>void)|null;onerror:((event:Event&{error?:string})=>void)|null;onend:(()=>void)|null};
type RecognitionConstructor=new()=>RecognitionLike;

export function useWakePhrase(enabled:boolean,onCommand:(command:string)=>void){
  const [active,setActive]=useState(false),[error,setError]=useState("");
  const armedUntil=useRef(0),restart=useRef(true),callback=useRef(onCommand);callback.current=onCommand;
  useEffect(()=>{
    if(!enabled){setActive(false);setError("");return}
    const SpeechRecognition=(window as unknown as {SpeechRecognition?:RecognitionConstructor;webkitSpeechRecognition?:RecognitionConstructor}).SpeechRecognition??(window as unknown as {webkitSpeechRecognition?:RecognitionConstructor}).webkitSpeechRecognition;
    if(!SpeechRecognition){setError("Wake phrase is unsupported in this browser.");return}
    const recognition=new SpeechRecognition();restart.current=true;recognition.continuous=true;recognition.interimResults=false;recognition.lang=navigator.language||"en-US";
    recognition.onresult=event=>{for(let index=0;index<event.results.length;index++){if(!event.results[index].isFinal)continue;const spoken=event.results[index][0].transcript.trim();const match=spoken.match(/hey\s+agent[,.]?\s*(.*)/i);if(match){if(match[1])callback.current(match[1].trim());else armedUntil.current=Date.now()+8000}else if(Date.now()<armedUntil.current){armedUntil.current=0;callback.current(spoken)}}};
    recognition.onerror=event=>{if(event.error==="not-allowed")setError("Microphone permission is required for Hey Agent.")};
    recognition.onend=()=>{setActive(false);if(restart.current){try{recognition.start();setActive(true)}catch{setError("Wake phrase listening was suspended by the browser.")}}};
    try{recognition.start();setActive(true)}catch{setError("Wake phrase listening could not start.")}
    return()=>{restart.current=false;recognition.stop();setActive(false)};
  },[enabled]);
  return {active,error};
}
