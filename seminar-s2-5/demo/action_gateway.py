"""Deterministic action-boundary gateway for the CO5151 S2-5 seminar demo.

The whole point of the seminar: the boundary between an agent and a harmful
action must be enforced by code that does NOT read the model's output as an
instruction. This module is that code, in ~200 lines, with no LLM and no
network access. It mirrors ``configs/action_policy.yaml`` from slide 21.

Run ``python run_demo.py`` for the scripted scenarios, or ``serve_demo.py``
for the interactive page.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

ALLOW = "ALLOW"
APPROVE = "REQUIRE_APPROVAL"
DENY = "DENY"

# --------------------------------------------------------------------------
# Policy: the machine-readable part. Same shape as slide 21 / Backup 4.
# --------------------------------------------------------------------------
POLICY: Dict[str, Any] = {
    "version": 3,
    "default": DENY,
    "agents": {
        # C0: read-only access to the statute corpus.
        "lawgraph": {
            "cred": "db_ro_lawgraph",
            "tools": {
                "graph_read": {"class": "C0", "calls_max": 8},
            },
        },
        # C0: read-only access to the validity tables.
        "auditor": {
            "cred": "db_ro_validity",
            "tools": {
                "validity_lookup": {"class": "C0"},
                "clause_exists": {"class": "C0"},
            },
        },
        # C1: no credential at all; it only emits an artifact into staging/.
        "drafter": {
            "cred": None,
            "tools": {
                "file_emit": {"class": "C1", "files_max": 3},
            },
        },
        # The only component allowed to touch the outside world.
        "executor": {
            "cred": "svc_executor",
            "tools": {
                "email_send": {"class": "C2", "per_day": 20},
                "http_post": {"class": "C2", "per_day": 20},
                "db_write_status": {"class": "C3"},
                "policy_update": {"class": "C4"},
            },
        },
    },
    "class_rules": {"C0": ALLOW, "C1": ALLOW, "C2": APPROVE, "C3": DENY, "C4": DENY},
    # Content from these sources is data, never an instruction.
    "taint_sources": ("upload", "web", "email"),
    "taint_max_class": "C1",  # tainted origin may not drive C2+
}

# Request with no approver token, approval seen for a *different* payload, etc.
T_UNTIL = 24 * 3600


def canonical(tool: str, args: Dict[str, Any]) -> str:
    return json.dumps({"tool": tool, "args": args}, sort_keys=True, ensure_ascii=False)


def payload_hash(tool: str, args: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical(tool, args).encode("utf-8")).hexdigest()[:12]


@dataclass
class Request:
    agent: str
    tool: str
    args: Dict[str, Any] = field(default_factory=dict)
    # e.g. ["user"] or ["doc:upload:hopdong.pdf"] -- anything not "user"/"planner"
    # coming from a taint source marks the request as tainted.
    origin: List[str] = field(default_factory=lambda: ["user"])
    approval_token: Optional[str] = None
    idempotency_key: Optional[str] = None


@dataclass
class Decision:
    kind: str
    reason: str
    tool_class: Optional[str] = None
    token: Optional[str] = None
    replayed: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "reason": self.reason,
            "tool_class": self.tool_class,
            "token": self.token,
            "replayed": self.replayed,
        }


class Gateway:
    """Deny-by-default executor. Has no model in the loop."""

    def __init__(self) -> None:
        self._calls: Dict[str, int] = {}
        self._seen_idem: Dict[str, Decision] = {}
        self.audit: List[Dict[str, Any]] = []
        self._prev = "genesis"

    # -- helpers ---------------------------------------------------------
    def _record(self, req: Request, dec: Decision) -> None:
        entry = {
            "t": round(time.time(), 3),
            "agent": req.agent,
            "tool": req.tool,
            "args_hash": payload_hash(req.tool, req.args),
            "origin": req.origin,
            "decision": dec.kind,
            "replayed": dec.replayed,
            "reason": dec.reason,
            "prev": self._prev,
        }
        blob = json.dumps(entry, sort_keys=True, ensure_ascii=False)
        entry["hash"] = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]
        self._prev = entry["hash"]
        self.audit.append(entry)

    @staticmethod
    def _tainted(req: Request) -> bool:
        """Origin entries look like "user", "upload:<file>", "web:<url>", "email:<id>"."""
        return any(
            src.split(":", 1)[0] in POLICY["taint_sources"] for src in req.origin
        )

    def _tool_spec(self, agent: str, tool: str) -> Optional[Dict[str, Any]]:
        return POLICY["agents"].get(agent, {}).get("tools", {}).get(tool)

    # -- approval tokens -------------------------------------------------
    def issue_approval(
        self, tool: str, args: Dict[str, Any], approver: str = "reviewer", ttl: int = T_UNTIL
    ) -> str:
        exp = int(time.time()) + ttl
        return f"{payload_hash(tool, args)}.{approver}.{exp}"

    def _verify_approval(self, req: Request) -> tuple[bool, str]:
        if not req.approval_token:
            return False, "no approval token"
        try:
            h, approver, exp = req.approval_token.split(".")
            exp_i = int(exp)
        except ValueError:
            return False, "malformed token"
        if h != payload_hash(req.tool, req.args):
            return False, "approval bound to a different payload (hash mismatch)"
        if exp_i < int(time.time()):
            return False, "approval expired"
        if not approver:
            return False, "no approver identity"
        return True, f"approved by {approver}"

    # -- the decision ----------------------------------------------------
    def decide(self, req: Request) -> Decision:
        # A repeated side-effect is not a second side-effect.
        if req.idempotency_key:
            key = f"{req.agent}:{req.tool}:{req.idempotency_key}"
            if key in self._seen_idem:
                prev = self._seen_idem[key]
                dec = Decision(prev.kind, "idempotent replay (no second side effect)",
                               prev.tool_class, replayed=True)
                self._record(req, dec)
                return dec

        spec = self._tool_spec(req.agent, req.tool)
        if spec is None:
            dec = Decision(DENY, "tool not in allowlist for this agent")
            self._record(req, dec)
            return dec

        cls = spec["class"]

        # 1) tainted content can inform a decision, never perform one
        if self._tainted(req) and cls not in ("C0", "C1"):
            dec = Decision(DENY, "tainted origin may not drive C2+ action", cls)
            self._record(req, dec)
            return dec

        # 2) class rule
        rule = POLICY["class_rules"].get(cls, DENY)
        if rule == DENY:
            dec = Decision(DENY, f"class {cls} is deny-by-default", cls)
            self._record(req, dec)
            return dec

        # 3) budget / parameter bounds
        key = f"{req.agent}:{req.tool}"
        used = self._calls.get(key, 0)
        cap = spec.get("calls_max") or spec.get("per_day")
        if cap is not None and used >= cap:
            dec = Decision(DENY, f"budget exhausted ({used}/{cap})", cls)
            self._record(req, dec)
            return dec

        # 4) approval for C2: missing token -> ask; bad token -> refuse
        if rule == APPROVE:
            ok, why = self._verify_approval(req)
            if not ok:
                if req.approval_token is None:
                    dec = Decision(APPROVE, why, cls)
                else:
                    dec = Decision(DENY, f"invalid approval: {why}", cls)
                self._record(req, dec)
                return dec
            reason = f"{why}; payload hash {payload_hash(req.tool, req.args)}"
        else:
            reason = f"class {cls} auto-allowed"

        self._calls[key] = used + 1
        dec = Decision(ALLOW, reason, cls)
        if req.idempotency_key:
            self._seen_idem[f"{req.agent}:{req.tool}:{req.idempotency_key}"] = dec
        self._record(req, dec)
        return dec

    def decide_prompt_only(self, req: Request, record: bool = False) -> Decision:
        """What happens when the 'boundary' lives in the system prompt only.

        The model was told to be careful; here we simulate a compliant-looking
        model that says yes to everything it is asked. Nothing is recorded by
        default, because in this mode nothing is actually *enforced* -- putting
        it in the audit log would misrepresent what happened.
        """
        dec = Decision(ALLOW, "model says it will be careful (no enforcement)", None)
        if record:
            self._record(req, dec)
        return dec

    def reset(self) -> None:
        self._calls.clear()
        self._seen_idem.clear()
        self.audit.clear()
        self._prev = "genesis"
