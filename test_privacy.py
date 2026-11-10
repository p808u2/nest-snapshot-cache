import unittest

from server import public_error


class PublicErrorTests(unittest.TestCase):
    def test_redacts_private_rtsp_url(self):
        value = public_error("Could not open rtsp://localhost:1234/private-stream: refused")
        self.assertEqual(value, "Could not open rtsp://[redacted] refused")

    def test_preserves_non_url_error(self):
        self.assertEqual(public_error("capture timed out"), "capture timed out")


if __name__ == "__main__":
    unittest.main()
