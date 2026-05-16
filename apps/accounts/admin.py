from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Organization, Team, Membership, Invitation
from apps.core.admin import ERPHistoryAdmin


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = ["email", "first_name", "last_name", "is_staff", "is_active"]
    search_fields = ["email", "first_name", "last_name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "avatar")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),
    )


@admin.register(Organization)
class OrganizationAdmin(ERPHistoryAdmin):
    list_display = ["name", "slug", "owner", "is_active"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Team)
class TeamAdmin(ERPHistoryAdmin):
    list_display = ["name", "organization"]
    list_filter = ["organization"]


@admin.register(Membership)
class MembershipAdmin(ERPHistoryAdmin):
    list_display = ["user", "organization", "team", "role"]
    list_filter = ["role", "organization"]


@admin.register(Invitation)
class InvitationAdmin(ERPHistoryAdmin):
    list_display = ["email", "organization", "role", "invited_by", "expires_at", "accepted_at"]
    list_filter = ["organization", "role"]
    search_fields = ["email"]
    readonly_fields = ["accepted_at", "expires_at", "invited_by"]
