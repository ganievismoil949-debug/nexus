"""Offline voice workers. Heavy voice models leave memory when each worker exits."""
import argparse
import importlib.util
import json
import os
import re
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import wave

BASE=Path(__file__).resolve().parent


def normalize_transcript(text):
    text=re.sub(r'\byou tube\b','YouTube',text,flags=re.I)
    return re.sub(r'\bg mail\b','Gmail',text,flags=re.I)


class Voice:
    def __init__(self,data):
        self.data=Path(data)
        self.process=None
        self.lock=threading.Lock()

    def status(self):
        piper_ready=(BASE/'assets/en_GB-alan-medium.onnx').exists() and importlib.util.find_spec('piper') is not None
        return {'speech': 'Piper · Alan (English male)' if piper_ready else 'eSpeak · English male',
                'recognition':(BASE/'assets/vosk-model-small-en-us-0.15/conf/model.conf').exists() and importlib.util.find_spec('vosk') is not None,
                'microphone':bool(shutil.which('arecord'))}

    def stop(self):
        if self.process and self.process.poll() is None:
            try:
                os.killpg(self.process.pid,signal.SIGTERM)
            except ProcessLookupError:
                pass
        for name in ('microphone.wav','speech.wav'):
            (self.data/name).unlink(missing_ok=True)

    def listen(self):
        if not self.lock.acquire(blocking=False):
            raise ValueError('Voice is already busy. Stop it before starting again.')
        try:
            self.process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'listen','--data',str(self.data)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
            out,err=self.process.communicate(timeout=35)
            if self.process.returncode:
                raise ValueError('Listening stopped or failed. Check the microphone and offline voice setup.')
            return json.loads(out)
        finally:
            if self.process and self.process.poll() is None:
                self.stop()
                self.process.wait(timeout=5)
            self.process=None
            self.lock.release()

    def speak(self,text):
        if not self.lock.acquire(blocking=False):
            return
        try:
            self.process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'speak','--data',str(self.data)],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,start_new_session=True)
            self.process.communicate(text[:1800],timeout=120)
            if self.process.returncode:
                raise ValueError('Speech playback stopped or failed. Check the audio output.')
        finally:
            if self.process and self.process.poll() is None:
                self.stop()
                self.process.wait(timeout=5)
            self.process=None
            self.lock.release()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['listen','speak'])
    parser.add_argument('--data',required=True)
    args=parser.parse_args()
    data=Path(args.data)
    data.mkdir(parents=True,exist_ok=True)
    if args.mode=='listen':
        model_path=BASE/'assets/vosk-model-small-en-us-0.15'
        if not model_path.is_dir():
            raise RuntimeError('Offline recognition is not installed. Run setup.sh.')
        from vosk import Model, KaldiRecognizer, SetLogLevel
        SetLogLevel(-1)
        wav_path=data/'microphone.wav'
        try:
            subprocess.run(['arecord','-q','-f','S16_LE','-r','16000','-c','1','-d','8',str(wav_path)],check=True,timeout=12)
            model=Model(str(model_path))
            recognizer=KaldiRecognizer(model,16000)
            with wave.open(str(wav_path),'rb') as wav:
                while chunk:=wav.readframes(4000):
                    recognizer.AcceptWaveform(chunk)
            print(json.dumps({'text':normalize_transcript(json.loads(recognizer.FinalResult()).get('text',''))}))
        finally:
            wav_path.unlink(missing_ok=True)
    else:
        text=sys.stdin.read(1800)
        voice_path=BASE/'assets/en_GB-alan-medium.onnx'
        wav_path=data/'speech.wav'
        try:
            if voice_path.exists() and importlib.util.find_spec('piper') is not None:
                import onnxruntime
                onnxruntime.disable_telemetry_events()
                from piper import PiperVoice
                voice=PiperVoice.load(str(voice_path))
                with wave.open(str(wav_path),'wb') as wav:
                    voice.synthesize_wav(text,wav)
                subprocess.run(['aplay','-q',str(wav_path)],check=True,timeout=110)
            else:
                subprocess.run(['espeak-ng','-v','en-gb+m3','-s','155','-p','38','--stdin'],input=text,text=True,timeout=110,check=True)
        finally:
            wav_path.unlink(missing_ok=True)


if __name__=='__main__':
    main()
