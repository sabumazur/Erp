from allauth.account.adapter import DefaultAccountAdapter

_SUPPRESSED = {
    "account/messages/logged_in.txt",
    "account/messages/logged_out.txt",
}


class AccountAdapter(DefaultAccountAdapter):
    def add_message(self, request, level, message_template, *args, **kwargs):
        if message_template in _SUPPRESSED:
            return
        super().add_message(request, level, message_template, *args, **kwargs)
