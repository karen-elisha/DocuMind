"""Start server and wait for it to be ready."""
import subprocess, time, urllib.request, sys, os

workdir = os.path.dirname(os.path.abspath(__file__))

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
    cwd=workdir,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

# Wait for server to be ready
for i in range(30):
    time.sleep(1)
    try:
        r = urllib.request.urlopen("http://localhost:8000/", timeout=2)
        print("Server ready:", r.read().decode())
        break
    except Exception:
        if i == 29:
            print("Server failed to start")
            sys.exit(1)
else:
    print("Server not ready")
    sys.exit(1)
