"""One-time, resumable downloads from the voice projects' official model hosts."""
from concurrent.futures import ThreadPoolExecutor
import fcntl
from pathlib import Path
import shutil
import tempfile
import time
import urllib.request
import zipfile

BASE=Path(__file__).resolve().parent/'assets'


def download(url,target):
    if target.exists() and target.stat().st_size>100:
        return
    partial=target.with_suffix(target.suffix+'.partial')
    for attempt in range(4):
        try:
            offset=partial.stat().st_size if partial.exists() else 0
            request=urllib.request.Request(url,headers={'Range':f'bytes={offset}-'} if offset else {})
            print(f'Downloading {target.name} (resume: {offset:,} bytes)',flush=True)
            with urllib.request.urlopen(request,timeout=30) as response:
                append=offset>0 and response.status==206
                if append and not response.headers.get('Content-Range','').startswith(f'bytes {offset}-'):
                    raise ValueError('Unexpected download range.')
                expected=response.headers.get('Content-Length')
                received=0
                with partial.open('ab' if append else 'wb') as file:
                    while chunk:=response.read(65536):
                        file.write(chunk)
                        received+=len(chunk)
                if expected is not None and received!=int(expected):
                    raise IOError('Incomplete download; saved partial file for resuming.')
            partial.replace(target)
            print('Ready: '+target.name,flush=True)
            return
        except Exception as error:
            print(f'{target.name}: {error}',flush=True)
            if attempt==3:
                raise
            time.sleep(2)


def main():
    BASE.mkdir(exist_ok=True)
    lock=(BASE/'.download.lock').open('w')
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('Another voice download is running. Let it finish before running setup again.')
    root='https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alan/medium/'
    downloads=[(root+name,BASE/name) for name in ['en_GB-alan-medium.onnx','en_GB-alan-medium.onnx.json','MODEL_CARD']]
    voice=BASE/'vosk-model-small-en-us-0.15'
    archive=BASE/'vosk-english.zip'
    ready=(voice/'.nexus-ready').exists()
    if not ready:
        downloads.append(('https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip',archive))
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda item:download(*item),downloads))
    if not ready and archive.exists():
        with zipfile.ZipFile(archive) as archive_file:
            for member in archive_file.infolist():
                target=(BASE/member.filename).resolve()
                if not target.is_relative_to(BASE.resolve()):
                    raise RuntimeError('Unsafe model archive path.')
            if archive_file.testzip() is not None:
                archive.unlink()
                raise RuntimeError('The model archive failed its integrity check. Run setup again to download a fresh copy.')
            with tempfile.TemporaryDirectory(prefix='.vosk-',dir=BASE) as temporary:
                archive_file.extractall(temporary)
                staged=Path(temporary)/voice.name
                if not (staged/'conf/model.conf').exists():
                    raise RuntimeError('The archive does not contain the expected speech model.')
                (staged/'.nexus-ready').write_text('ZIP CRC verified\n')
                if voice.exists():
                    shutil.rmtree(voice)
                staged.rename(voice)
        archive.unlink()
    print('Offline voice assets ready.',flush=True)


if __name__=='__main__':
    main()
