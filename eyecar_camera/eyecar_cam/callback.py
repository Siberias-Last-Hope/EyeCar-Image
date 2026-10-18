import functools
import threading


def long_callback(func):
    lock = threading.Lock()
    state = {'pending': None, 'running': False}

    def worker(args, kwargs):
        while True:
            try:
                func(*args, **kwargs)
            finally:
                with lock:
                    nxt = state['pending']
                    state['pending'] = None
                    if nxt is None:
                        state['running'] = False
                        return
            args, kwargs = nxt

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with lock:
            if state['running']:
                state['pending'] = (args, kwargs)
                return
            state['running'] = True
        threading.Thread(target=worker, args=(args, kwargs), daemon=True).start()

    return wrapper
