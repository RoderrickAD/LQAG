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
        self.reader = easyocr.Reader(['de'], gpu=torch.cuda.is_available(), verbose=False)
        self.tts = None
        
    def load_tts_model(self):
        if self.tts is None:
            logging.info("--- Lade TTS Modell (XTTS v2) ---")
            
            if torch.cuda.is_available():
                device = "cuda"
                logging.info("🚀 NVIDIA GPU gefunden! Aktiviere Turbo-Modus.")
                torch.backends.cudnn.benchmark = True
                torch.backends.cuda.matmul.allow_tf32 = True 
                torch.backends.cudnn.allow_tf32 = True
            else:
                device = "cpu"
                logging.warning("⚠️ Keine GPU gefunden. Nutze CPU.")

            try:
                # DEBUG: Wir lassen stderr an, damit wir Fehler sehen!
                # if sys.stdout is None: sys.stdout = NullWriter()
                # if sys.stderr is None: sys.stderr = NullWriter()

                config_path = os.path.join(os.getcwd(), "resources", "models.json")
                if os.path.exists(config_path):
                    logging.info(f"PATCH: Nutze Config-Datei aus: {config_path}")
                    def patched_get_models_file_path(self): return config_path
                    TTS.get_models_file_path = patched_get_models_file_path

                def patched_ask_tos(self, output_path): return True 
                ModelManager.ask_tos = patched_ask_tos

                self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", progress_bar=False).to(device)
                logging.info(f"✅ TTS Modell erfolgreich geladen auf: {device.upper()}")
            except Exception as e:
                logging.critical(f"❌ FEHLER beim Laden des Modells: {e}")
                logging.debug(traceback.format_exc())

    def run_process(self, resources_path, reference_audio, on_audio_ready, filter_pattern=None):
        # Wir loggen HIER, ob der Aufruf überhaupt ankommt
        logging.info(f"Worker Dispatch: Audio={reference_audio}, Filter={filter_pattern}")
        
        # Thread starten
        thread = threading.Thread(target=self._process, args=(resources_path, reference_audio, on_audio_ready, filter_pattern))
        thread.start()

    def clean_and_optimize_text(self, raw_text, filter_pattern):
        clean_base = raw_text.replace("\n", " ") 
        clean_base = re.sub(r'\s+', ' ', clean_base).strip()
        clean_base = re.sub(r"[‘´`’]", "'", clean_base)
        
        filtered_text = clean_base

        if filter_pattern:
            try:
                matches = re.findall(filter_pattern, clean_base, re.DOTALL)
                if matches:
                    filtered_text = " ".join(matches)
                    logging.info(f"Filter aktiv ({len(matches)} Blöcke gefunden).")
                else:
                    logging.warning(f"Filter '{filter_pattern}' hat nichts gefunden! -> FALLBACK.")
                    filtered_text = clean_base 
            except Exception as e:
                logging.error(f"Regex Fehler: {e}")
                filtered_text = clean_base

        raw_sentences = re.split(r'(?<=[.!?])\s+', filtered_text)
        optimized_sentences = []
        current_chunk = ""
        
        for sent in raw_sentences:
            sent = sent.strip()
            if not sent: continue
            if len(current_chunk) + len(sent) < 150:
                if len(current_chunk) < 20 or len(current_chunk) > 0:
                    current_chunk += " " + sent
                else:
                    current_chunk = sent
            else:
                optimized_sentences.append(current_chunk.strip())
                current_chunk = sent
        
        if current_chunk:
            optimized_sentences.append(current_chunk.strip())
            
        return " ".join(optimized_sentences)

    def _process(self, res_path, ref_audio, callback, filter_pattern):
        # SOFORT EIN TRY-CATCH UM ALLES, DAMIT WIR DEN FEHLER FANGEN
        try:
            logging.info("--- Starte Scan-Prozess ---")
            
            if self.tts is None:
                logging.error("ABBRUCH: TTS Modell ist noch nicht geladen.")
                return
                
            try:
                for old_file in glob.glob("output_speech_*.wav"):
                    try: os.remove(old_file)
                    except: pass
            except: pass

            path_tl = os.path.join(res_path, "template_tl.png")
            path_br = os.path.join(res_path, "template_br.png")

            logging.debug("Mache Screenshot...")
            sc_raw = pyautogui.screenshot()
            sc = cv2.cvtColor(np.array(sc_raw), cv2.COLOR_RGB2BGR)
            cv2.imwrite("debug_1_screenshot.png", sc)

            def find_template(img, templ_p):
                if not os.path.exists(templ_p): return None
                templ = cv2.imread(templ_p)
                if templ is None: return None
                h, w = templ.shape[:2]
                res = cv2.matchTemplate(img, templ, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                cv2.rectangle(img, max_loc, (max_loc[0] + w, max_loc[1] + h), (0, 0, 255), 2)
                return max_val, max_loc, w, h

            res_tl = find_template(sc, path_tl)
            res_br = find_template(sc, path_br)
            cv2.imwrite("debug_3_matches.png", sc)

            if not res_tl or not res_br:
                logging.warning("Templates nicht gefunden.")
                return

            val1, loc1, w1, h1 = res_tl
            val2, loc2, w2, h2 = res_br

            x_start = loc1[0]
            y_start = loc1[1] + h1
            x_end = loc2[0] + w2
            y_end = loc2[1]

            if x_end <= x_start or y_end <= y_start:
                logging.error("FEHLER: Bereich ungültig.")
                return

            roi = sc_raw.crop((x_start, y_start, x_end, y_end))
            roi_np = cv2.cvtColor(np.array(roi), cv2.COLOR_RGB2BGR)
            cv2.imwrite("debug_2_roi.png", roi_np)
            
            # Grayscale OCR
            gray_roi = cv2.cvtColor(roi_np, cv2.COLOR_BGR2GRAY)
            ocr_start = time.time()
            logging.debug(f"Starte OCR...")
            
            text_list = self.reader.readtext(gray_roi, detail=0, paragraph=False, workers=0, batch_size=4, reformat=False)
            
            logging.info(f"OCR-Dauer: {time.time() - ocr_start:.2f}s")
            
            raw_full_text = " ".join(text_list)
            
            # Debug Text speichern
            try:
                with open("debug_ocr_text.txt", "w", encoding="utf-8") as f:
                    f.write(f"RAW: {raw_full_text}\nFILTER: {filter_pattern}\n")
            except: pass

            final_text = self.clean_and_optimize_text(raw_full_text, filter_pattern)
            
            logging.info(f"ERKANNT: '{final_text[:50]}...' ({len(final_text)} Zeichen)")

            if not final_text.strip():
                logging.warning("Kein Text erkannt.")
                return

            logging.info(f"Generiere Audio-Stream...")
            
            # --- STREAMING ---
            try:
                stream_generator = self.tts.synthesizer.tts(
                    text=final_text,
                    speaker_wav=ref_audio,
                    language="de",
                    stream=True,
                    split_sentences=True,
                    speed=1.1
                )
                
                # Generator übergeben
                callback(stream_generator)
                logging.info("Stream übergeben!")
                
            except Exception as e:
                logging.error(f"TTS Streaming Fehler: {e}")
                logging.error(traceback.format_exc())

        except Exception as e:
            # DIESER BLOCK FÄNGT JETZT ALLES AB
            logging.critical(f"FATALER FEHLER IM WORKER THREAD: {e}")
            logging.critical(traceback.format_exc())
            # Wir schreiben es auch in eine Notfall-Datei, falls Logging versagt
            try:
                with open("CRASH_LOG.txt", "w") as f:
                    f.write(str(e))
                    f.write(traceback.format_exc())
            except: pass
