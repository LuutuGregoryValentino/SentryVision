from app import create_app

class TestConfig:
    SECRET_KEY = 'test'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    API_KEY = 'test-key'

app = create_app(TestConfig)
client = app.test_client()
resp = client.post('/api/v1/facial-recognition/', json={}, headers={'X-API-Key': 'test-key'})
print(resp.status_code)
print(resp.get_json())
