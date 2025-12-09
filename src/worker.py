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
        # gpu=True ist wichtig für Speed
        self.reader = easyocr.Reader(['de'], gpu=torch.cuda.is_available())
        self.tts = None
        
    def load_tts_model(self):
        if self.tts is None:
            logging.info("--- Lade TTS Modell (XTTS v2) ---")
            
            if torch.cuda.is_available():
                device = "cuda"
                logging.info("🚀 NVIDIA GPU gefunden! Aktiviere Turbo-Modus.")
                # Performance Tweaks
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

    def run_process(self, resources_path, reference_audio, on_audio_ready):
        thread = threading.Thread(target=self._process, args=(resources_path, reference_audio, on_audio_ready))
        thread.start()

    # --- NEU: INTELLIGENTE TEXT-AUFBEREITUNG ---
    def clean_and_optimize_text(self, raw_text):
        # 1. ZITAT FILTER: Suche Text zwischen ' und '
        # Wir suchen nach 'blabla', ignorieren Zeilenumbrüche zwischendrin
        matches = re.findall(r"'([^']*)'", raw_text, re.DOTALL)
        
        if not matches:
            logging.warning("Keine Quest-Zitate ('...') gefunden. Nutze Fallback (ganzer Text).")
            # Fallback: Versuche zumindest das Gröbste zu reinigen
            clean_text = raw_text
        else:
            # Wir verbinden alle gefundenen Zitat-Blöcke
            clean_text = " ".join(matches)
            logging.info(f"Quest-Filter aktiv: {len(matches)} Textblöcke extrahiert.")

        # 2. BASIS REINIGUNG
        clean_text = clean_text.replace("\n", " ") # Zeilenumbrüche weg
        clean_text = re.sub(r'\s+', ' ', clean_text).strip() # Doppelte Leerzeichen weg

        # 3. SATZ-OPTIMIERUNG (Deine 20-125 Zeichen Logik)
        # Wir splitten erst grob nach Satzzeichen
        raw_sentences = re.split(r'(?<=[.!?])\s+', clean_text)
        
        optimized_sentences = []
        current_chunk = ""
        
        for sent in raw_sentences:
            if not sent.strip(): continue
            
            # Wenn der aktuelle Block + der neue Satz noch unter 150 Zeichen ist...
            if len(current_chunk) + len(sent) < 150:
                # ...und der aktuelle Block sehr kurz ist (< 20) ODER der neue Satz kurz ist,
                # dann kleben wir sie zusammen.
                if len(current_chunk) < 20 or len(current_chunk) > 0:
                    current_chunk += " " + sent
                else:
                    current_chunk = sent
            else:
                # Block ist voll -> Abspeichern und neuen Block beginnen
                optimized_sentences.append(current_chunk.strip())
                current_chunk = sent
        
        # Den letzten Rest nicht vergessen
        if current_chunk:
            optimized_sentences.append(current_chunk.strip())
            
        # Alles wieder zu einem perfekten String für die TTS zusammenfügen
        final_text = " ".join(optimized_sentences)
        return final_text

    def _process(self, res_path, ref_audio, callback):
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
            logging.debug("Mache Screenshot...")
            sc_raw = pyautogui.screenshot()
            sc = cv2.cvtColor(np.array(sc_raw), cv2.COLOR_RGB2BGR)

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
                logging.warning("Templates nicht gefunden.")
                return

            val1, loc1, w1, h1 = res_tl
            val2, loc2, w2, h2 = res_br

            if val1 < 0.7 or val2 < 0.7:
                logging.warning(f"Ecken ungenau ({val1:.2f}/{val2:.2f}).")

            x_start = loc1[0]
            y_start = loc1[1] + h1
            x_end = loc2[0] + w2
            y_end = loc2[1]

            if x_end <= x_start or y_end <= y_start:
                logging.error("FEHLER: Bereich ungültig.")
                return

            roi = sc_raw.crop((x_start, y_start, x_end, y_end))
            roi_np = cv2.cvtColor(np.array(roi), cv2.COLOR_RGB2BGR)
            
            # OCR
            logging.debug("Lese Text...")
            text_list = self.reader.readtext(roi_np, detail=0, paragraph=True)
            raw_full_text = " ".join(text_list)
            
            # --- HIER PASSIERT DIE MAGIE ---
            final_text = self.clean_and_optimize_text(raw_full_text)
            # -------------------------------
            
            logging.info(f"ERKANNT (Optimiert): '{final_text[:50]}...' ({len(final_text)} Zeichen)")

            if not final_text.strip():
                logging.warning("Kein Text erkannt (oder Filter hat alles entfernt).")
                return

            # TTS
            logging.info(f"Generiere Audio...")
            timestamp = int(time.time())
            out_path = f"output_speech_{timestamp}.wav"
            
            self.tts.tts_to_file(
                text=final_text, 
                speaker_wav=ref_audio, 
                language="de", 
                file_path=out_path,
                split_sentences=True # Coqui nutzt unsere optimierten Sätze
            )
            
            logging.info("Audio fertig!")
            callback(out_path)

        except Exception as e:
            logging.error(f"WORKER FEHLER: {e}")
            logging.error(traceback.format_exc())
