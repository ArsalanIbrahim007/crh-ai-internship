from __future__ import annotations
import math,re
from collections import Counter
from dataclasses import dataclass
from sqlalchemy.orm import Session
from app.db.models import Document,DocumentChunk
from app.services.llm_service import llm_service
@dataclass
class RetrievedChunk: source_id:str; title:str; text:str; score:float

def toks(s:str): return re.findall(r"[a-z0-9]+",s.lower())
def cosine(a:Counter,b:Counter)->float:
    dot=sum(v*b.get(k,0) for k,v in a.items()); na=math.sqrt(sum(v*v for v in a.values())); nb=math.sqrt(sum(v*v for v in b.values())); return dot/(na*nb) if na and nb else 0
class RAGService:
    def hybrid_search(self,db:Session,query_text:str,user_role:str="manager",top_k:int=5)->list[RetrievedChunk]:
        q=Counter(toks(query_text)); rows=db.query(DocumentChunk,Document).join(Document,Document.id==DocumentChunk.document_id).all(); scored=[]
        for ch,doc in rows:
            if user_role not in {x.strip() for x in doc.allowed_roles.split(",")}: continue
            ct=toks(ch.text); dense=cosine(q,Counter(ct)); overlap=len(set(q)&set(ct))/max(1,len(set(q))); score=.65*dense+.35*overlap
            if score>0: scored.append(RetrievedChunk(doc.id,doc.filename,ch.text,score))
        return sorted(scored,key=lambda x:x.score,reverse=True)[:top_k]
    async def answer(self,db:Session,query_text:str,user_role:str="manager")->tuple[str,list[RetrievedChunk]]:
        chunks=self.hybrid_search(db,query_text,user_role)
        if not chunks: return "No grounded company source matched the question.",[]
        context="\n\n".join(f"[{i+1}] {c.title}: {c.text}" for i,c in enumerate(chunks))
        prompt=f"Question: {query_text}\n\nGrounded sources:\n{context}\n\nAnswer only from these sources. Cite sources as [1], [2], etc."
        ans=await llm_service.complete("You are a grounded enterprise RAG assistant. Never invent facts beyond supplied context.",prompt)
        return ans,chunks
rag_service=RAGService()
