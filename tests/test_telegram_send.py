"""Tests for the runner-side Telegram sender. No network: post() is mocked."""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import telegram_send as ts  # noqa: E402

FAKE_TOKEN = "1234567890:" + "C" * 35
DATE = "2026-11-04"


class SenderTests(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        self.dir = tempfile.mkdtemp(prefix="tg-send-")
        os.chdir(self.dir)
        os.makedirs("telegram")
        with open(ts.LOG, "w", encoding="utf-8") as f:
            json.dump({"sent": [{"date": "2026-11-03", "message_id": 90, "status": "ok"}]}, f)
        self.env = mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": FAKE_TOKEN, "TELEGRAM_CHAT_ID": "-1001234567890"})
        self.env.start()
        self.calls = []
        self.next_id = 100

        def fake_post(token, payload, timeout=30):
            self.calls.append(payload)
            self.next_id += 1
            return True, {"ok": True, "result": {"message_id": self.next_id}}, 200

        self.post = mock.patch.object(ts, "post", side_effect=fake_post)
        self.post.start()

    def tearDown(self):
        self.post.stop()
        self.env.stop()
        os.chdir(self._cwd)

    def outbox(self, text="Today's AI News", kind=None, date=DATE):
        data = {"date": date, "text": text}
        if kind:
            data["kind"] = kind
        with open(ts.OUTBOX, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def run_main(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = ts.main()
        return code, out.getvalue()

    def log(self):
        with open(ts.LOG, encoding="utf-8") as f:
            return json.load(f)

    def test_no_outbox_is_a_noop(self):
        self.assertEqual(self.run_main()[0], 0)
        self.assertEqual(self.calls, [])

    def test_briefing_sent_once_per_date(self):
        self.outbox()
        self.assertEqual(self.run_main()[0], 0)
        self.outbox("second attempt")
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("ALREADY DELIVERED", out)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual([e["message_id"] for e in self.log()["sent"] if e["date"] == DATE], [101])

    def test_alert_gets_through_after_briefing_but_only_once(self):
        self.outbox()
        self.run_main()
        self.outbox("pipeline FAILED at step 6", kind="alert")
        self.assertEqual(self.run_main()[0], 0)
        self.outbox("another alert", kind="alert")
        self.run_main()
        self.assertEqual(len(self.calls), 2)
        log = self.log()
        self.assertEqual([e["date"] for e in log["alerts"]], [DATE])
        self.assertEqual(len([e for e in log["sent"] if e["date"] == DATE]), 1)

    def test_unknown_kind_is_rejected(self):
        self.outbox(kind="spam")
        self.assertEqual(self.run_main()[0], 2)
        self.assertEqual(self.calls, [])

    def test_plain_text_and_token_never_printed(self):
        self.outbox("<a href='https://phish.example'>x</a>")
        _, out = self.run_main()
        self.assertNotIn(FAKE_TOKEN, out)
        self.assertNotIn("parse_mode", self.calls[0])
        self.assertTrue(self.calls[0]["disable_web_page_preview"])

    def test_failure_records_last_error_without_marking_sent(self):
        self.post.stop()
        with mock.patch.object(ts, "post", return_value=(False, {"error_code": 401, "description": "Unauthorized"}, 401)):
            self.outbox()
            code, _ = self.run_main()
        self.post.start()
        self.assertEqual(code, 1)
        log = self.log()
        self.assertEqual(log["last_error"]["date"], DATE)
        self.assertFalse([e for e in log["sent"] if e["date"] == DATE])

    def test_rate_limit_is_retried(self):
        responses = [(False, {"error_code": 429, "parameters": {"retry_after": 1}}, 429),
                     (True, {"ok": True, "result": {"message_id": 7}}, 200)]
        self.post.stop()
        with mock.patch.object(ts, "post", side_effect=responses), mock.patch.object(ts.time, "sleep") as sleep:
            self.outbox()
            code, _ = self.run_main()
        self.post.start()
        self.assertEqual(code, 0)
        sleep.assert_called_once_with(1)

    def test_missing_secret_is_config_error(self):
        del os.environ["TELEGRAM_BOT_TOKEN"]
        self.outbox()
        self.assertEqual(self.run_main()[0], 2)

    def test_long_message_keeps_briefing_link(self):
        body = ts.truncate("x" * 3000 + "\n" + "y" * 3000 + "\n" + ts.BRIEFING_LINK)
        self.assertLessEqual(len(body), ts.MAX_TEXT)
        self.assertTrue(body.endswith(ts.BRIEFING_LINK))


if __name__ == "__main__":
    unittest.main()
