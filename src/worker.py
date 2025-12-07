import threading
import os
import cv2
import numpy as np
import pyautogui
import easyocr
import logging
from TTS.api import TTS

class Worker:
    def __init__(self):
        self.reader = easyocr.Reader(['de'])
        self.tts = None
        
    def load_tts_model(self):
        if self.tts is None:
            logging.info("Lade KI-Modell (XTTS)...")
            try:
                self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cpu")
                logging.info("Bereit!")
            except Exception as e:
                logging.critical(f"TTS Fehler: {e}")

    def run_process(self, resources_path, reference_audio, on_audio_ready):
        # Wir übergeben jetzt den ganzen Ordner Pfad, da wir 2 Bilder laden müssen
        threading.Thread(target=self._process, args=(resources_path, reference_audio, on_audio_ready)).start()

    def _process(self, res_path, ref_audio, callback):
        if self.tts is None: return

        path_tl = os.path.join(res_path, "template_tl.png")
        path_br = os.path.join(res_path, "template_br.png")

        if not os.path.exists(path_tl) or not os.path.exists(path_br):
            logging.error("Fehler: Templates fehlen (TL oder BR). Bitte Setup ausführen!")
            return

        # 1. Screenshot machen
        sc = cv2.cvtColor(np.array(pyautogui.screenshot()), cv2.COLOR_RGB2BGR)

        # 2. Beide Ecken suchen
        def find_template(screenshot, templ_path):
            templ = cv2.imread(templ_path)
            h, w = templ.shape[:2]
            res = cv2.matchTemplate(screenshot, templ, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            return max_val, max_loc, w, h

        # Suche Top-Left
        val1, loc1, w1, h1 = find_template(sc, path_tl)
        if val1 < 0.8:
            logging.warning(f"Obere linke Ecke nicht gefunden ({val1:.2f})")
            return

        # Suche Bottom-Right
        val2, loc2, w2, h2 = find_template(sc, path_br)
        if val2 < 0.8:
            logging.warning(f"Untere rechte Ecke nicht gefunden ({val2:.2f})")
            return

        logging.info("Fenster erkannt! Berechne dynamische Größe...")

        # 3. Dynamischen Bereich berechnen
        # Start X = Links von TL
        # Start Y = Unterhalb von TL (um den Header nicht mitzulesen)
        # End X   = Rechts von BR
        # End Y   = Oberhalb von BR (um Footer/Buttons nicht mitzulesen)

        x_start = loc1[0]
        y_start = loc1[1] + h1 # Text fängt UNTER der oberen Ecke an
        
        x_end = loc2[0] + w2
        y_end = loc2[1]        # Text hört ÜBER der unteren Ecke auf

        # Sicherheitscheck: Ist BR wirklich rechts/unterhalb von TL?
        if x_end <= x_start or y_end <= y_start:
            logging.error("Fehler: Die Ecken sind vertauscht oder Fenster zu klein.")
            return

        # Ausschneiden
        roi = sc[y_start:y_end, x_start:x_end]
        
        # Optional: Debug speichern
        # cv2.imwrite("debug_dynamic_roi.png", roi)

        # 4. OCR und TTS (Wie gehabt)
        text_list = self.reader.readtext(roi, detail=0, paragraph=True)
        full_text = " ".join(text_list)
        
        if not full_text.strip():
            logging.info("Kein Text im Bereich erkannt.")
            return

        logging.info(f"Gelesen ({len(full_text)} Zeichen): {full_text[:40]}...")

        out_path = "output_speech.wav"
        self.tts.tts_to_file(text=full_text, speaker_wav=ref_audio, language="de", file_path=out_path)
        callback(out_path)
