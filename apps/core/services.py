"""
Service layer conventions for SabSys.

Every service module must follow these rules for history integration:

1. Import the helper:
       from apps.core.history import record_change_reason

2. After any .save() call where a change_reason string is available:
       instance.save()
       record_change_reason(instance, reason)

3. For mutations outside a request context (management commands, Celery tasks),
   attach the acting user before saving so history records the correct user:
       instance._history_user = acting_user
       instance.save()
       record_change_reason(instance, reason)

These rules apply to all services in apps/<app>/services.py.
Existing services are not modified; this file documents the convention only.
"""
