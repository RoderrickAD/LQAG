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
        self.model_name = "tts_models/multilingual/multi-dataset/xtts_v2"

    def load_tts_model(self):
        if self.tts is None:
            logging.info("Lade KI-Sprachmodell (XTTS)... Bitte warten.")
            try:
                # Wichtig: gpu=False für Kompatibilität, falls User keine NVIDIA hat
                self.tts = TTS(self.model_name).to("cpu") 
                logging.info("KI-Modell bereit!")
            except Exception as e:
                logging.critical(f"Kritischer Modell-Fehler: {e}")

    def run_process(self, template_path, reference_audio, on_audio_ready):
        threading.Thread(target=self._process, args=(template_path, reference_audio, on_audio_ready)).start()

    def _process(self, template_path, ref_audio, callback):
        if self.tts is None:
            logging.warning("Modell lädt noch. Bitte kurz warten.")
            return

        # 1. Screenshot & Suche
        try:
            sc = cv2.cvtColor(np.array(pyautogui.screenshot()), cv2.COLOR_RGB2BGR)
            templ = cv2.imread(template_path)
            res = cv2.matchTemplate(sc, templ, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val < 0.8:
                logging.warning(f"Template nicht gefunden ({max_val:.2f}).")
                return
            
            # Bereich unter dem Template scannen (Anpassen je nach Bedarf)
            h, w = templ.shape[:2]
            roi = sc[max_loc[1]+h : max_loc[1]+h+400, max_loc[0] : max_loc[0]+500]
            
            # 2. Text lesen
            txt = " ".join(self.reader.readtext(roi, detail=0, paragraph=True))
            if not txt.strip(): 
                logging.info("Kein Text im Bereich erkannt.")
                return
            
            logging.info(f"Gelesen: {txt[:40]}...")

            # 3. Sprechen
            out = "lqag_output.wav"
            self.tts.tts_to_file(text=txt, speaker_wav=ref_audio, language="de", file_path=out)
            callback(out)
            
        except Exception as e:
            logging.error(f"Prozess Fehler: {e}")
