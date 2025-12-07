import threading
import os
import cv2
import numpy as np
import pyautogui
import easyocr
import logging
import traceback
from TTS.api import TTS

class Worker:
    def __init__(self):
        logging.info("Initialisiere EasyOCR...")
        self.reader = easyocr.Reader(['de'])
        self.tts = None
        
    def load_tts_model(self):
        if self.tts is None:
            logging.info("--- Lade TTS Modell (XTTS v2) ---")
            logging.info("Dies kann beim allerersten Start lange dauern (Download).")
            try:
                # gpu=False erzwingen für Kompatibilität
                self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cpu")
                logging.info("✅ TTS Modell erfolgreich geladen und bereit!")
            except Exception as e:
                logging.critical(f"❌ FEHLER beim Laden des Modells: {e}")
                logging.debug(traceback.format_exc())

    def run_process(self, resources_path, reference_audio, on_audio_ready):
        # Startet den Thread
        thread = threading.Thread(target=self._process, args=(resources_path, reference_audio, on_audio_ready))
        thread.start()

    def _process(self, res_path, ref_audio, callback):
        logging.info("--- Starte Scan-Prozess ---")
        
        if self.tts is None:
            logging.error("ABBRUCH: TTS Modell ist noch nicht geladen.")
            return

        path_tl = os.path.join(res_path, "template_tl.png")
        path_br = os.path.join(res_path, "template_br.png")

        try:
            # 1. SCREENSHOT
            logging.debug("Mache Screenshot...")
            sc_raw = pyautogui.screenshot()
            sc = cv2.cvtColor(np.array(sc_raw), cv2.COLOR_RGB2BGR)
            # Debug Bild speichern
            cv2.imwrite("debug_1_screenshot.png", sc)
            logging.debug("Screenshot gespeichert: debug_1_screenshot.png")

            # 2. TEMPLATE MATCHING
            logging.debug(f"Suche Templates in: {res_path}")
            
            def find_template(img, templ_p, name):
                if not os.path.exists(templ_p):
                    logging.error(f"Template fehlt: {templ_p}")
                    return None
                templ = cv2.imread(templ_p)
                if templ is None:
                    logging.error(f"Konnte Template nicht lesen: {templ_p}")
                    return None
                    
                h, w = templ.shape[:2]
                res = cv2.matchTemplate(img, templ, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                
                logging.debug(f"Template '{name}' gefunden bei {max_loc} mit Confidence: {max_val:.2f}")
                
                # Zeichne Rechteck in das Debug-Bild
                cv2.rectangle(img, max_loc, (max_loc[0] + w, max_loc[1] + h), (0, 0, 255), 2)
                return max_val, max_loc, w, h

            # Suche Top-Left
            res_tl = find_template(sc, path_tl, "Top-Left")
            # Suche Bottom-Right
            res_br = find_template(sc, path_br, "Bottom-Right")

            # Speichere das Bild mit den Markierungen
            cv2.imwrite("debug_3_matches.png", sc)

            if not res_tl or not res_br:
                logging.warning("Konnte Templates nicht finden (siehe debug_3_matches.png)")
                return

            val1, loc1, w1, h1 = res_tl
            val2, loc2, w2, h2 = res_br

            # Schwellwert prüfen (0.8 = 80% Übereinstimmung)
            if val1 < 0.8:
                logging.warning(f"Obere Ecke zu ungenau ({val1:.2f}). Setup wiederholen?")
                return
            if val2 < 0.8:
                logging.warning(f"Untere Ecke zu ungenau ({val2:.2f}). Setup wiederholen?")
                return

            # 3. BEREICH BERECHNEN
            x_start = loc1[0]
            y_start = loc1[1] + h1 # Unterhalb des Icons
            x_end = loc2[0] + w2
            y_end = loc2[1]        # Oberhalb des unteren Icons

            logging.debug(f"Berechneter Bereich: X={x_start}-{x_end}, Y={y_start}-{y_end}")

            if x_end <= x_start or y_end <= y_start:
                logging.error("FEHLER: Negative Größe. Ist die untere Ecke wirklich rechts unterhalb der oberen?")
                return

            # Ausschneiden
            roi = sc_raw.crop((x_start, y_start, x_end, y_end))
            roi_np = cv2.cvtColor(np.array(roi), cv2.COLOR_RGB2BGR)
            
            # WICHTIG: Das sieht der OCR!
            cv2.imwrite("debug_2_roi.png", roi_np)
            logging.info("Ausschnitt gespeichert: debug_2_roi.png")

            # 4. OCR (Texterkennung)
            logging.debug("Starte EasyOCR auf dem Ausschnitt...")
            text_list = self.reader.readtext(roi_np, detail=0, paragraph=True)
            full_text = " ".join(text_list)
            
            logging.info(f"--- ERKANNT (OCR) ---")
            logging.info(f"'{full_text}'")
            logging.info(f"---------------------")

            if not full_text.strip():
                logging.warning("Kein Text erkannt (Bild leer?).")
                return

            # 5. TTS (Audio)
            logging.info(f"Starte TTS Generierung mit Stimme: {os.path.basename(ref_audio)}")
            out_path = "output_speech.wav"
            
            self.tts.tts_to_file(text=full_text, speaker_wav=ref_audio, language="de", file_path=out_path)
            
            logging.info(f"Audio generiert: {out_path}")
            callback(out_path)

        except Exception as e:
            logging.error(f"KRITISCHER FEHLER IM WORKER: {e}")
            logging.error(traceback.format_exc()) # Speichert den genauen Fehlergrund im Log
