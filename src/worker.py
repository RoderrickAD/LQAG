import threading
import os
import cv2
import numpy as np
import pyautogui
import easyocr
import logging
import traceback
import sys  # WICHTIG
from TTS.api import TTS
from TTS.utils.manage import ModelManager 

# --- HILFSKLASSE FÜR PYINSTALLER ---
# Da wir keine Konsole haben, leiten wir Text-Ausgaben ins Leere um,
# damit tqdm (Ladebalken) nicht abstürzt.
class NullWriter:
    def write(self, data): pass
    def flush(self): pass

class Worker:
    def __init__(self):
        logging.info("Initialisiere EasyOCR...")
        self.reader = easyocr.Reader(['de'])
        self.tts = None
        
    def load_tts_model(self):
        if self.tts is None:
            logging.info("--- Lade TTS Modell (XTTS v2) ---")
            logging.info("Dies kann beim allerersten Start lange dauern (Download ca. 1.5GB).")
            logging.info("Bitte Geduld haben, auch wenn keine Balken zu sehen sind!")
            
            try:
                # --- FIX 1: SYSTEM STREAMS UMLEITEN ---
                # Wenn sys.stdout/stderr None sind (kein Konsolenfenster),
                # ersetzen wir sie durch unseren NullWriter.
                if sys.stdout is None: sys.stdout = NullWriter()
                if sys.stderr is None: sys.stderr = NullWriter()

                # --- MONKEY PATCH 1: CONFIG PFAD ---
                config_path = os.path.join(os.getcwd(), "resources", "models.json")
                if os.path.exists(config_path):
                    logging.info(f"PATCH: Nutze Config-Datei aus: {config_path}")
                    def patched_get_models_file_path(self):
                        return config_path
                    TTS.get_models_file_path = patched_get_models_file_path
                else:
                    logging.warning(f"PATCH FEHLGESCHLAGEN: {config_path} nicht gefunden!")

                # --- MONKEY PATCH 2: LIZENZ AUTO-AKZEPTIEREN ---
                logging.info("PATCH: Akzeptiere automatisch Coqui TTS Lizenz.")
                def patched_ask_tos(self, output_path):
                    return True 
                ModelManager.ask_tos = patched_ask_tos

                # --- STARTEN MIT PROGRESS_BAR=FALSE ---
                # WICHTIG: progress_bar=False verhindert, dass tqdm versucht zu zeichnen
                self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", progress_bar=False).to("cpu")
                
                logging.info("✅ TTS Modell erfolgreich geladen und bereit!")
                
            except Exception as e:
                logging.critical(f"❌ FEHLER beim Laden des Modells: {e}")
                logging.debug(traceback.format_exc())

    def run_process(self, resources_path, reference_audio, on_audio_ready):
        thread = threading.Thread(target=self._process, args=(resources_path, reference_audio, on_audio_ready))
        thread.start()

    def _process(self, res_path, ref_audio, callback):
        logging.info("--- Starte Scan-Prozess ---")
        
        if self.tts is None:
            logging.error("ABBRUCH: TTS Modell ist noch nicht geladen (Download läuft noch?).")
            return

        path_tl = os.path.join(res_path, "template_tl.png")
        path_br = os.path.join(res_path, "template_br.png")

        try:
            logging.debug("Mache Screenshot...")
            sc_raw = pyautogui.screenshot()
            sc = cv2.cvtColor(np.array(sc_raw), cv2.COLOR_RGB2BGR)
            cv2.imwrite("debug_1_screenshot.png", sc)

            def find_template(img, templ_p, name):
                if not os.path.exists(templ_p):
                    logging.error(f"Template fehlt: {templ_p}")
                    return None
                templ = cv2.imread(templ_p)
                if templ is None: return None
                h, w = templ.shape[:2]
                res = cv2.matchTemplate(img, templ, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                cv2.rectangle(img, max_loc, (max_loc[0] + w, max_loc[1] + h), (0, 0, 255), 2)
                return max_val, max_loc, w, h

            res_tl = find_template(sc, path_tl, "Top-Left")
            res_br = find_template(sc, path_br, "Bottom-Right")
            cv2.imwrite("debug_3_matches.png", sc)

            if not res_tl or not res_br:
                logging.warning("Konnte Templates nicht finden (siehe debug_3_matches.png)")
                return

            val1, loc1, w1, h1 = res_tl
            val2, loc2, w2, h2 = res_br

            if val1 < 0.7 or val2 < 0.7:
                logging.warning(f"Ecken zu ungenau ({val1:.2f} / {val2:.2f}).")
                return

            x_start = loc1[0]
            y_start = loc1[1] + h1
            x_end = loc2[0] + w2
            y_end = loc2[1]

            if x_end <= x_start or y_end <= y_start:
                logging.error("FEHLER: Bereich ungültig (Ende vor Start).")
                return

            roi = sc_raw.crop((x_start, y_start, x_end, y_end))
            roi_np = cv2.cvtColor(np.array(roi), cv2.COLOR_RGB2BGR)
            cv2.imwrite("debug_2_roi.png", roi_np)
            
            # OCR
            text_list = self.reader.readtext(roi_np, detail=0, paragraph=True)
            full_text = " ".join(text_list)
            
            logging.info(f"ERKANNT: '{full_text}'")

            if not full_text.strip():
                logging.warning("Kein Text erkannt.")
                return

            # TTS
            logging.info(f"Generiere Audio mit: {os.path.basename(ref_audio)}")
            out_path = "output_speech.wav"
            self.tts.tts_to_file(text=full_text, speaker_wav=ref_audio, language="de", file_path=out_path)
            
            logging.info("Audio fertig!")
            callback(out_path)

        except Exception as e:
            logging.error(f"WORKER FEHLER: {e}")
            logging.error(traceback.format_exc())
