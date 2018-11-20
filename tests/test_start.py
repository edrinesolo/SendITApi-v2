import json
import unittest
from app import app
from app.database.database import Database


class TestsStart(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client(self)
        with app.app_context():
            connect = Database()
            connect.drop_tables()
            connect.create_tables()

    def test_app_doesnot_work_without_token(self):
        rs = self.client.get('/', content_type="application/json", data='')
        self.assertEqual(rs.status_code, 401)
        data=json.loads(rs.data.decode())
        self.assertEqual(data['message'],'Not logged in,please login')

    def tearDown(self):
        with app.app_context():
            connect = Database()
            connect.drop_tables()
            connect.create_tables()
