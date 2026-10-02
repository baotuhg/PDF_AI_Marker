from pathlib import Path
import sys, os, subprocess, threading, queue, json, tempfile, shutil, time

ROOT=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent

class Cancelled(Exception):
    pass

def convert(source,destination,mode='auto',password='',chunk_size=3000,
            cancel=None,progress=lambda *args:None,pages=''):
    cancel=cancel or threading.Event()
    if cancel.is_set(): raise Cancelled()
    # `engine/python.exe` is the copied standalone interpreter.  Keep the
    # venv launcher as a fallback for older packages created before the
    # portable runtime was assembled.
    runtime=ROOT/'engine/python.exe'
    if not runtime.exists():
        runtime=ROOT/'engine/Scripts/python.exe'
    if not runtime.exists():
        raise RuntimeError('Thiếu bộ chạy Marker. Cần giữ thư mục engine cạnh ứng dụng.')
    sessions=ROOT/'sessions'
    sessions.mkdir(exist_ok=True)
    session=Path(tempfile.mkdtemp(prefix='job_',dir=sessions))
    logpath=session/'marker.log'
    env=os.environ.copy()
    for key in ['PYTHONPATH','PYTHONHOME','TCL_LIBRARY','TK_LIBRARY']:
        env.pop(key,None)
    env['PYTHONUTF8']='1'
    env['PYTHONIOENCODING']='utf-8'
    site_packages=ROOT/'engine/Lib/site-packages'
    env['PYTHONPATH']=(str(ROOT)+os.pathsep+str(site_packages)) if site_packages.exists() else str(ROOT)
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    # A frozen PyInstaller process changes the DLL search directory. Restore
    # Windows defaults for the external Marker interpreter, then restore GUI.
    if os.name=='nt' and getattr(sys,'frozen',False):
        import ctypes
        ctypes.windll.kernel32.SetDllDirectoryW(None)
    try:
        process=subprocess.Popen([str(runtime),'-u',str(ROOT/'marker_worker.py')],
            cwd=str(ROOT),env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',creationflags=flags)
    finally:
        if os.name=='nt' and getattr(sys,'frozen',False):
            ctypes.windll.kernel32.SetDllDirectoryW(sys._MEIPASS)
    request={'source':str(Path(source).resolve()),'destination':str(Path(destination).resolve()),
             'mode':mode,'password':password,'session':str(session),'pages':pages,
             'chunk_size':chunk_size}
    process.stdin.write(json.dumps(request,ensure_ascii=False)+'\n')
    process.stdin.close()
    messages=queue.Queue()
    def reader():
        with logpath.open('w',encoding='utf-8') as log:
            for line in process.stdout:
                log.write(line)
                log.flush()
                if line.startswith('PDF_AI_EVENT '):
                    try: messages.put(json.loads(line[len('PDF_AI_EVENT '):]))
                    except json.JSONDecodeError: pass
    thread=threading.Thread(target=reader,daemon=True)
    thread.start()
    ready=None
    error=None
    started=time.monotonic()
    last_tick=0
    current='Đang khởi động Marker…'
    current_pct=0
    try:
        while process.poll() is None or thread.is_alive() or not messages.empty():
            if cancel.is_set():
                subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],
                    capture_output=True,creationflags=flags,timeout=15)
                process.wait(timeout=15)
                thread.join(timeout=5)
                raise Cancelled()
            try:
                event=messages.get(timeout=.2)
                if event['type']=='progress':
                    current=event['message']
                    if 'percent' in event:
                        current_pct=int(event['percent'])
                    progress(current_pct,100,current)
                elif event['type']=='result_ready': ready=event
                elif event['type']=='error': error=event['message']
            except queue.Empty:
                pass
            elapsed=int(time.monotonic()-started)
            if elapsed!=last_tick:
                display_msg=current if ('còn lại' in current or 's)' in current) else f'{current} ({elapsed}s)'
                progress(current_pct,100,display_msg)
                last_tick=elapsed
        if cancel.is_set():
            raise Cancelled()
        if process.returncode or error or not ready:
            raise RuntimeError((error or f'Marker kết thúc với mã {process.returncode}')+f'\nNhật ký: {logpath}')
        staged=Path(ready['path']).resolve()
        if staged != (session/'result').resolve():
            raise RuntimeError('Đường dẫn kết quả không hợp lệ.')
        dest=Path(destination).resolve()
        dest.mkdir(parents=True,exist_ok=True)
        stem=Path(source).stem[:80]+'_Marker'
        # Copy to a hidden staging directory on the destination filesystem;
        # rename atomically without overwriting any previous export.
        export_temp=Path(tempfile.mkdtemp(prefix='.pdf_ai_',dir=dest))
        try:
            shutil.copytree(staged,export_temp,dirs_exist_ok=True)
            payload=json.loads((export_temp/'du_lieu.json').read_text(encoding='utf-8'))
            markdown=(export_temp/'noi_dung.md').read_text(encoding='utf-8')
            if cancel.is_set(): raise Cancelled()
            for i in range(100000):
                target=dest/(stem if i==0 else f'{stem}_{i}')
                try:
                    export_temp.rename(target)
                    break
                except FileExistsError: continue
            else: raise RuntimeError('Không tạo được thư mục kết quả mới.')
        finally:
            if export_temp.exists(): shutil.rmtree(export_temp)
        progress(100,100,'Hoàn tất • PDF AI v3')
        return target,payload,markdown
    finally:
        process.stdout.close()
        # Session folder is scoped by mkdtemp; remove decrypted input/results,
        # retain only logs for diagnosing a failed conversion.
        for item in session.iterdir():
            if item.name.endswith('.log'): continue
            if item.is_dir(): shutil.rmtree(item)
            else: item.unlink(missing_ok=True)
