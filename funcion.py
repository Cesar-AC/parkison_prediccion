import os, joblib, numpy as np, parselmouth, librosa, soundfile as sf, nolds

# ─── modelo ─────────────────────────
modelo    = joblib.load("models/modelo_knn.pkl")
escalador = joblib.load("models/scalador.pkl")

# ─── 14 features (orden idéntico al entrenamiento) ─────────────────
MODEL_FEATURES = [
    "spread1","PPE","spread2",
    "MDVP:Fo(Hz)","MDVP:Flo(Hz)",
    "MDVP:Shimmer","MDVP:APQ",
    "HNR","Shimmer:APQ5",
    "MDVP:Shimmer(dB)","Shimmer:APQ3",
    "Shimmer:DDA","MDVP:Jitter(Abs)",
    "RPDE"
]

# ─── rangos del CSV para clipping ──────────────────────────────────
RANGE = {
    "spread1":(-7.964984,-2.434031),"PPE":(0.044539,0.527367),
    "spread2":(0.006274,0.450493),
    "MDVP:Fo(Hz)":(88.333,260.105),"MDVP:Flo(Hz)":(65.476,239.170),
    "MDVP:Shimmer":(0.00954,0.11908),"MDVP:APQ":(0.00719,0.13778),
    "HNR":(8.441,33.047),"Shimmer:APQ5":(0.00570,0.07940),
    "MDVP:Shimmer(dB)":(0.085,1.302),"Shimmer:APQ3":(0.00455,0.05647),
    "Shimmer:DDA":(0.01364,0.16942),"MDVP:Jitter(Abs)":(7e-6,2.6e-4),
    "RPDE":(0.25657,0.685151)
}

def pcall(obj, fn,*a):
    try: return parselmouth.praat.call(obj,fn,*a)
    except: return np.nan

# ─── extracción ────────────────────────────────────────────────────
def extract_parkinson_features(wav:str)->dict:
    # 0) trim & normalise
    y, sr     = librosa.load(wav, sr=None)
    y,_       = librosa.effects.trim(y, top_db=20)
    if y.size==0: raise ValueError("audio vacío")
    y         = y/np.max(np.abs(y)); tmp=wav.replace(".wav","_pp.wav")
    sf.write(tmp,y,sr)

    snd       = parselmouth.Sound(tmp)
    pp        = pcall(snd,"To PointProcess (periodic, cc)",75,500)

    # 1) F0
    f0        = snd.to_pitch().selected_array["frequency"]
    f0        = f0[f0>0]
    fo_bar    = np.mean(f0) if f0.size else np.nan
    fo_min    = np.min(f0)  if f0.size else np.nan

    # 2) spread1 & spread2
    if f0.size:
        spread1 = np.log(np.mean(np.abs(f0-fo_bar))/fo_bar)
        spread2 = np.std(np.diff(f0))/fo_bar
    else: spread1=spread2=np.nan

    # 3) PPE
    if f0.size:
        semi = 12*np.log2(f0/55.0)
        p    = np.histogram(semi,20,density=True)[0]
        p    = p[p>0]
        ppe  = -np.sum(p*np.log(p))/np.log(len(p))
    else: ppe=np.nan

    # 4) jitter abs
    jit_abs = pcall(pp,"Get jitter (local, absolute)",0,0,1e-4,0.02,1.3)

    # 5) shimmer & derivados
    sh     = pcall([snd,pp],"Get shimmer (local)",0,0,1e-4,0.02,1.3,1.6)
    sh_db  = pcall([snd,pp],"Get shimmer (local, dB)",0,0,1e-4,0.02,1.3,1.6)
    if np.isnan(sh_db) and not np.isnan(sh) and sh>0:
        sh_db = 20*np.log10(1+sh)
    apq3   = pcall([snd,pp],"Get shimmer (apq3)",0,0,1e-4,0.02,1.3,1.6)
    apq5   = pcall([snd,pp],"Get shimmer (apq5)",0,0,1e-4,0.02,1.3,1.6)
    apq    = pcall([snd,pp],"Get shimmer (apq)", 0,0,1e-4,0.02,1.3,1.6)
    if np.isnan(apq) and not (np.isnan(apq3) or np.isnan(apq5)):
        apq = (apq3+apq5)/2          # fallback
    dda    = pcall([snd,pp],"Get shimmer (dda)",0,0,1e-4,0.02,1.3,1.6)

    # 6) HNR
    hnr    = pcall(pcall(snd,"To Harmonicity (cc)",0.01,75,0.1,1.0),"Get mean",0,0)

    # 7) RPDE
    rpde   = pcall(pcall(snd,"To RPDE",0.02,0.2,18,1.0),"Get mean",0,0)
    if np.isnan(rpde):
        try: rpde = nolds.corr_dim(y, emb_dim=2)
        except: rpde = np.nan

    try: os.remove(tmp)
    except: pass

    feats = {
        "spread1":spread1,"PPE":ppe,"spread2":spread2,
        "MDVP:Fo(Hz)":fo_bar,"MDVP:Flo(Hz)":fo_min,
        "MDVP:Shimmer":sh,"MDVP:APQ":apq,
        "HNR":hnr,"Shimmer:APQ5":apq5,
        "MDVP:Shimmer(dB)":sh_db,"Shimmer:APQ3":apq3,
        "Shimmer:DDA":dda,"MDVP:Jitter(Abs)":jit_abs,
        "RPDE":rpde
    }
    return {k:(0.0 if np.isnan(v) else float(v)) for k,v in feats.items()}

# ─── inferencia con clipping ───────────────────────────────────────
def predict_parkinson(wav:str):
    raw = extract_parkinson_features(wav)
    # 1. clip a los rangos del CSV
    clipped = {f: np.clip(raw[f], *RANGE[f]) for f in MODEL_FEATURES}
    # 2. escalar y predecir
    X   = np.array([clipped[f] for f in MODEL_FEATURES]).reshape(1,-1)
    Xs  = escalador.transform(X)
    y   = modelo.predict(Xs)[0]
    p   = modelo.predict_proba(Xs)[0]
    # devuelvo también el vector escalado por si quieres verlo
    scaled = {f: Xs[0,i] for i,f in enumerate(MODEL_FEATURES)}
    return raw, clipped, scaled, y, p
