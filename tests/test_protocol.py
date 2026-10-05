import json
import os
import subprocess
import sys
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ProtocolTest(unittest.TestCase):
    def test_init_handle_draw_close(self):
        p = subprocess.Popen([sys.executable, "run.py"], cwd=ROOT, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        try:
            def send(o):
                p.stdin.write(json.dumps(o) + "\n")
                p.stdin.flush()

            def until(id_):
                deadline = time.time() + 5
                seen = []
                while time.time() < deadline:
                    line = p.stdout.readline()
                    if not line:
                        break
                    msg = json.loads(line)
                    seen.append(msg)
                    if msg.get("id") == id_ and "method" not in msg:
                        return msg, seen
                self.fail("no reply for %s" % id_)

            send({"id": 1, "method": "init", "params": {}})
            until(1)
            send({"method": "handle", "params": {"kind": "pad", "data": {"col": 0, "row": 7, "pressed": True}}})
            send({"method": "handle", "params": {"kind": "button", "data": {"name": "Layout", "pressed": True}}})
            send({"id": 2, "method": "draw", "params": {}})
            msg, seen = until(2)
            self.assertEqual(msg["result"]["failed"], 0)
            self.assertTrue(any(m.get("method") == "set_pad" for m in seen))
            self.assertTrue(any(m.get("method") == "set_button" and m["params"]["cc"] == 31 for m in seen))
            send({"id": 3, "method": "close", "params": {}})
            until(3)
        finally:
            p.kill()
            p.wait()
            for f in (p.stdin, p.stdout, p.stderr):
                f.close()


if __name__ == "__main__":
    unittest.main()
