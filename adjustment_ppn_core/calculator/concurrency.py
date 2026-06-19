import threading
import queue
import time

class DbWriterQueue:
    """
    A thread-safe queue for executing SQL write queries (INSERT, UPDATE, DELETE).
    This ensures that only one thread (the DB Writer Thread) communicates with 
    the database for writes, preventing SQLite 'database is locked' errors and 
    PyMySQL 'commands out of sync' errors.
    """
    def __init__(self, target_conn):
        self.target_conn = target_conn
        self.q = queue.Queue()
        self.running = True
        self.worker_thread = threading.Thread(target=self._writer_loop, daemon=True)
        self.worker_thread.start()

    def _writer_loop(self):
        cursor = self.target_conn.cursor()
        while self.running or not self.q.empty():
            try:
                task = self.q.get(timeout=0.1)
                if task is None:
                    continue
                sql, params = task
                cursor.execute(sql, params)
                self.q.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"DbWriterQueue Error: {e}")

    def push(self, sql, params):
        self.q.put((sql, params))

    def stop_and_wait(self):
        self.running = False
        self.worker_thread.join()
        try:
            self.target_conn.commit()
        except:
            pass


class LogBatcher:
    """
    Batches logs to avoid overwhelming the GUI thread with signals.
    """
    def __init__(self, log_callback, batch_size=20):
        self.log_callback = log_callback
        self.batch_size = batch_size
        self.logs = []
        self.lock = threading.Lock()

    def add_log(self, msg):
        if not self.log_callback or not callable(self.log_callback):
            return
        with self.lock:
            self.logs.append(msg)
            if len(self.logs) >= self.batch_size:
                self.flush_unsafe()

    def flush_unsafe(self):
        if self.logs:
            combined = "\n".join(self.logs)
            self.log_callback(combined)
            self.logs.clear()

    def flush(self):
        if not self.log_callback or not callable(self.log_callback):
            return
        with self.lock:
            self.flush_unsafe()
