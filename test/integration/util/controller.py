import shutil
import json
import time
import socket
import subprocess
import os
import signal

class TCPSocket:
    def __init__(self, port=8787):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect(("127.0.0.1", port))
        # without a timeout recv() blocks forever if the simulator never answers
        self.s.settimeout(0.5)
        # bytes read by _wait_line beyond the line it returned
        self._buf = b""

    def readline(self, eol=b"\r\n", timeout=3):
        res, self._buf = self._buf, b""
        t0 = time.time()
        while not (eol in res):
            # timeout
            if time.time()-t0 > timeout:
                break
            try:
                raw = self.s.recv(1000)
                res += raw
            except socket.timeout:
                continue
            except Exception as e:
                print(e)
                time.sleep(0.01)
        return res

    def send(self, cmd):
        cmd = json.dumps([cmd])[1:-1]
        self.s.send(str(cmd).encode()+b"\r\n")
        res = self.readline()

    def query(self, data):
        self.s.send(data)
        return self.readline(eol=b"ACK\r\n")

    def receive(self, timeout=60):
        # Before the socket timeout existed, recv() blocked until data came,
        # so slow host commands (e.g. PSBT signing) never timed out here.
        # Keep a long default so they still complete.
        return self.readline(timeout=timeout)

    def drain(self, timeout=0.3):
        """Discard anything already sent to us (e.g. old screen names)."""
        self.readline(eol=b"\0never\0", timeout=timeout)
        self._buf = b""

    def _wait_line(self, match, timeout):
        t0 = time.time()
        while time.time() - t0 < timeout:
            while b"\r\n" in self._buf:
                line, self._buf = self._buf.split(b"\r\n", 1)
                if match(line):
                    return line
            try:
                self._buf += self.s.recv(1000)
            except socket.timeout:
                pass
        return None

    def command(self, name, timeout=3):
        """Simulator widget command on the GUI socket (see
        TCPGUI.widget_command), e.g. "press_confirm" or "scroll_end".
        Returns the reply line, or None on timeout."""
        self.s.send(name.encode() + b"\r\n")
        return self._wait_line(
            lambda l: l.startswith(b"state ") or l.startswith(b"error:"), timeout)

    def wait_screen(self, name, timeout=5):
        """Wait until the GUI reports that screen `name` was opened."""
        return self._wait_line(lambda l: l == name.encode(), timeout)

class SimController:
    def __init__(self):
        self.started = False
        self.gui = None
        self.usb = None
        try:
            shutil.rmtree("./fs/")
        except:
            pass

    def start(self):
        print("Starting up...")
        self.proc = subprocess.Popen("../../bin/micropython_unix simulator.py",
                                stdout=subprocess.PIPE,
                                shell=True, preexec_fn=os.setsid)
        # GUI commands sent before the first screen exists are dropped, so
        # give slow machines (e.g. macOS with SDL) time to bring it up.
        time.sleep(float(os.environ.get("SIM_STARTUP_DELAY", "5")))

    def load(self):
        # command socket
        self.gui = TCPSocket(8787)
        # select PIN
        self.gui.send("")
        # confirm PIN
        self.gui.send("")
        # enter recovery phrase
        self.gui.send(1)
        self.gui.send("abandon "*11+"about")
        # now we can open usb communication
        time.sleep(1)
        self.usb = TCPSocket(8789)

    def shutdown(self):
        print("Shutting down...")
        if self.gui is not None:
            try:
                self.gui.s.send(b"quit\r\n")
                time.sleep(0.3)
            except:
                pass
        try:
            # The simulator may exit after handling the quit command above.
            os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
        time.sleep(1)

    def query(self, data, commands=[]):
        if isinstance(data, str):
            data = data.encode()
        if data[-1:] not in b"\r\n":
            data = data + b"\r\n"
        res = self.usb.query(data)
        assert res == b"ACK\r\n"
        # if we need to confirm anything
        for command in commands:
            sim.gui.send(command)
            time.sleep(0.3)
        res = sim.usb.receive()
        return res.strip()

class BitcoinCore:
    datadir = "./testdir/"
    def __init__(self):
        pass

    def start(self):
        print("starting Bitcon Core in regtest mode with datadir %s" % self.datadir)
        try:
            shutil.rmtree(self.datadir)
        except:
            pass
        try:
            os.mkdir(self.datadir)
        except:
            pass
        self.proc = subprocess.Popen("bitcoind -datadir=%s -regtest -fallbackfee=0.0002 -rpcuser=bitcoin -rpcpassword=secret -rpcport=18778 -port=18779" % self.datadir,
                                stdout=subprocess.PIPE,
                                shell=True, preexec_fn=os.setsid)
        time.sleep(1)

    def shutdown(self):
        print("shutting down Bitcon Core")
        os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)  # Send the signal to all the process groups
        time.sleep(3)
        try:
            shutil.rmtree(self.datadir)
        except:
            pass

sim = SimController()
core = BitcoinCore()
