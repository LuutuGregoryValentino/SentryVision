import unittest

from app import create_app


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def test_dashboard_renders(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Facial Recognition Console", response.data)
        self.assertIn(b"Device Status", response.data)


if __name__ == "__main__":
    unittest.main()
