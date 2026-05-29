#runtime/id_runtime.py
# IdentityRuntime: the identity‑anchored substrate membrane.
# Owns identity physics: continuity, chronicle, secrets, state hashing, identity metadata.

from datetime import datetime, timezone
import os
import json
from pathlib import Path
import hashlib
import tomllib
import uuid

from loam.identity.keysources import KeySourceContext
from loam.identity.paths import (
    continuity_dir,
    continuity_log,
    chronicle_dir,
    chronicle_log,
    PUBLIC_KEY,
    ROOT_DOSSIER,
)
from loam.identity.toml_loader import load_identity_toml, load_state_config
from loam.chronicle.emitter import emit_chronicle_event

from loam.continuity.append import (
    create_continuity_record,
    append_continuity_record,
)
from loam.identity.secrets import SECRET_OPERATIONS, secret_load
from loam.identity.identity_fingerprint import (
    build_identity_fingerprint_v1,
    compute_identity_fingerprint_hash_v1,
)
from loam.runtime.llm_loader import load_llm_backend
from loam.substrate.signer_factory import create_signer
from loam.substrate.state_hashing import compute_state_hash
from loam.substrate.trust import verify_trust_boundaries

from ..substrate.config import Config

class IdentityRuntime:
    """
    IdentityRuntime is the identity‑plane membrane.
    It owns:
      - identity fingerprint + hash
      - continuity (seq + append)
      - chronicle emission
      - state hashing
      - secret access
    """

    # SimulationRuntime overrides this to forbid identity-plane ops.
    def assert_not_simulation(self):
        return

    def __init__(self, identity_path: Path, passphrase=None):
        # ------------------------------------------------------------
        # Identity-plane configuration
        # ------------------------------------------------------------
        self.config = Config(store_path=identity_path)
        self.passphrase = passphrase
        self.ksctx = KeySourceContext(passphrase=passphrase)
        # Store ontology
        self.store_path = Path(identity_path)
        self.store_id = self.store_path.name

        # Canonical substrate paths
        self.continuity_dir = continuity_dir(self.store_id)
        self.continuity_log_path = continuity_log(self.store_id)
        self.chronicle_dir = chronicle_dir(self.store_id)
        self.chronicle_log_path = chronicle_log(self.store_id)

        # Ensure dossier + secrets directories exist
        self.dossier_dir = self.store_path / "dossier"
        self.dossier_dir.mkdir(exist_ok=True)
        self.secrets_dir = self.store_path / "secrets"
        self.secrets_dir.mkdir(exist_ok=True)

        # Envelope placeholders (ExecRuntime/SimulationRuntime fill these)
        self.envelope = None
        self.envelope_hash = None

        # Continuity sequence (updated on finalize_continuity)
        self.current_continuity_seq = 0
        self._authority_initialized = False
        
        # ------------------------------------------------------------
        # Load identity.toml + state config
        # ------------------------------------------------------------
        identity_toml_path = self.store_path / "identity.toml"
        toml_data = load_identity_toml(identity_toml_path)
        state_cfg = load_state_config(toml_data)
        self.state_cfg = state_cfg
        
        #policy enforcement
        self.policy_tools = toml_data.get("tools", {})
        self.policy_subprocess = toml_data.get("subprocess", {})
        self.policy_filesystem = toml_data.get("filesystem", {})
        self.policy_http = toml_data.get("http", {})
        self.policy_llm = toml_data.get("llm", {})
        self.policy_approvals = toml_data.get("approvals", {})
        self.policy = PolicyEnforcer(self)

        # State hashing enabled?
        self.state_enabled = bool(state_cfg and state_cfg.hashing_enabled)

        # Resolve state directory
        p = Path(state_cfg.path) if state_cfg and state_cfg.path else None
        if p is None:
            self.state_dir = None
        elif p.is_absolute():
            self.state_dir = p
        else:
            self.state_dir = (self.store_path / p).resolve()

    # ------------------------------------------------------------
    # Envelope creation (identity-bound fields only)
    # ExecRuntime / SimulationRuntime fill in simulation_depth + timestamp
    # ------------------------------------------------------------
    def create_execution_envelope(self, simulation_depth: int):
        self._require_authority()
        run_id = uuid.uuid4().hex

        envelope = {
            "schema_version": 1,
            "run_id": run_id,
            "simulation_depth": simulation_depth,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "identity_fingerprint_hash": self.identity_fingerprint_hash(),
            "store_id": self.store_id,
        }

        self.envelope = envelope
        self.run_id = run_id
        return envelope
    
    # ------------------------------------------------------------
    # Trust Pipeline
    # ------------------------------------------------------------
    
    def initialize_authority(self):
        if self._authority_initialized:
            return

        # 1. Load identity metadata (fingerprint, dossier, etc.)
        self.identity = self._load_identity()

        # 2. Load signer FIRST so chronicle can sign events
        descriptor_path = self.store_path / "keys" / "key_descriptor.json"
        with open(descriptor_path, "r") as f:
            signer_config = json.load(f)

        self.signer = create_signer(signer_config, ksctx=self.ksctx)

        # 3. Mark authority initialized BEFORE trust checks
        self._authority_initialized = True

        # 4. Now run trust boundaries (chronicle is legal now)
        if not self.is_simulation():
            verify_trust_boundaries(self)

    # ------------------------------------------------------------
    # Continuity
    # ------------------------------------------------------------
    def finalize_continuity(self):
        self._require_authority()
        self.assert_not_simulation()

        identity_fingerprint = build_identity_fingerprint_v1(self.store_id)
        identity_fingerprint_hash = compute_identity_fingerprint_hash_v1(identity_fingerprint)

        # Optional state hash
        new_state_hash = None
        if self.state_cfg.hashing_enabled and self.state_cfg.path:
            new_state_hash = compute_state_hash(self.state_dir)

        continuity_record = create_continuity_record(
            self.store_id,
            self.signer,
            identity_fingerprint_hash=identity_fingerprint_hash,
            state_hash=new_state_hash,
        )

        append_continuity_record(self.store_id, continuity_record)

        self.current_continuity_seq = continuity_record["seq"]
        return continuity_record, new_state_hash

    # ------------------------------------------------------------
    # State hashing
    # ------------------------------------------------------------
    def compute_current_state_hash(self) -> str | None:
        toml_path = self.store_path / "identity.toml"
        if not toml_path.exists():
            return None

        cfg = tomllib.loads(toml_path.read_text())
        state_cfg = cfg.get("state")
        if not state_cfg:
            return None

        rel_path = state_cfg.get("path")
        if not rel_path:
            return None

        state_path = self.store_path / rel_path
        if not state_path.exists():
            return None

        if state_path.is_file():
            return hashlib.sha256(state_path.read_bytes()).hexdigest()

        h = hashlib.sha256()
        for p in sorted(state_path.rglob("*")):
            if p.is_file():
                h.update(p.relative_to(state_path).as_posix().encode())
                h.update(p.read_bytes())
        return h.hexdigest()

    # ------------------------------------------------------------
    # Identity helpers
    # ------------------------------------------------------------
    def _load_identity(self) -> dict:
        store_path = self.config.store_path

        public_key_path = store_path / PUBLIC_KEY
        dossier_path = store_path / ROOT_DOSSIER

        root_dossier = {}
        if dossier_path.exists():
            root_dossier = json.loads(dossier_path.read_text())

        # NEW: unified identity fingerprint (raw key → sha256)
        identity_fingerprint = build_identity_fingerprint_v1(self.store_id)
        identity_fingerprint_hash = compute_identity_fingerprint_hash_v1(identity_fingerprint)

        # Cache them so we don't recompute later
        self._identity_fingerprint = identity_fingerprint
        self._identity_fingerprint_hash = identity_fingerprint_hash

        return {
            "root_dossier": root_dossier,
            "identity_fingerprint": identity_fingerprint,
            "identity_fingerprint_hash": identity_fingerprint_hash,
        }


    def identity_fingerprint_hash(self):
        # Return cached value instead of recomputing
        return self._identity_fingerprint_hash


    # ------------------------------------------------------------
    # Chronicle
    # ------------------------------------------------------------
    def chronicle(self, event_type, payload=None):
        self._require_authority()
        return emit_chronicle_event(self.store_id, event_type, payload or {}, self.signer)

    # ------------------------------------------------------------
    # Secrets
    # ------------------------------------------------------------
    def get_secret(self, name: str):
        self._require_authority()
        self.assert_not_simulation()
        self.policy.allow_secret(name, "load")


        try:
            plaintext = secret_load(self.store_id, name, ksctx=self.ksctx)
        except Exception as e:
            self.chronicle("secret_access_failed", {"name": name, "error": str(e)})
            raise

        self.chronicle("secret_accessed", {"name": name})
        return plaintext

    def _require_authority(self):
        if not self._authority_initialized:
            raise RuntimeError("identity_plane_not_initialized")



    def secret_use(self, name: str, operation: str, payload: bytes):
        """
        Use a secret without exposing it to the agent.
        operation: one of SECRET_OPERATIONS keys.
        payload: bytes to operate on.
        """
        self._require_authority()
        self.assert_not_simulation()
        self.policy.allow_secret(name, operation)

        if operation not in SECRET_OPERATIONS:
            raise ValueError(f"unsupported_operation: {operation}")

        try:
            result = SECRET_OPERATIONS[operation](self.store_id, name, payload, ksctx=self.ksctx)
        except Exception as e:
            self.chronicle(
                "secret_use_failed",
                {"name": name, "op": operation, "error": str(e)},
            )
            raise

        self.chronicle(
            "secret_used",
            {"name": name, "op": operation},
        )
        return result
    # ------------------------------------------------------------
    # LLM
    # ------------------------------------------------------------
    def cognition_llm_think(self, backend, input, model=None, tags=None):
        if backend is None:
            raise RuntimeError("Agent did not specify an LLM backend")

        # Lazy-load backend instance
        if self.llm_backend is None or self.llm_backend.provider_name != backend:
            self.llm_backend = load_llm_backend(backend, self)
        provider = backend

        # --- Identity policy check ---
        self.policy.allow_llm_model(model)

        # Chronicle start
        self.chronicle("cognition_start", {
            "cognition": "llm.think",
            "vendor": provider,
            "model": model,
            "input_hash": hash_str(input),
            "tags": tags or {},
        })

        try:
            data = self.llm_backend.think(
                input=input,
                model=model,
                tags=tags or {},
            )
            if not isinstance(data, dict):
                data = {"output": str(data)}

            if "output" not in data:
                data["output"] = ""

            # Chronicle finish
            self.chronicle("cognition_finished", {
                "cognition": "llm.think",
                "vendor": provider,
                "model": model,
                "input_hash": hash_str(input),
                "output_hash": hash_str(data.get("output", "")),
                "usage": data.get("usage"),
            })

            return data.get("output", "")


        except Exception as e:
            # Chronicle error
            self.chronicle("cognition_error", {
                "cognition": "llm.think",
                "vendor": provider,
                "model": model,
                "error": str(e),
                "error_type": type(e).__name__,
            })
            return""

