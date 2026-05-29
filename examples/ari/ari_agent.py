#!/usr/bin/env python3

import json
from loam.runtime.ari import Agent

def main():
    agent = Agent()

    url = agent.args[0] if agent.args else "https://example.com"

    # 1. Fetch
    resp = agent.tool("http.request", {
        "method": "GET",
        "url": url,
        "headers": {},
        "body": None,
    })

    parsed = json.loads(resp["stdout"])

    # 2. Write body to scratch
    agent.tool("fs.write", {
        "path": "scratch://page.html",
        "content": parsed["body"],
    })

    # 3. Read it back
    reread = agent.tool("fs.read", {
        "path": "scratch://page.html",
    })

    reread_parsed = json.loads(reread["stdout"])

    # 4. Finish
    agent.finish({
        "requested_url": url,
        "exit_code": resp["exit_code"],
        "scratch_file_bytes": len(reread_parsed["content"]),
        "artifact": resp["artifact"],
    })

if __name__ == "__main__":
    main()
