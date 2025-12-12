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

# FIXES
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

from TTS.api import TTS
from TTS.utils.manage import ModelManager 

class NullWriter:
    def write(self, data): pass
    def flush(self): pass

class Worker:
    def __init__(self):
        print("DEBUG: Worker Init...")
        logging.info("Initialisiere EasyOCR...")
        # verbose=False, gpu=True
        self.reader = easyocr.Reader(['de'], gpu=torch.cuda.is_available(), verbose=False)
        self.tts = None
        
    def load_tts_model(self):
        if self.tts is None:
            logging.info("--- Lade TTS Modell ---")
            device = "cuda" if torch.cuda.is_available() else "cpu"
            try:
                # DEBUG: stderr offen lassen
                config_path = os.path.join(os.getcwd(), "resources", "models.json")
                if os.path.exists(config_path):
                    def patched_get_models_file_path(self): return config_path
                    TTS.get_models_file_path = patched_get_models_file_path

                def patched_ask_tos(self, output_path): return True 
                ModelManager.ask_tos = patched_ask_tos

                self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", progress_bar=False).to(device)
                logging.info(f"✅ TTS Modell geladen: {device}")
                
                # Optimierung
                if device == "cuda":
                    torch.backends.cudnn.benchmark = True
                    torch.backends.cuda.matmul.allow_tf32 = True 
                    torch.backends.cudnn.allow_tf32 = True
                    
            except Exception as e:
                logging.critical(f"TTS LOAD ERROR: {e}")
                traceback.print_exc()

    def run_process(self, resources_path, reference_audio, on_audio_ready, filter_pattern=None):
        print(f"DEBUG: run_process aufgerufen. Pattern={filter_pattern}")
        thread = threading.Thread(target=self._process, args=(resources_path, reference_audio, on_audio_ready, filter_pattern))
        thread.start()

    def clean_and_optimize_text(self, raw_text, filter_pattern):
        clean_base = raw_text.replace("\n", " ").strip()
        clean_base = re.sub(r'\s+', ' ', clean_base)
        # Quote Fix
        clean_base = re.sub(r"[‘´`’]", "'", clean_base)
        
        filtered_text = clean_base

        if filter_pattern:
            try:
                matches = re.findall(filter_pattern, clean_base, re.DOTALL)
                if matches:
                    filtered_text = " ".join(matches)
                    print(f"DEBUG: Filter Match! {len(matches)} Teile.")
                else:
                    print("DEBUG: Filter leer. Fallback.")
                    filtered_text = clean_base 
            except:
                filtered_text = clean_base

        # Satz-Splitting
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
        print("DEBUG: Thread running...")
        try:
            logging.info("--- Starte Scan-Prozess ---")
            
            if self.tts is None:
                logging.error("ABBRUCH: TTS nicht geladen.")
                return

            print("DEBUG: Screenshot...")
            sc_raw = pyautogui.screenshot()
            sc = cv2.cvtColor(np.array(sc_raw), cv2.COLOR_RGB2BGR)
            cv2.imwrite("debug_1_screenshot.png", sc)

            path_tl = os.path.join(res_path, "template_tl.png")
            path_br = os.path.join(res_path, "template_br.png")

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
                logging.warning("Templates nicht gefunden (F8 nötig?).")
                return

            val1, loc1, w1, h1 = res_tl
            val2, loc2, w2, h2 = res_br
            print(f"DEBUG: Matches: {val1:.2f} / {val2:.2f}")

            x_start = loc1[0]
            y_start = loc1[1] + h1
            x_end = loc2[0] + w2
            y_end = loc2[1]

            if x_end <= x_start or y_end <= y_start:
                logging.error("Bereich ungültig.")
                return

            roi = sc_raw.crop((x_start, y_start, x_end, y_end))
            roi_np = cv2.cvtColor(np.array(roi), cv2.COLOR_RGB2BGR)
            cv2.imwrite("debug_2_roi.png", roi_np)
            
            # FAST OCR
            print("DEBUG: Starte OCR...")
            gray_roi = cv2.cvtColor(roi_np, cv2.COLOR_BGR2GRAY)
            start_ocr = time.time()
            text_list = self.reader.readtext(gray_roi, detail=0, paragraph=False, workers=0, reformat=False)
            print(f"DEBUG: OCR fertig in {time.time() - start_ocr:.2f}s")
            
            raw_full_text = " ".join(text_list)
            
            # Debug Text Save
            try:
                with open("debug_ocr_text.txt", "w", encoding="utf-8") as f:
                    f.write(f"RAW: {raw_full_text}\nFILTER: {filter_pattern}\n")
            except: pass

            final_text = self.clean_and_optimize_text(raw_full_text, filter_pattern)
            logging.info(f"ERKANNT: '{final_text[:40]}...'")

            if not final_text.strip():
                logging.warning("Kein Text.")
                return

            logging.info(f"Starte Streaming...")
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
                print("DEBUG: Stream an Player gesendet.")
            except Exception as e:
                logging.error(f"TTS Error: {e}")

        except Exception as e:
            print(f"CRASH: {e}")
            logging.critical(f"WORKER CRASH: {e}")
            logging.critical(traceback.format_exc())
            try:
                with open("CRASH_LOG.txt", "w") as f:
                    f.write(traceback.format_exc())
            except: pass
