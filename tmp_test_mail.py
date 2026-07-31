import logging
from types import SimpleNamespace

from app import create_app
from app.services import send_unauthorized_notification

app = create_app()
app.logger.setLevel(logging.DEBUG)

with app.app_context():
    print('sender=', app.config.get('MAIL_DEFAULT_SENDER'))
    print('recipient=', app.config.get('ADMIN_EMAIL') or app.config.get('MAIL_DEFAULT_SENDER'))
    result = send_unauthorized_notification('instance/uploads/placeholder.jpg', SimpleNamespace(id=999, detected_label='Unknown', authorization_status='Unknown', confidence=60.0))
    print('result=', result)