def hash_str(s: str) -> str:
        return "sha256:" + hashlib.sha256(s.encode("utf-8")).hexdigest()

class PolicyEnforcer:
    def __init__(self, runtime):
        self.rt = runtime

    def allow_llm_model(self, model):
        if model is None:
            raise RuntimeError("Agent must specify an LLM model.")
        allowed = self.rt.policy_llm.get("allowed_models", [])
        if model not in allowed:
            raise RuntimeError(f"policy_denied: llm model '{model}' not allowed")


    def allow_tool(self, tool_name):
        allowed = self.rt.policy_tools.get("allowed", [])
        if tool_name not in allowed:
            raise RuntimeError(f"policy_denied: tool '{tool_name}' not allowed")

    def allow_http_domain(self, domain):
        allowed = self.rt.policy_http.get("allowed_domains", [])

        # Allow everything
        if "*" in allowed:
            return

        # Exact match
        if domain in allowed:
            return

        # Wildcard suffix match
        for pattern in allowed:
            if pattern.startswith("*."):
                suffix = pattern[1:]  # ".example.com"
                if domain.endswith(suffix):
                    return

        raise RuntimeError(f"policy_denied: http domain '{domain}' not allowed")

    def allow_subprocess(self, cmd):
        # cmd is the resolved executable path, e.g. "/usr/bin/echo"
        exe = cmd
        basename = os.path.basename(exe)
        dirname = os.path.dirname(exe)

        allowed_cmds = self.rt.policy_subprocess.get("allowed_commands", [])
        allowed_paths = self.rt.policy_subprocess.get("allowed_paths", [])

        # Check command name
        if basename not in allowed_cmds:
            raise RuntimeError(f"policy_denied: subprocess '{basename}' not allowed")

        # Check executable directory
        if dirname not in allowed_paths:
            raise RuntimeError(f"policy_denied: subprocess path '{dirname}' not allowed")

    def allow_fs_path(self, path):
        allowed = self.rt.policy_filesystem.get("allowed_paths", [])
        if not any(path.startswith(prefix) for prefix in allowed):
            raise RuntimeError(f"policy_denied: filesystem path '{path}' not allowed")

    def allow_secret(self, name, op):
        # optional: enforce secret names or ops, not implemented yet
        pass
