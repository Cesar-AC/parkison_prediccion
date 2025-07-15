# -------------------------------
# IMPORTS
# -------------------------------
import os, joblib, numpy as np, parselmouth, librosa, soundfile as sf, nolds
from parselmouth.praat import call
# -------------------------------
# 1) CARGAR EL NUEVO PIPELINE
# -------------------------------
# Guardaste el pipeline así: {'scaler': StandardScaler(), 'model': SVC(...)}
# ⇨  carpeta /models/  ──┐
PIPE_PATH = "models/svm_mcc_final.joblib"
pipe      = joblib.load(PIPE_PATH)
escalador = pipe["scaler"]         # StandardScaler
modelo    = pipe["model"]          # SVC entrenado



MODEL_FEATURES = ["spread1", "MDVP:APQ", "MDVP:Shimmer"]
RANGE = {
    "spread1":      (-7.964984, -2.434031),
    "MDVP:APQ":     ( 0.007190,  0.137780),
    "MDVP:Shimmer": ( 0.009540,  0.119080),
}

def extract_parkinson_features(wav_path: str) -> dict:
    # — preprocesado igual que antes —
    y, sr = librosa.load(wav_path, sr=None)
    y, _ = librosa.effects.trim(y, top_db=20)
    if y.size == 0:
        raise ValueError("Audio vacío")
    y = y / np.max(np.abs(y))
    tmp = wav_path.replace(".wav", "_pp.wav")
    sf.write(tmp, y, sr)

    snd = parselmouth.Sound(tmp)
    pp  = call(snd, "To PointProcess (periodic, cc)", 75, 500)

    # 1) spread1 (misma fórmula que en entrenamiento)
    f0 = snd.to_pitch().selected_array["frequency"]
    f0 = f0[f0>0]
    if f0.size:
        fo_bar = np.mean(f0)
        spread1 = np.log(np.mean(np.abs(f0 - fo_bar)) / fo_bar)
    else:
        spread1 = np.nan

    # 2) MDVP:APQ (shimmer apq) — prueba tres métodos
    apq = np.nan
    for metodo in ["Get shimmer (apq)", "Get shimmer (apq3)", "Get shimmer (apq5)"]:
        try:
            val = call([snd, pp], metodo,
                       0, 0,      # time range
                       1e-4, 0.02, 1.3, 1.6)
            if not np.isnan(val):
                apq = val
                break
        except parselmouth.PraatError:
            continue

    # 3) MDVP:Shimmer (local)
    try:
        shimmer = call([snd, pp],
                       "Get shimmer (local)",
                       0, 0, 1e-4, 0.02, 1.3, 1.6)
    except parselmouth.PraatError:
        shimmer = np.nan

    # limpio archivo temporal
    try: os.remove(tmp)
    except OSError: pass

    # convierto NaN→0.0 para clipping y devuelvo solo las 3
    return {
        "spread1":      float(0.0 if np.isnan(spread1) else spread1),
        "MDVP:APQ":     float(0.0 if np.isnan(apq)      else apq),
        "MDVP:Shimmer": float(0.0 if np.isnan(shimmer) else shimmer)
    }

def predict_parkinson(wav_path: str):
    raw     = extract_parkinson_features(wav_path)
    clipped = { f: np.clip(raw[f], *RANGE[f]) for f in MODEL_FEATURES }
    X       = np.array([clipped[f] for f in MODEL_FEATURES]).reshape(1,-1)
    Xs      = escalador.transform(X)
    y       = modelo.predict(Xs)[0]
    p       = modelo.predict_proba(Xs)[0]
    scaled  = { f: Xs[0,i] for i,f in enumerate(MODEL_FEATURES) }
    return raw, clipped, scaled, y, p