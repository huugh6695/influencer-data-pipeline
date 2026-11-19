import subprocess, json, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
proc = subprocess.Popen([sys.executable, os.path.join(HERE, "server.py")],
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                        encoding="utf-8", errors="replace", env=env)
seq = 0

# 入口: 发一条 JSON-RPC 请求
def rpc(method, params=None, notify=False):
    global seq
    msg = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    if not notify:
        seq += 1
        msg["id"] = seq
    line = json.dumps(msg, ensure_ascii=False)
    print(f">>> {line}")
    proc.stdin.write(line + "\n")
    proc.stdin.flush()
    if notify:
        return None
    resp = proc.stdout.readline().strip()
    print(f"<<< {resp}")
    return json.loads(resp)

try:
    rpc("initialize", {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "demo-client", "version": "0.1.0"},
    })
    rpc("notifications/initialized", notify=True)
    rpc("tools/list")
    rpc("tools/call", {"name": "add_numbers", "arguments": {"a": 17, "b": 25}})
    rpc("tools/call", {"name": "read_note", "arguments": {"key": "demo"}})
    print("\nOK: MCP handshake + tool calls completed")
finally:
    proc.terminate()
