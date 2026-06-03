"""Cedar Policy Decision Point adapter — see ADR-0003-cedar-policy-schema.md."""

import cedarpy

from seatbelt.types import AuthzRequest, Decision


class CedarPDP:
    """PDP backed by cedarpy. Fail-closed on any error."""

    # MVP policy subset: default-deny via forbid-overrides-permit.
    POLICIES = """\
permit(principal, action == Seatbelt::Action::"AdmitInput", resource);
forbid(principal, action == Seatbelt::Action::"AdmitInput", resource) when { context.scope_verdict == "offscope" };
permit(principal, action == Seatbelt::Action::"Egress", resource);
forbid(principal, action == Seatbelt::Action::"Egress", resource) when { !resource.allowlisted };
"""

    def decide(self, req: AuthzRequest) -> Decision:
        try:
            # cedarpy entity dict shape: {"uid": {"type": str, "id": str}, "attrs": dict, "parents": list}
            entities = [
                {"uid": {"type": "Seatbelt::Session", "id": req.principal_id}, "attrs": {}, "parents": []},
                {"uid": {"type": req.resource_type, "id": req.resource_id}, "attrs": req.resource_attrs, "parents": []},
            ]
            request = {
                "principal": f'Seatbelt::Session::"{req.principal_id}"',
                "action": f'Seatbelt::Action::"{req.action}"',
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
