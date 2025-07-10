import warnings
warnings.filterwarnings("ignore", category=UserWarning)
from sklearn.exceptions import InconsistentVersionWarning
warnings.filterwarnings("ignore", category=InconsistentVersionWarning)

import joblib
import parselmouth
import librosa
import nolds
import numpy as np
import sys
import pandas as pd

# === Carga del modelo y escalador ===
modelo    = joblib.load('models/modelo_knn.pkl')
escalador = joblib.load('models/escalador.pkl')

# === Lista de features que usa tu modelo ===
MODEL_FEATURES = [
    'spread1', 'PPE', 'spread2',
    'MDVP:Fo(Hz)', 'MDVP:Flo(Hz)',
    'MDVP:Shimmer', 'MDVP:APQ',
    'HNR', 'Shimmer:APQ5',
    'MDVP:Shimmer(dB)', 'Shimmer:APQ3',
    'Shimmer:DDA',
    'MDVP:Jitter(Abs)', 'RPDE'
]

def safe_call(*praat_args):
    """Envuelve parselmouth.praat.call y devuelve np.nan si falla."""
    try:
        return parselmouth.praat.call(*praat_args)
    except Exception:
        return np.nan

# === Extracción de características ===
def extract_parkinson_features(wav_path):
    """Extrae las características acústicas de un archivo .wav"""
    try:
        snd = parselmouth.Sound(wav_path)
        pp = safe_call(snd, "To PointProcess (periodic, cc)", 75, 500)

        # — Pitch — 
        pitch = snd.to_pitch()
        freqs = pitch.selected_array['frequency']
        freqs = freqs[freqs > 0]  # Solo frecuencias positivas
        mdvp_fo  = freqs.mean() if freqs.size else np.nan
        mdvp_flo = freqs.min()  if freqs.size else np.nan
        mdvp_fhi = freqs.max()  if freqs.size else np.nan

        # — Jitter — 
        jitter_local = safe_call(pp, "Get jitter (local)", 0,0,0.0001,0.02,1.3)
        jitter_rap   = safe_call(pp, "Get jitter (rap)",   0,0,0.0001,0.02,1.3)
        jitter_ppq   = safe_call(pp, "Get jitter (ppq)",   0,0,0.0001,0.02,1.3)
        jitter_ddp   = safe_call(pp, "Get jitter (ddp)",   0,0,0.0001,0.02,1.3)

        # Si hay múltiples valores en jitter_rap, tomamos solo el primero
        jitter_rap = jitter_rap[0] if isinstance(jitter_rap, np.ndarray) else jitter_rap

        # — Shimmer —
        shimmer_loc = safe_call([snd, pp], "Get shimmer (local)",    0,0,0.0001,0.02,1.3,1.6)
        shimmer_db  = safe_call([snd, pp], "Get shimmer (local, dB)",0,0,0.0001,0.02,1.3,1.6)
        apq3        = safe_call([snd, pp], "Get shimmer (apq3)",     0,0,0.0001,0.02,1.3,1.6)
        apq5        = safe_call([snd, pp], "Get shimmer (apq5)",     0,0,0.0001,0.02,1.3,1.6)
        apq         = safe_call([snd, pp], "Get shimmer (apq)",      0,0,0.0001,0.02,1.3,1.6)
        dda         = safe_call([snd, pp], "Get shimmer (dda)",      0,0,0.0001,0.02,1.3,1.6)

        # — Harmonicity — 
        hnr_obj = safe_call(snd, "To Harmonicity (cc)", 0.01,75,0.1,1.0)
        hnr     = safe_call(hnr_obj, "Get mean", 0,0)
        nhr     = (1.0/(hnr+1e-6)) if not np.isnan(hnr) else np.nan

        # — Nonlinear — 
        rpde_obj = safe_call(snd, "To RPDE", 0.02,0.2,18,1.0)
        rpde     = safe_call(rpde_obj, "Get mean", 0,0)
        dfa_obj  = safe_call(snd, "To DFA", 0.1,0.1,500)
        dfa      = safe_call(dfa_obj, "Get alpha", 0,0)

        # — Spectral & fractal —
        y, sr = librosa.load(wav_path, sr=None)
        S     = np.abs(librosa.stft(y))
        centroids = librosa.feature.spectral_centroid(S=S)
        bandwidths = librosa.feature.spectral_bandwidth(S=S, centroid=centroids)
        spread1 = bandwidths.mean()
        spread2 = librosa.feature.spectral_contrast(S=S, sr=sr).mean()

        intervals = np.diff(pp.selected_array['x']) if hasattr(pp, 'selected_array') else np.array([])
        probs     = np.histogram(intervals, bins=20, density=True)[0] if intervals.size else np.array([])
        probs     = probs[probs > 0]
        ppe       = -np.sum(probs * np.log(probs)) if probs.size else np.nan

        # Crear el diccionario de características
        feats = {
            'spread1': spread1,
            'PPE': ppe,
            'spread2': spread2,
            'MDVP:Fo(Hz)': mdvp_fo,
            'MDVP:Fhi(Hz)': mdvp_fhi,
            'MDVP:Flo(Hz)': mdvp_flo,
            'MDVP:Jitter(%)': jitter_local * 100 if not np.isnan(jitter_local) else np.nan,
            'MDVP:Jitter(Abs)': jitter_local,
            'MDVP:RAP': jitter_rap,
            'MDVP:PPQ': jitter_ppq,
            'Jitter:DDP': jitter_ddp,
            'MDVP:Shimmer': shimmer_loc,
            'MDVP:Shimmer(dB)': shimmer_db,
            'Shimmer:APQ3': apq3,
            'Shimmer:APQ5': apq5,
            'MDVP:APQ': apq,
            'Shimmer:DDA': dda,
            'NHR': nhr,
            'HNR': hnr,
            'RPDE': rpde,
            'DFA': dfa
        }

        # Reemplazar NaN con 0
        feats = {k: (v if not np.isnan(v) else 0) for k, v in feats.items()}

        return feats

    except Exception as e:
        print(f"Error en la extracción de características: {e}")
        return None


# === Proceso de prueba ===
def run_test(wav_path):
    feats = extract_parkinson_features(wav_path)
    if feats:
        print(f"\n📊 Características extraídas de '{wav_path}':\n")
        df_feats = pd.DataFrame(list(feats.items()), columns=["Feature", "Value"])
        print(df_feats.to_string(index=False))
    else:
        print("Error al extraer las características del archivo.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python test_backend.py recording.wav")
        sys.exit(1)

    # Llamada a la función para probar
    run_test(sys.argv[1])
