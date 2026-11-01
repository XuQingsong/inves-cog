"""Bounded local-communication probes shared by the v3 test and evidence run."""

LOCAL_COMMUNICATION_PROBES = {
    "socketpair": """import socket
def test_probe():
    left, right = socket.socketpair()
    with left, right:
        assert left.family == socket.AF_UNIX
        left.sendall(b'local')
        assert right.recv(5) == b'local'
        right.send(b'ok')
        assert left.recv(2) == b'ok'
    print('socketpair: local send/receive passed', flush=True)
""",
    "asyncio": """import asyncio, threading
def test_probe():
    loop = asyncio.new_event_loop()
    ready, done = threading.Event(), threading.Event()
    def serve():
        asyncio.set_event_loop(loop)
        loop.call_soon(ready.set)
        loop.run_forever()
    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    try:
        assert ready.wait(5)
        loop.call_soon_threadsafe(done.set)
        assert done.wait(5)
        print('asyncio: call_soon_threadsafe passed', flush=True)
    finally:
        loop.call_soon_threadsafe(loop.stop)
        worker.join(5)
        assert not worker.is_alive()
        loop.close()
""",
    "testclient": """from fastapi import FastAPI
from fastapi.testclient import TestClient
def test_probe():
    app = FastAPI()
    @app.get('/probe')
    async def route():
        return {'ok': True}
    print('TestClient: request started', flush=True)
    with TestClient(app) as client:
        response = client.get('/probe')
        assert response.status_code == 200
        assert response.json() == {'ok': True}
        print('TestClient: status=200 body={"ok": true}', flush=True)
""",
}
