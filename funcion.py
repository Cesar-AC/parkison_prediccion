# -------------------------------
# IMPORTS
# -------------------------------
import os, joblib, numpy as np, parselmouth, librosa, soundfile as sf, nolds
from parselmouth.praat import call

from sklearn.pipeline        import Pipeline
from sklearn.preprocessing   import StandardScaler
from sklearn.ensemble        import VotingClassifier, StackingClassifier
from sklearn.linear_model    import LogisticRegression
from sklearn.ensemble        import RandomForestClassifier
from xgboost                 import XGBClassifier
from sklearn.svm             import SVC
# -------------------------------
# 1) CARGAR EL NUEVO PIPELINE
# -------------------------------
# Guardaste el pipeline así: {'scaler': StandardScaler(), 'model': SVC(...)}
# ⇨  carpeta /models/  ──┐
PIPE_SOFT  = "models/soft_voting_parkinson.joblib"
PIPE_STACK = "models/stacking_parkinson.joblib"

pipe_soft  = joblib.load(PIPE_SOFT)   # Pipeline(StandardScaler + SoftVoting)
pipe_stack = joblib.load(PIPE_STACK)  # Pipeline(StandardScaler + Stacking)



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

def predict_parkinson(wav_path: str, method: str = "soft"):
    """
    method: "soft" para Voting suave, "stack" para Stacking
    """

    # --- 2) Extrae y recorta características igual que antes ---
    raw     = extract_parkinson_features(wav_path)
    clipped = { f: np.clip(raw[f], *RANGE[f]) for f in MODEL_FEATURES }
    X       = np.array([clipped[f] for f in MODEL_FEATURES]).reshape(1, -1)

    # --- 3) Escalado interno + predicción ---
    if method == "soft":
        y_pred = pipe_soft.predict(X)[0]
        proba  = pipe_soft.predict_proba(X)[0]
        scaler = pipe_soft.named_steps['scaler']
    elif method == "stack":
        y_pred = pipe_stack.predict(X)[0]
        proba  = pipe_stack.predict_proba(X)[0]
        scaler = pipe_stack.named_steps['scaler']
    else:
        raise ValueError("method debe ser 'soft' o 'stack'")

    # --- 4) Si quieres exponer también las features escaladas ---
    scaled_vals = scaler.transform(X)[0]
    scaled = { f: scaled_vals[i] for i, f in enumerate(MODEL_FEATURES) }

    return raw, clipped, scaled, y_pred, proba