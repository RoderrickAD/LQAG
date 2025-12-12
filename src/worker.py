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
import re

# --- FIXES ---
_original_load = torch.load
def patched_torch_load(*args, **kwargs):
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
    return _original_load(*args, **kwargs)
torch.load = patched_torch_load

def manual_audio_load(filepath, *args, **kwargs):
    data, samplerate = sf.read(filepath)
    if data.ndim == 1:
        data = data.reshape(-1, 1)
    data = data.T 
    tensor = torch.from_numpy(data).float()
    return tensor, samplerate
torchaudio.load = manual_audio_load
# -------------

from TTS.api import TTS
from TTS.utils.manage import ModelManager 

class NullWriter:
    def write(self, data): pass
    def flush(self): pass

class Worker:
    def __init__(self):
        print("DEBUG: Worker __init__ gestartet")
        logging.info("Initialisiere EasyOCR...")
        self.reader = easyocr.Reader(['de'], gpu=torch.cuda.is_available(), verbose=False)
        self.tts = None
        print("DEBUG: Worker __init__ fertig")
        
    def load_tts_model(self):
        if self.tts is None:
            logging.info("--- Lade TTS Modell ---")
            device = "cuda" if torch.cuda.is_available() else "cpu"
            
            try:
                # WICHTIG: Kein NullWriter, damit wir Fehler sehen!
                # if sys.stdout is None: sys.stdout = NullWriter()
                
                config_path = os.path.join(os.getcwd(), "resources", "models.json")
                if os.path.exists(config_path):
                    def patched_get_models_file_path(self): return config_path
                    TTS.get_models_file_path = patched_get_models_file_path

                def patched_ask_tos(self, output_path): return True 
                ModelManager.ask_tos = patched_ask_tos

                self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", progress_bar=False).to(device)
                logging.info(f"✅ TTS Modell geladen auf: {device}")
            except Exception as e:
                logging.critical(f"❌ MODEL LOAD ERROR: {e}")
                traceback.print_exc()

    def run_process(self, resources_path, reference_audio, on_audio_ready, filter_pattern=None):
        # Diagnose-Ausgabe direkt in die Konsole
        print(f"DEBUG: run_process aufgerufen! Pattern: {filter_pattern}")
        
        thread = threading.Thread(target=self._process, args=(resources_path, reference_audio, on_audio_ready, filter_pattern))
        thread.start()
        print("DEBUG: Thread gestartet.")

    def clean_and_optimize_text(self, raw_text, filter_pattern):
        clean_base = raw_text.replace("\n", " ").strip()
        clean_base = re.sub(r'\s+', ' ', clean_base)
        clean_base = re.sub(r"[‘´`’]", "'", clean_base)
        
        filtered_text = clean_base

        if filter_pattern:
            try:
                matches = re.findall(filter_pattern, clean_base, re.DOTALL)
                if matches:
                    filtered_text = " ".join(matches)
                else:
                    logging.warning("Filter leer -> Fallback.")
                    filtered_text = clean_base 
            except:
                filtered_text = clean_base

        return filtered_text

    def _process(self, res_path, ref_audio, callback, filter_pattern):
        print("DEBUG: Bin im Thread _process angekommen!") # Lebenszeichen 1
        
        try:
            logging.info("--- Starte Scan-Prozess ---")
            
            if self.tts is None:
                logging.error("ABBRUCH: TTS Modell fehlt.")
                return

            # Teste Bildaufnahme explizit
            print("DEBUG: Prüfe Screenshot Funktion...")
            try:
                sc_raw = pyautogui.screenshot()
                print("DEBUG: Screenshot erfolgreich!")
                sc = cv2.cvtColor(np.array(sc_raw), cv2.COLOR_RGB2BGR)
            except Exception as e_scr:
                logging.critical(f"FEHLER BEI BILDAUFNAHME: {e_scr}")
                return

            path_tl = os.path.join(res_path, "template_tl.png")
            path_br = os.path.join(res_path, "template_br.png")

            print(f"DEBUG: Suche Templates in {res_path}")
            
            # Helper
            def find_template(img, templ_p):
                if not os.path.exists(templ_p):
                    print(f"DEBUG: Template fehlt: {templ_p}")
                    return None
                templ = cv2.imread(templ_p)
                if templ is None: return None
                h, w = templ.shape[:2]
                res = cv2.matchTemplate(img, templ, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                return max_val, max_loc, w, h

            res_tl = find_template(sc, path_tl)
            res_br = find_template(sc, path_br)

            if not res_tl or not res_br:
                logging.warning("Templates nicht gefunden! (F8 neu machen)")
                return

            val1, loc1, w1, h1 = res_tl
            val2, loc2, w2, h2 = res_br
            
            print(f"DEBUG: Matches gefunden: {val1:.2f} / {val2:.2f}")

            x_start = loc1[0]
            y_start = loc1[1] + h1
            x_end = loc2[0] + w2
            y_end = loc2[1]

            if x_end <= x_start or y_end <= y_start:
                logging.error(f"FEHLER: Ungültige Koordinaten: X:{x_start}-{x_end} Y:{y_start}-{y_end}")
                return

            print("DEBUG: Schneide Bild aus...")
            roi = sc_raw.crop((x_start, y_start, x_end, y_end))
            roi_np = cv2.cvtColor(np.array(roi), cv2.COLOR_RGB2BGR)
            
            # OCR
            print("DEBUG: Starte OCR...")
            gray_roi = cv2.cvtColor(roi_np, cv2.COLOR_BGR2GRAY)
            text_list = self.reader.readtext(gray_roi, detail=0, paragraph=False, workers=0, reformat=False)
            
            raw_text = " ".join(text_list)
            print(f"DEBUG: OCR fertig. Textlänge: {len(raw_text)}")
            
            final_text = self.clean_and_optimize_text(raw_full_text=raw_text, filter_pattern=filter_pattern)
            logging.info(f"ERKANNT: '{final_text[:30]}...'")

            if not final_text.strip():
                logging.warning("Kein Text erkannt.")
                return

            print("DEBUG: Starte TTS Streaming...")
            try:
                stream_generator = self.tts.synthesizer.tts(
                    text=final_text,
                    speaker_wav=ref_audio,
                    language="de",
                    stream=True,
                    split_sentences=True,
                    speed=1.1
                )
                callback(stream_generator)
                print("DEBUG: Stream übergeben.")
                
            except Exception as e:
                logging.error(f"TTS Fehler: {e}")

        except Exception as e:
            print(f"CRITICAL WORKER CRASH: {e}")
            logging.critical(f"WORKER CRASH: {e}")
            logging.critical(traceback.format_exc())
