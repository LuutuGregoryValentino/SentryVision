import importlib
import config
import smtplib

importlib.reload(config)
from config import Config

host = Config.MAIL_SERVER
port = Config.MAIL_PORT
use_tls = Config.MAIL_USE_TLS
user = Config.MAIL_USERNAME
# Do not print passwords
sender = Config.MAIL_DEFAULT_SENDER

print('SMTP host:', host)
print('SMTP port:', port)
print('Use TLS/STARTTLS:', use_tls)
print('Username:', user)
print('Sender:', sender)

try:
    with smtplib.SMTP(host, port, timeout=10) as s:
        code, msg = s.ehlo()
        print('EHLO:', code, msg)
        print('ESMTP features (pre-STARTTLS):', s.esmtp_features)
        if use_tls:
            try:
                s.starttls()
                s.ehlo()
                print('Started TLS successfully')
                print('ESMTP features (post-STARTTLS):', s.esmtp_features)
            except Exception as e:
                print('STARTTLS failed:', repr(e))
        if user and Config.MAIL_PASSWORD:
            try:
                s.login(user, Config.MAIL_PASSWORD)
                print('Login OK')
            except Exception as e:
                print('Login failed:', repr(e))
        else:
            print('No credentials provided; skipping login')
except Exception as e:
    print('Connection/setup failed:', repr(e))
