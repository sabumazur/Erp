from django.utils.deprecation import MiddlewareMixin
from .models import Organization, Membership


class OrganizationMiddleware(MiddlewareMixin):
    """
    Attaches request.organization and request.membership on every
    authenticated request.

    Resolution order:
    1. session["active_org_slug"]
    2. first membership (by created_at)
    """

    def process_request(self, request):
        request.organization = None
        request.membership = None

        if not request.user.is_authenticated:
            return

        slug = request.session.get("active_org_slug")

        if slug:
            try:
                membership = (
                    Membership.objects
                    .select_related("organization")
                    .get(user=request.user, organization__slug=slug)
                )
                request.organization = membership.organization
                request.membership = membership
                return
            except Membership.DoesNotExist:
                del request.session["active_org_slug"]

        membership = (
            Membership.objects
            .select_related("organization")
            .filter(user=request.user)
            .order_by("created_at")
            .first()
        )
        if membership:
            request.organization = membership.organization
            request.membership = membership
            request.session["active_org_slug"] = membership.organization.slug
