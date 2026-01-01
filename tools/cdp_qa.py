"""CDP QA harness: drive headless Chrome in REAL time, evaluate page
state, screenshot. Usage:
  python cdp_qa.py <url> <wait_s> <out.png> [<js-expr>]
"""
import base64
import json
import subprocess
import sys
import time
import urllib.request

import websocket

url, wait_s, out = sys.argv[1], float(sys.argv[2]), sys.argv[3]
expr = sys.argv[4] if len(sys.argv) > 4 else "1+1"
PORT = 9333

chrome = subprocess.Popen(
    ["google-chrome", "--headless=new", "--disable-gpu", "--no-sandbox",
     f"--remote-debugging-port={PORT}", "--remote-allow-origins=*", "--window-size=1280,800",
     "--hide-scrollbars", "--mute-audio", "about:blank"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try:
            tabs = json.load(urllib.request.urlopen(
                f"http://127.0.0.1:{PORT}/json"))
            break
        except Exception:
            time.sleep(0.2)
    tab = next(t for t in tabs if t.get("type") == "page")
    ws = websocket.create_connection(tab["webSocketDebuggerUrl"],
                                     max_size=50_000_000, timeout=40)
    mid = [0]

    def cmd(method, **params):
        mid[0] += 1
        ws.send(json.dumps({"id": mid[0], "method": method,
                            "params": params}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == mid[0]:
                return m.get("result", {})

    cmd("Page.enable")
    cmd("Runtime.enable")
    cmd("Emulation.setDeviceMetricsOverride", width=1280, height=800,
        deviceScaleFactor=1, mobile=False)
    cmd("Page.navigate", url=url)
    time.sleep(wait_s)
    r = cmd("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
    print("EVAL:", json.dumps(r.get("result", {}).get("value")))
    if out != "-":
        shot = cmd("Page.captureScreenshot", format="png")
        open(out, "wb").write(base64.b64decode(shot["data"]))
        print("SHOT:", out)
finally:
    chrome.terminate()
    chrome.wait()
