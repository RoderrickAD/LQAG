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
        # gpu=True ist PFLICHT für Geschwindigkeit.
        # verbose=False verhindert Spam in der Konsole.
        self.reader = easyocr.Reader(['de'], gpu=torch.cuda.is_available(), verbose=False)
        self.tts = None
        
    def load_tts_model(self):
        if self.tts is None:
            logging.info("--- Lade TTS Modell (XTTS v2) ---")
            
            if torch.cuda.is_available():
                device = "cuda"
                logging.info("🚀 NVIDIA GPU gefunden! Aktiviere Turbo-Modus.")
                # Maximale GPU Optimierung
                torch.backends.cudnn.benchmark = True
                torch.backends.cuda.matmul.allow_tf32 = True 
                torch.backends.cudnn.allow_tf32 = True
            else:
                device = "cpu"
                logging.warning("⚠️ Keine GPU gefunden. Nutze CPU.")

            try:
                if sys.stdout is None: sys.stdout = NullWriter()
                if sys.stderr is None: sys.stderr = NullWriter()

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
        thread = threading.Thread(target=self._process, args=(resources_path, reference_audio, on_audio_ready, filter_pattern))
        thread.start()

    def clean_and_optimize_text(self, raw_text, filter_pattern):
        # 1. BASIS REINIGUNG
        clean_base = raw_text.replace("\n", " ") 
        clean_base = re.sub(r'\s+', ' ', clean_base).strip()
        
        filtered_text = clean_base

        # 2. DYNAMISCHER FILTER
        if filter_pattern:
            try:
                matches = re.findall(filter_pattern, clean_base, re.DOTALL)
                if matches:
                    filtered_text = " ".join(matches)
                    logging.info(f"Filter aktiv ({len(matches)} Treffer).")
                else:
                    logging.warning(f"Filter '{filter_pattern}' hat NICHTS gefunden!")
                    logging.warning("-> FALLBACK: Nutze den gesamten Text.")
                    filtered_text = clean_base 
            except Exception as e:
                logging.error(f"Regex Fehler: {e}")
                filtered_text = clean_base

        # 3. SATZ-OPTIMIERUNG (Deine Logik: Kurze Sätze zusammenkleben)
        raw_sentences = re.split(r'(?<=[.!?])\s+', filtered_text)
        optimized_sentences = []
        current_chunk = ""
        
        for sent in raw_sentences:
            if not sent.strip(): continue
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
        logging.info("--- Starte Scan-Prozess ---")
        
        if self.tts is None:
            logging.error("ABBRUCH: TTS Modell ist noch nicht geladen.")
            return
            
        try:
            for old_file in glob.glob("output_speech_*.wav"):
                try: os.remove(old_file)
                except: pass
        except Exception: pass

        path_tl = os.path.join(res_path, "template_tl.png")
        path_br = os.path.join(res_path, "template_br.png")

        try:
            # 1. SCREENSHOT
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
            
            # --- PERFORMANCE BOOST: GRAYSCALE ---
            # Wandelt Bild in Graustufen um (entfernt Farben) -> 3x weniger Daten
            gray_roi = cv2.cvtColor(roi_np, cv2.COLOR_BGR2GRAY)
            
            # --- START ZEITMESSUNG ---
            ocr_start_time = time.time()
            logging.debug(f"Starte OCR (Grayscale, Raw-Mode)...")
            
            # --- OCR CONFIG ---
            text_list = self.reader.readtext(
                gray_roi, 
                detail=0,           # Nur Text zurückgeben
                paragraph=False,    # Deaktiviert: Keine Absatz-Analyse (Spart Zeit!)
                workers=0,          # Deaktiviert: Kein Multiprocessing-Overhead (Spart Zeit!)
                batch_size=4,       # Kleiner Batch für kleine Bilder
                reformat=False      # Deaktiviert: Keine Bildverbesserung (Spart Zeit!)
            )
            
            ocr_end_time = time.time()
            logging.info(f"OCR-Dauer: {ocr_end_time - ocr_start_time:.2f} Sekunden.")
            # --------------------------
            
            raw_full_text = " ".join(text_list)
            
            # Debug Text Datei
            try:
                with open("debug_ocr_text.txt", "w", encoding="utf-8") as f:
                    f.write("=== RAW OCR TEXT ===\n")
                    f.write(raw_full_text + "\n\n")
                    f.write(f"=== FILTER EINSTELLUNG: {filter_pattern} ===\n\n")
            except: pass

            final_text = self.clean_and_optimize_text(raw_full_text, filter_pattern)
            
            try:
                with open("debug_ocr_text.txt", "a", encoding="utf-8") as f:
                    f.write("=== FINALER TEXT ===\n")
                    f.write(final_text)
            except: pass

            logging.info(f"ERKANNT: '{final_text[:50]}...' ({len(final_text)} Zeichen)")

            if not final_text.strip():
                logging.warning("Kein Text erkannt.")
                return

            logging.info(f"Generiere Audio...")
            timestamp = int(time.time())
            out_path = f"output_speech_{timestamp}.wav"
            
            self.tts.tts_to_file(
                text=final_text, 
                speaker_wav=ref_audio, 
                language="de", 
                file_path=out_path,
                split_sentences=True, 
                speed=1.1
            )
            
            logging.info("Audio fertig!")
            callback(out_path)

        except Exception as e:
            logging.error(f"WORKER FEHLER: {e}")
            logging.error(traceback.format_exc())
