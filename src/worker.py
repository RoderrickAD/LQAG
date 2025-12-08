import threading
import os
import cv2
import numpy as np
import pyautogui
import easyocr
import logging
import traceback
import sys
import torch
import torchaudio
import soundfile as sf
import time
import glob

# --- FIX 0: PYTORCH 2.6 KOMPATIBILITÄT ---
_original_load = torch.load
def patched_torch_load(*args, **kwargs):
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
    return _original_load(*args, **kwargs)
torch.load = patched_torch_load

# --- FIX 3: AUDIO BACKEND ---
def manual_audio_load(filepath, *args, **kwargs):
    data, samplerate = sf.read(filepath)
    if data.ndim == 1:
        data = data.reshape(-1, 1)
    data = data.T 
    tensor = torch.from_numpy(data).float()
    return tensor, samplerate
torchaudio.load = manual_audio_load
# ---------------------------------------------

from TTS.api import TTS
from TTS.utils.manage import ModelManager 

class NullWriter:
    def write(self, data): pass
    def flush(self): pass

class Worker:
    def __init__(self):
        logging.info("Initialisiere EasyOCR...")
        # gpu=True beschleunigt OCR massiv, wenn CUDA verfügbar ist
        self.reader = easyocr.Reader(['de'], gpu=torch.cuda.is_available())
        self.tts = None
        
    def load_tts_model(self):
        if self.tts is None:
            logging.info("--- Lade TTS Modell (XTTS v2) ---")
            
            # --- PERFORMANCE: GPU OPTIMIERUNGEN ---
            if torch.cuda.is_available():
                device = "cuda"
                logging.info("🚀 NVIDIA GPU gefunden! Aktiviere Turbo-Modus.")
                
                # Optimiert die Rechenkerne für deine spezifische Karte
                torch.backends.cudnn.benchmark = True
                # Erlaubt schnellere Matrix-Berechnungen (kleiner Qualitätsverlust, massiver Speedup)
                torch.backends.cuda.matmul.allow_tf32 = True 
                torch.backends.cudnn.allow_tf32 = True
            else:
                device = "cpu"
                logging.warning("⚠️ Keine GPU gefunden. Nutze CPU.")

            try:
                # --- FIXES ---
                if sys.stdout is None: sys.stdout = NullWriter()
                if sys.stderr is None: sys.stderr = NullWriter()

                config_path = os.path.join(os.getcwd(), "resources", "models.json")
                if os.path.exists(config_path):
                    logging.info(f"PATCH: Nutze Config-Datei aus: {config_path}")
                    def patched_get_models_file_path(self): return config_path
                    TTS.get_models_file_path = patched_get_models_file_path

                def patched_ask_tos(self, output_path): return True 
                ModelManager.ask_tos = patched_ask_tos

                # Laden
                self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", progress_bar=False).to(device)
                logging.info(f"✅ TTS Modell erfolgreich geladen auf: {device.upper()}")
                
            except Exception as e:
                logging.critical(f"❌ FEHLER beim Laden des Modells: {e}")
                logging.debug(traceback.format_exc())

    def run_process(self, resources_path, reference_audio, on_audio_ready):
        thread = threading.Thread(target=self._process, args=(resources_path, reference_audio, on_audio_ready))
        thread.start()

    def _process(self, res_path, ref_audio, callback):
        logging.info("--- Starte Scan-Prozess ---")
        
        if self.tts is None:
            logging.error("ABBRUCH: TTS Modell ist noch nicht geladen.")
            return
            
        # Cleanup
        try:
            for old_file in glob.glob("output_speech_*.wav"):
                try: os.remove(old_file)
                except: pass
        except Exception: pass

        path_tl = os.path.join(res_path, "template_tl.png")
        path_br = os.path.join(res_path, "template_br.png")

        try:
            # --- SCREENSHOT & MATCHING ---
            logging.debug("Mache Screenshot...")
            sc_raw = pyautogui.screenshot()
            sc = cv2.cvtColor(np.array(sc_raw), cv2.COLOR_RGB2BGR)
            # Wir speichern nicht mehr jedes Mal Bilder, das kostet Zeit.
            # Nur bei Bedarf einkommentieren.
            # cv2.imwrite("debug_1_screenshot.png", sc)

            def find_template(img, templ_p):
                if not os.path.exists(templ_p): return None
                templ = cv2.imread(templ_p)
                if templ is None: return None
                h, w = templ.shape[:2]
                res = cv2.matchTemplate(img, templ, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                return max_val, max_loc, w, h

            res_tl = find_template(sc, path_tl)
            res_br = find_template(sc, path_br)

            if not res_tl or not res_br:
                logging.warning("Templates nicht gefunden (F8 Setup gemacht?).")
                return

            val1, loc1, w1, h1 = res_tl
            val2, loc2, w2, h2 = res_br

            # Toleranz
            if val1 < 0.8 or val2 < 0.8:
                logging.warning(f"Ecken unsicher ({val1:.2f} / {val2:.2f}).")

            x_start = loc1[0]
            y_start = loc1[1] + h1
            x_end = loc2[0] + w2
            y_end = loc2[1]

            if x_end <= x_start or y_end <= y_start:
                logging.error("FEHLER: Bereich ungültig.")
                return

            roi = sc_raw.crop((x_start, y_start, x_end, y_end))
            roi_np = cv2.cvtColor(np.array(roi), cv2.COLOR_RGB2BGR)
            
            # --- OCR ---
            logging.debug("Lese Text...")
            text_list = self.reader.readtext(roi_np, detail=0, paragraph=True)
            full_text = " ".join(text_list)
            
            # Bereinigen von Newlines für flüssigeres Lesen
            full_text = full_text.replace("\n", " ").strip()
            
            logging.info(f"ERKANNT ({len(full_text)} Zeichen): '{full_text[:50]}...'")

            if not full_text:
                logging.warning("Kein Text erkannt.")
                return

            # --- TTS GENERIERUNG ---
            logging.info(f"Generiere Audio (High Performance)...")
            timestamp = int(time.time())
            out_path = f"output_speech_{timestamp}.wav"
            
            # split_sentences=True ist WICHTIG für Speed bei langen Texten.
            # Die KI berechnet Satz für Satz, statt alles auf einmal in den Speicher zu laden.
            self.tts.tts_to_file(
                text=full_text, 
                speaker_wav=ref_audio, 
                language="de", 
                file_path=out_path,
                split_sentences=True 
            )
            
            logging.info("Audio fertig!")
            callback(out_path)

        except Exception as e:
            logging.error(f"WORKER FEHLER: {e}")
            logging.error(traceback.format_exc())
