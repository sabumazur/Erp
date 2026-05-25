from django.urls import path
from .views import (
    DashboardView,
    ProfileView,
    SwitchOrganizationView,
    OrganizationSettingsView,
    MemberListView,
    ChangeMemberRoleView,
    RemoveMemberView,
    InviteMemberView,
    ResendInvitationView,
    CancelInvitationView,
    AcceptInvitationView,
    TeamListView,
    TeamUpdateView,
    TeamDeleteView,
    AssignMemberTeamView,
    CreateOrganizationView,
    LeaveOrganizationView,
    SessionKeepaliveView,
)

app_name = "accounts"

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("session/keepalive/", SessionKeepaliveView.as_view(), name="session_keepalive"),
    path("switch-org/<slug:slug>/", SwitchOrganizationView.as_view(), name="switch_org"),

    # Organisation management
    path("org/settings/", OrganizationSettingsView.as_view(), name="org_settings"),
    path("org/members/", MemberListView.as_view(), name="members"),
    path("org/members/<uuid:pk>/role/", ChangeMemberRoleView.as_view(), name="member_role"),
    path("org/members/<uuid:pk>/remove/", RemoveMemberView.as_view(), name="member_remove"),

    # Invitations
    path("org/invite/", InviteMemberView.as_view(), name="invite_member"),
    path("org/invitations/<uuid:pk>/resend/", ResendInvitationView.as_view(), name="invitation_resend"),
    path("org/invitations/<uuid:pk>/cancel/", CancelInvitationView.as_view(), name="invitation_cancel"),
    path("invitations/<uuid:pk>/accept/", AcceptInvitationView.as_view(), name="accept_invitation"),

    # Multi-org
    path("org/create/", CreateOrganizationView.as_view(), name="create_org"),
    path("org/leave/", LeaveOrganizationView.as_view(), name="leave_org"),

    # Teams
    path("org/teams/", TeamListView.as_view(), name="teams"),
    path("org/teams/<uuid:pk>/edit/", TeamUpdateView.as_view(), name="team_edit"),
    path("org/teams/<uuid:pk>/delete/", TeamDeleteView.as_view(), name="team_delete"),
    path("org/members/<uuid:pk>/assign-team/", AssignMemberTeamView.as_view(), name="member_assign_team"),
]
