"""A session-wide socket/DNS guard that records even caught violations."""

import inspect
import socket


class NetworkBlockedError(RuntimeError):
    pass


class NetworkGuard:
    def __init__(self):
        self.allowed = False
        self.events = []
        self.originals = []

    def _wrapper(self, original, operation, *, socket_method=False):
        def checked(*args, **kwargs):
            # AF_UNIX carries only local IPC, including asyncio's self-pipe.
            # Module helpers (DNS/create_connection) remain blocked offline.
            local = socket_method and args and args[0].family == socket.AF_UNIX
            if self.allowed or local:
                return original(*args, **kwargs)
            frames = inspect.stack()[1:]
            frame = next((f for f in frames if f.filename.rsplit("/", 1)[-1].startswith("test_")), None)
            frame = frame or next((f for f in frames if f.filename != __file__), None)
            location = f"{frame.filename}:{frame.lineno}" if frame else "<socket>:1"
            message = f"{location}: FR-M0-03: forbidden socket/DNS operation {operation}"
            self.events.append(message)
            raise NetworkBlockedError(message)

        return checked

    def install(self):
        for owner, names in (
            (
                socket,
                (
                    "create_connection",
                    "getaddrinfo",
                    "gethostbyname",
                    "gethostbyname_ex",
                    "gethostbyaddr",
                    "getnameinfo",
                    "getfqdn",
                ),
            ),
            (socket.socket, ("connect", "connect_ex", "sendto", "send", "sendall", "sendmsg", "listen")),
        ):
            for name in names:
                if hasattr(owner, name):
                    original = getattr(owner, name)
                    self.originals.append((owner, name, original))
                    setattr(owner, name, self._wrapper(original, name, socket_method=owner is socket.socket))

    def restore(self):
        for owner, name, original in reversed(self.originals):
            setattr(owner, name, original)
        self.originals.clear()
