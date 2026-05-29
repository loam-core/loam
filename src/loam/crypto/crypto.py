import os
import base64
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

def make_kdf_info_scrypt() -> dict:
    salt = os.urandom(16)
    params = {"n": 2**14, "r": 8, "p": 1}
    return {
        "algo": "scrypt",
        "salt": base64.b64encode(salt).decode("ascii"),
        "params": params,
    }

def derive_key_from_passphrase(passphrase: str, kdf_info: dict) -> bytes:
    if kdf_info["algo"] != "scrypt":
        raise ValueError(f"Unsupported KDF algo: {kdf_info['algo']}")

    salt = base64.b64decode(kdf_info["salt"])
    params = kdf_info["params"]

    kdf = Scrypt(
        salt=salt,
        length=32,
        n=params["n"],
        r=params["r"],
        p=params["p"],
    )
    return kdf.derive(passphrase.encode("utf-8"))