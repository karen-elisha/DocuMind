"""
Runner: starts uvicorn in a thread, runs retrieval quality tests via HTTP.
Usage: python run_test_runner.py
"""
import sys, os, time, threading, urllib.request, urllib.error
from uvicorn.config import Config
from uvicorn.server import Server

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from main import app

server_ref = None

def start_server():
    global server_ref
    config = Config(app=app, host="127.0.0.1", port=8000, log_level="warning")
    server_ref = Server(config=config)
    server_ref.run()

t = threading.Thread(target=start_server, daemon=True)
t.start()

for i in range(60):
    try:
        r = urllib.request.urlopen("http://127.0.0.1:8000/", timeout=3)
        if r.status == 200:
            print(f"Server ready after {i}s")
            break
    except Exception:
        pass
    time.sleep(1)
else:
    print("Server failed to start")
    sys.exit(1)

from test_retrieval_quality import run_tests
success = run_tests()
sys.exit(0 if success else 1)
