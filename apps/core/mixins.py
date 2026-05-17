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
                record.diff_changes = delta.changes
            else:
                record.diff_changes = []
        return records
