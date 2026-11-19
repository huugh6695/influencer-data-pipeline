import sys, json

TOOLS = [
    {
        "name": "add_numbers",
        "description": "返回两个数字之和",
        "inputSchema": {
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
    },
    {
        "name": "read_note",
        "description": "读取一条演示笔记",
        "inputSchema": {"type": "object", "properties": {"key": {"type": "string"}}},
    },
]

NOTES = {"demo": "MCP 握手成功：initialize -> tools/list -> tools/call"}

# 出口: 写 stdout
def send(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()

def handle(req):
    method = req.get("method")
    rid = req.get("id")
    params = req.get("params") or {}

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "demo-mcp", "version": "0.1.0"},
        }}
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        if name == "add_numbers":
            out = args.get("a", 0) + args.get("b", 0)
            text = f"{args.get('a')} + {args.get('b')} = {out}"
        elif name == "read_note":
            text = NOTES.get(args.get("key", ""), "not found")
        else:
            return {"jsonrpc": "2.0", "id": rid,
                    "error": {"code": -32601, "message": f"unknown tool: {name}"}}
        return {"jsonrpc": "2.0", "id": rid,
                "result": {"content": [{"type": "text", "text": text}], "isError": False}}
    return {"jsonrpc": "2.0", "id": rid,
            "error": {"code": -32601, "message": f"method not found: {method}"}}

# 入口: stdio 主循环
def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(req)
        if resp is not None:
            send(resp)

if __name__ == "__main__":
    main()
