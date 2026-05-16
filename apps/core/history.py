from simple_history.utils import update_change_reason


def record_change_reason(instance, reason: str):
    """Attach a human-readable change reason to the latest history record."""
    if reason:
        update_change_reason(instance, reason)
