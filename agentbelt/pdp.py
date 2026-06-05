"""Cedar Policy Decision Point adapter — see ADR-0003-cedar-policy-schema.md."""

import cedarpy

from agentbelt.types import AuthzRequest, Decision


class CedarPDP:
    """PDP backed by cedarpy. Fail-closed on any error."""

    # MVP policy subset: default-deny via forbid-overrides-permit.
    POLICIES = """\
permit(principal, action == Agentbelt::Action::"AdmitInput", resource);
forbid(principal, action == Agentbelt::Action::"AdmitInput", resource) when { context.scope_verdict == "offscope" };
permit(principal, action == Agentbelt::Action::"InvokeTool", resource);
forbid(principal, action == Agentbelt::Action::"InvokeTool", resource) when { context.provenance_max_trust == "untrusted" && context.tier != "low" };
forbid(principal, action == Agentbelt::Action::"InvokeTool", resource) when { context.tier == "high" && !(context.user_verified && context.human_confirmed) };
permit(principal, action == Agentbelt::Action::"Egress", resource);
forbid(principal, action == Agentbelt::Action::"Egress", resource) when { !resource.allowlisted };
"""

    def decide(self, req: AuthzRequest) -> Decision:
        try:
            # cedarpy entity dict shape: {"uid": {"type": str, "id": str}, "attrs": dict, "parents": list}
            entities = [
                {"uid": {"type": "Agentbelt::Session", "id": req.principal_id}, "attrs": {}, "parents": []},
                {"uid": {"type": req.resource_type, "id": req.resource_id}, "attrs": req.resource_attrs, "parents": []},
            ]
            request = {
                "principal": f'Agentbelt::Session::"{req.principal_id}"',
                "action": f'Agentbelt::Action::"{req.action}"',
                "resource": f'{req.resource_type}::"{req.resource_id}"',
                "context": req.context,
            }
            result = cedarpy.is_authorized(request, self.POLICIES, entities)
            if result.decision == cedarpy.Decision.Allow:
                return Decision(effect="allow")
            reasons = [str(r) for r in result.diagnostics.reasons] if result.diagnostics.reasons else ["denied_by_policy"]
            return Decision(effect="deny", reasons=reasons)
        except Exception as e:
            return Decision(effect="deny", reasons=[f"pdp_error: {e}"])
