import ssl
from django.core.mail.backends.smtp import EmailBackend


def _no_verify_context():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


class TLSNoVerifyEmailBackend(EmailBackend):
    """SMTP+STARTTLS backend with hostname verification disabled.

    Claro DR's SMTP server presents a cert for *.carrierzone.com, not for
    smtp.cafetropicalmazur.com, so standard hostname verification fails.
    This backend skips hostname/cert verification while still encrypting
    the connection with TLS.
    """

    def open(self):
        if self.connection:
            return False
        from django.core.mail.backends.smtp import DNS_NAME
        connection_params = {"local_hostname": DNS_NAME.get_fqdn()}
        if self.timeout is not None:
            connection_params["timeout"] = self.timeout
        ctx = _no_verify_context()
        if self.use_ssl:
            connection_params["context"] = ctx
        try:
            self.connection = self.connection_class(
                self.host, self.port, **connection_params
            )
            if not self.use_ssl and self.use_tls:
                self.connection.starttls(context=ctx)
            if self.username and self.password:
                self.connection.login(self.username, self.password)
            return True
        except OSError:
            if not self.fail_silently:
                raise
