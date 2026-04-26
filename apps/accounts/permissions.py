from guardian.shortcuts import assign_perm, remove_perm
from .models import Membership


def can_access_module(membership, module_slug: str) -> bool:
    """
    Return True if the membership's role/team allows access to module_slug.

    Rules:
    - No membership         → False
    - Owner / Admin         → always True
    - Member/Viewer, no team assigned → True (no restriction applied yet)
    - Member/Viewer on a team with no modules set → True (empty = unrestricted)
    - Member/Viewer on a team with modules set → only those slugs pass
    """
    if not membership:
        return False
    if membership.is_admin:
        return True
    if not membership.team_id:
        return True
    allowed = list(membership.team.modules.values_list("slug", flat=True))
    if not allowed:
        return True
    return module_slug in allowed

# ── Role → permission map ─────────────────────────────────────────────────────
#
# Empty for now — auth layer has no business object permissions yet.
# Each ERP app will add its own block here when built.
#
# Format:
#   Membership.Role.OWNER: {
#       "app_label.ModelName": ["codename", ...],
#   }

ROLE_PERMISSIONS: dict[str, dict[str, list[str]]] = {
    Membership.Role.OWNER:  {},
    Membership.Role.ADMIN:  {},
    Membership.Role.MEMBER: {},
    Membership.Role.VIEWER: {},
}


def assign_org_permissions(membership: Membership) -> None:
    """
    Assign object-level permissions scoped to the user's Organization.
    Called by signal on every Membership save.
    Safe to call when ROLE_PERMISSIONS blocks are empty.
    """
    from django.apps import apps

    org = membership.organization
    user = membership.user
    role_perms = ROLE_PERMISSIONS.get(membership.role, {})

    for model_label, codenames in role_perms.items():
        app_label, model_name = model_label.split(".")
        try:
            apps.get_model(app_label, model_name)
        except LookupError:
            continue
        for codename in codenames:
            assign_perm(codename, user, org)


def revoke_org_permissions(membership: Membership) -> None:
    """
    Revoke all known permissions for a user on their Organization.
    Called before re-assigning on role change, or on membership deletion.
    """
    from django.apps import apps

    org = membership.organization
    user = membership.user

    for role_perms in ROLE_PERMISSIONS.values():
        for model_label, codenames in role_perms.items():
            app_label, model_name = model_label.split(".")
            try:
                apps.get_model(app_label, model_name)
            except LookupError:
                continue
            for codename in codenames:
                remove_perm(codename, user, org)
