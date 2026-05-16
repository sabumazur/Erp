class HistoryMixin:
    history_limit = 20

    def get_history(self, obj):
        records = list(
            obj.history.select_related("history_user").order_by("-history_date")[: self.history_limit]
        )
        for record in records:
            record.delta = record.diff_against(record.prev_record) if record.prev_record else None
        return records
