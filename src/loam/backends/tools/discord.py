#backends/tools/discord.py
import httpx
from loam.identity.secrets import secret_load


DISCORD_API_BASE = "https://discord.com/api/v10"


def send_message(context, args):
    channel_id = args["channel_id"]
    content = args["content"]

    token = secret_load(context.store_id, "discord_bot_token", ksctx=context.ksctx)

    with httpx.Client(timeout=10) as client:
        response = client.post(
            f"{DISCORD_API_BASE}/channels/{channel_id}/messages",
            headers={"Authorization": f"Bot {token}"},
            json={"content": content},
        )

    body = {}
    try:
        body = response.json()
    except Exception:
        pass

    data = {
        "status": response.status_code,
        "message_id": body.get("id", None),
    }

    return {
        "result": data,
        "meta": {"channel_id": channel_id, "status": data["status"]},
    }


def fetch_messages(context, args):
    channel_id = args["channel_id"]

    token = secret_load(context.store_id, "discord_bot_token", ksctx=context.ksctx)

    with httpx.Client(timeout=10) as client:
        response = client.get(
            f"{DISCORD_API_BASE}/channels/{channel_id}/messages",
            headers={"Authorization": f"Bot {token}"},
            params={"limit": 50},
        )

    messages = response.json() if response.status_code == 200 else []

    return {
        "result": {"messages": messages},
        "meta": {"channel_id": channel_id, "count": len(messages)},
    }


def _resolve_bot_token(context):
    return secret_load(context.store_id, "discord_bot_token", ksctx=context.ksctx)


def fetch_reactions(context, args):
    channel_id = args["channel_id"]
    message_id = args["message_id"]
    emoji = args.get("emoji", "%F0%9F%91%8D")  # URL-encoded 👍

    token = secret_load(context.store_id, "discord_bot_token", ksctx=context.ksctx)

    with httpx.Client(timeout=10) as client:
        response = client.get(
            f"{DISCORD_API_BASE}/channels/{channel_id}/messages/{message_id}/reactions/{emoji}",
            headers={"Authorization": f"Bot {token}"},
        )

    # Discord returns a list of users who reacted.
    # We convert that into a reaction object compatible with your workflow.
    users = response.json() if response.status_code == 200 else []

    return {
        "result": {
            "reactions": [{
                "emoji": {"name": "👍"},
                "count": len(users),
            }]
        },
        "meta": {"channel_id": channel_id, "message_id": message_id},
    }
