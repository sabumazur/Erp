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
