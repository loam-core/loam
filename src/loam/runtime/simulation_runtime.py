# runtime/simulation_runtime.py

from loam.runtime.id_runtime import IdentityRuntime
from loam.substrate.simulation_envelope import create_simulation_envelope, hash_envelope

class SimulationRuntime(IdentityRuntime):
    """
    SimulationRuntime: a capability‑stripped execution membrane used for
    hypothetical reasoning, planning, and nested simulation.
    """

class SimulationRuntime(IdentityRuntime):
    """
    SimulationRuntime: a capability-stripped execution membrane used for
    hypothetical reasoning, planning, and nested simulation.
    """

    def __init__(self, parent: IdentityRuntime, simulation_input):
        # MUST come first
        self.parent = parent

        # Clone identity-plane state from parent (read-only mirror)
        self.store_path = parent.store_path
        self.store_id = parent.store_id
        self.identity = parent.identity
        self.signer = parent.signer
        self.config = parent.config
        self.workdir = parent.workdir

        # Policy-plane (just mirror)
        self.policy_llm = parent.policy_llm
        self.policy = parent.policy
        
        # Inherit execution metadata from parent
        self.exec_path = parent.exec_path
        self.exec_basename = parent.exec_basename
        self.exec_code_hash = parent.exec_code_hash

        self.driver = parent.driver
        
        # Store simulation input
        self.simulation_input = simulation_input

        # Simulation depth = parent depth + 1
        parent_depth = parent.envelope["simulation_depth"]
        self.envelope = create_simulation_envelope(self)
        self.envelope["simulation_depth"] = parent_depth + 1
        self.envelope_hash = hash_envelope(self.envelope)
        self.run_id = self.envelope["run_id"]

        # Simulated chronicle buffer
        self.simulated_events = []

        self.llm_backend = None

    # Key: simulations share the parent’s identity fingerprint
    def identity_fingerprint_hash(self):
        return self.parent.identity_fingerprint_hash()

    # ------------------------------------------------------------
    # Simulation physics
    # ------------------------------------------------------------

    def is_simulation(self) -> bool:
        return True

    def assert_not_simulation(self):
        raise RuntimeError("operation_forbidden_in_simulation")

    def identity_fingerprint_hash(self):
        return self.parent.identity_fingerprint_hash()

    # ------------------------------------------------------------
    # Overrides: forbid real capabilities
    # ------------------------------------------------------------
    
    def initialize_authority(self):
        raise RuntimeError("simulation_cannot_enter_trust_pipeline")

    def run_tool(self, tool_name, tool_args):
        self.assert_not_simulation()

    def get_secret(self, name: str):
        self.assert_not_simulation()

    def finalize_continuity(self):
        self.assert_not_simulation()

    # ------------------------------------------------------------
    # Override init message to inject simulation_input
    # ------------------------------------------------------------

    def build_init_message(self, args):
        msg = super().build_init_message(args)
        msg["simulation_input"] = self.simulation_input
        return msg

    # ------------------------------------------------------------
    # Simulated chronicle (no real writes)
    # ------------------------------------------------------------

    def chronicle(self, event_type: str, payload=None):
        self.simulated_events.append({
            "event_type": event_type + "_simulated",
            "payload": payload or {},
        })
        return None

    def extract_simulation_telemetry(self):
        telemetry = {
            "token_usage": {},
            "models": [],
            "vendors": [],
            "input_hashes": [],
            "output_hashes": [],
        }

        for ev in self.simulated_events:
            if ev["event_type"] == "cognition_finished_simulated":
                payload = ev["payload"]

                usage = payload.get("usage")
                if usage:
                    telemetry["token_usage"] = merge_usage(
                        telemetry["token_usage"], usage
                    )

                telemetry["models"].append(payload.get("model"))
                telemetry["vendors"].append(payload.get("vendor"))
                telemetry["input_hashes"].append(payload.get("input_hash"))
                telemetry["output_hashes"].append(payload.get("output_hash"))

        return telemetry

def merge_usage(a, b):
    out = dict(a)
    for k, v in (b or {}).items():
        out[k] = out.get(k, 0) + (0 if v is None else v)

    return out
