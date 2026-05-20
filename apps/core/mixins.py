class HistoryMixin:
    history_limit = 50

    def get_history(self, obj):
        records = list(
            obj.history.select_related("history_user").order_by("-history_date")[: self.history_limit]
        )
        for i, record in enumerate(records):
            prev = records[i + 1] if i + 1 < len(records) else record.prev_record
            if prev:
                delta = record.diff_against(prev)
                record.diff_changes = _translate_changes(record, delta.changes)
            else:
                record.diff_changes = []
        return records


def _translate_changes(record, changes):
    translated = []
    for change in changes:
        try:
            field = record._meta.get_field(change.field)
            label = str(field.verbose_name)
            label = label[0].upper() + label[1:] if label else change.field
            old_val = change.old
            new_val = change.new
            if getattr(field, "choices", None):
                choices_map = dict(field.choices)
                old_val = choices_map.get(change.old, change.old)
                new_val = choices_map.get(change.new, change.new)
        except Exception:
            label = change.field
            old_val = change.old
            new_val = change.new
        translated.append({"field": label, "old": old_val, "new": new_val})
    return translated
