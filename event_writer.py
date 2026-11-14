"""Local event file writes leave the time-critical controller thread."""
import os,queue,threading

class QueuedWriter:
    def __init__(self,path):
        self.queue=queue.Queue();self.error=None;self.closed=False
        self.file=open(path,'a',encoding='utf-8',buffering=1)
        self.thread=threading.Thread(target=self._run,daemon=True);self.thread.start()
    def write(self,text):
        if self.closed:raise ValueError('Closed event writer')
        self.queue.put_nowait(text);return len(text)
    def _run(self):
        while True:
            text=self.queue.get()
            try:
                if text is None:return
                self.file.write(text)
            except OSError as error:self.error=type(error).__name__
            finally:self.queue.task_done()
    def flush(self):self.queue.join();self.file.flush()
    def close(self):
        if self.closed:return
        self.closed=True;self.queue.put(None);self.thread.join(5)
        if self.thread.is_alive():raise RuntimeError('Event writer did not drain')
        self.file.close()

def open_events(path):
    return QueuedWriter(path) if os.environ.get('HONGIK_ASYNC_RECORDS')=='1' else open(path,'a',encoding='utf-8',buffering=1)
