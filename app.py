import streamlit as st
import subprocess, tempfile, os, re, uuid
from pathlib import Path

st.set_page_config(page_title="Yoon Recap", page_icon="🎬", layout="centered")
WORK=Path(tempfile.gettempdir())/"yoon_recap"; WORK.mkdir(exist_ok=True)

def ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()

def save_file(f, ext):
    p=WORK/f"{uuid.uuid4().hex}{ext}"; p.write_bytes(f.getbuffer()); return p

def run(cmd):
    p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    if p.returncode: raise RuntimeError(p.stderr[-2500:])
    return p

def call_gemini(key,prompt,model):
    from google import genai
    c=genai.Client(api_key=key)
    r=c.models.generate_content(model=model,contents=prompt)
    return getattr(r,"text","") or ""

def transcribe(key,path,model):
    from google import genai
    c=genai.Client(api_key=key)
    f=c.files.upload(file=str(path))
    r=c.models.generate_content(model=model,contents=[f,"Transcribe all spoken dialogue. Output only the transcript. Preserve Burmese speech naturally; no timestamps or explanations."])
    return getattr(r,"text","") or ""

def recap(key,text,model):
    return call_gemini(key,"Write a natural, casual Burmese movie recap from this transcript. Keep important events and do not invent major events. Output only the Burmese narration.\n\n"+text,model)

def make_srt(text):
    parts=[x.strip() for x in re.split(r"\n+|(?<=[.!?။])\s+",text) if x.strip()]
    out=[]; t=0
    for i,x in enumerate(parts,1):
        d=max(2,min(7,len(x)/8)); a=int(t*1000); b=int((t+d)*1000)
        def tm(ms):
            s,ms=divmod(ms,1000); h,s=divmod(s,3600); m,s=divmod(s,60)
            return f"{h:02}:{m:02}:{s:02},{ms:03}"
        out.append(f"{i}\n{tm(a)} --> {tm(b)}\n{x}\n"); t+=d
    return "\n".join(out)

def tts(text,voice,rate):
    import edge_tts, asyncio
    p=WORK/f"{uuid.uuid4().hex}.mp3"
    async def go(): await edge_tts.Communicate(text,voice,rate=rate).save(str(p))
    asyncio.run(go()); return p

def render(video,voice,srt):
    out=WORK/f"{uuid.uuid4().hex}.mp4"; cmd=[ffmpeg(),"-y","-i",str(video)]
    if voice: cmd+=["-i",str(voice)]
    if srt:
        sp=WORK/f"{uuid.uuid4().hex}.srt"; sp.write_text(srt,encoding="utf-8")
        esc=str(sp).replace("\\","/").replace(":","\\:")
        cmd+=["-vf",f"subtitles='{esc}'"]
    cmd+=["-map","0:v:0","-map","1:a:0" if voice else "0:a:0?","-c:v","libx264","-preset","veryfast","-crf","25","-c:a","aac","-b:a","128k","-shortest",str(out)]
    run(cmd); return out

st.title("🎬 Yoon Recap")
st.caption("Streamlit Edition")
with st.sidebar:
    key=st.text_input("Gemini API Key",type="password")
    model=st.text_input("Gemini Model","gemini-2.5-flash")
    st.markdown("[Get Gemini API Key](https://aistudio.google.com/app/apikey)")
    voice=st.selectbox("Burmese Voice",["my-MM-NilarNeural","my-MM-ThihaNeural"])
    speed=st.slider("Voice Speed",0.5,1.5,1.0,0.1)

video=st.file_uploader("🎬 Video Upload",type=["mp4","mov","mkv","webm","avi"])
external=st.file_uploader("📄 External SRT (optional)",type=["srt"])
uploaded_voice=st.file_uploader("🎙️ AI Voice Upload (optional)",type=["mp3","wav","m4a"])

if video:
    st.video(video)
    if st.button("🚀 01 • Transcribe Video",use_container_width=True):
        if not key: st.error("Gemini API Key ထည့်ပါ။")
        else:
            with st.spinner("Transcript ထုတ်နေပါတယ်..."):
                try:
                    vp=save_file(video,Path(video.name).suffix or ".mp4")
                    st.session_state.transcript=transcribe(key,vp,model)
                    st.session_state.original_srt=make_srt(st.session_state.transcript)
                except Exception as e: st.error(str(e))

if st.session_state.get("transcript"):
    st.text_area("📝 Original Transcript",st.session_state.transcript,height=180)
    st.download_button("📥 Original SRT",st.session_state.original_srt,"original.srt")
    if st.button("🇲🇲 02 • Generate Burmese Recap",use_container_width=True):
        with st.spinner("Burmese recap ရေးနေပါတယ်..."):
            try: st.session_state.recap=recap(key,st.session_state.transcript,model)
            except Exception as e: st.error(str(e))

if st.session_state.get("recap"):
    st.text_area("✍️ Burmese Recap Script",st.session_state.recap,height=220)
    if st.button("🔊 03 • Generate Free Burmese AI Voice",use_container_width=True):
        with st.spinner("AI Voice ထုတ်နေပါတယ်..."):
            try:
                rate="+0%" if speed==1 else f"{int((speed-1)*100):+d}%"
                st.session_state.voice=str(tts(st.session_state.recap,voice,rate))
            except Exception as e: st.error(str(e))

if st.session_state.get("voice") and Path(st.session_state.voice).exists():
    vp=Path(st.session_state.voice); st.audio(vp.read_bytes())
    st.download_button("📥 AI Voice Download",vp.read_bytes(),"burmese_voice.mp3")

if video:
    st.subheader("🎞️ 04 • Final Video")
    if st.button("🎬 Render Final MP4",use_container_width=True):
        try:
            vp=save_file(video,Path(video.name).suffix or ".mp4")
            ap=Path(st.session_state.voice) if st.session_state.get("voice") else None
            if uploaded_voice: ap=save_file(uploaded_voice,Path(uploaded_voice.name).suffix or ".mp3")
            srt=external.getvalue().decode("utf-8-sig") if external else ""
            with st.spinner("Final MP4 render လုပ်နေပါတယ်..."): out=render(vp,ap,srt)
            data=out.read_bytes(); st.video(data)
            st.download_button("📥 Final MP4 Download",data,"yoon_recap_final.mp4","video/mp4",use_container_width=True)
        except Exception as e: st.error(f"Render Error: {e}")

st.divider(); st.caption("Yoon Recap • Streamlit")
