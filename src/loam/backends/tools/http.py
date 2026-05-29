#backends/tools/http.py
import json
import httpx

def request(context, args):
    method = args["method"].upper()
    url = args["url"]
    headers = args.get("headers", {})
    body = args.get("body")
    timeout = args.get("timeout", 30)

    with httpx.Client(timeout=timeout) as client:
        response = client.request(
            method=method,
            url=url,
            headers=headers,
            content=body,
        )

    data = {
        "status": response.status_code,
        "headers": dict(response.headers),
        "body": response.text,
    }

    meta = {
        "method": method,
        "url": url,
        "status": data["status"],
        "response_bytes": len(data["body"].encode("utf-8")),
    }

    return {
        "result": data,
        "meta": meta,
    }
