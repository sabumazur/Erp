from .models import Membership


class OrganizationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self._resolve_org(request)
        return self.get_response(request)

    def _resolve_org(self, request):
        request.organization = None
        request.membership = None

        if not request.user.is_authenticated:
            return

        usable_memberships = (
            Membership.objects
            .select_related("organization")
            .filter(
                user=request.user,
                organization__is_active=True,
                organization__deleted_at__isnull=True,
            )
        )
        slug = request.session.get("active_org_slug")

        if slug:
            try:
                membership = usable_memberships.get(organization__slug=slug)
                request.organization = membership.organization
                request.membership = membership
                return
            except Membership.DoesNotExist:
                request.session.pop("active_org_slug", None)

        membership = (
            usable_memberships
            .order_by("created_at")
            .first()
        )
        if membership:
            request.organization = membership.organization
            request.membership = membership
            request.session["active_org_slug"] = membership.organization.slug
