"""Security regression tests. Run from the repo root: python3 -m unittest discover -s tests -v"""
import contextlib
import gzip
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")

_TMP = tempfile.mkdtemp(prefix="ai-news-test-")
os.environ["AI_NEWS_HOME"] = os.path.join(_TMP, "notes")
os.environ["AI_NEWS_WORK"] = os.path.join(_TMP, "work")
os.makedirs(os.environ["AI_NEWS_HOME"])
os.makedirs(os.environ["AI_NEWS_WORK"])
sys.path.insert(0, SCRIPTS)

import deploy_gate  # noqa: E402
import generate_briefing_fixed as gen  # noqa: E402
import prepare_publish  # noqa: E402
import telegram_deliver as tg  # noqa: E402
import template_validator  # noqa: E402

TEMPLATE = os.path.join(os.environ["AI_NEWS_HOME"], "master_template.html")
with open(os.path.join(ROOT, "master_template.html.gz.b64"), "rb") as f:
    TEMPLATE_HTML = gzip.decompress(f.read()).decode("utf-8")
with open(TEMPLATE, "w", encoding="utf-8") as f:
    f.write(TEMPLATE_HTML)

DATE = "2026-11-02"
FAKE_TOKEN = "1234567890:" + "A" * 35
FAKE_CHAT = "-1001234567890"


def article(**overrides):
    a = {"title": "Model X released", "url": "https://example.com/x", "source": "Example",
         "summary": "A model was released. It is fast. It is open.", "why_it_matters": "Speed.",
         "category": "LLM", "importance": 8}
    a.update(overrides)
    return a


def analysis(articles):
    return {"articles": articles,
            "trends": [{"title": "Open models", "description": "More open weights.", "related": ["Model"]}],
            "stats": {"total": 999, "collected": 30, "deduped": 25, "categories": {"<b>": 1}},
            "why_read": "Because.", "concept_title": "MoE", "concept_subtitle": "Experts",
            "concept_paras": ["Mixture of <em>experts</em> routes tokens."],
            "briefing_paragraphs": ["First paragraph.", "Second paragraph."]}


def build(articles):
    with contextlib.redirect_stderr(io.StringIO()):
        html = gen.build_briefing(analysis(articles), DATE, TEMPLATE)
    path = os.path.join(os.environ["AI_NEWS_WORK"], f"ai-news-{DATE}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return html, path


def validate_html(html):
    path = os.path.join(_TMP, "candidate.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return template_validator.validate(path, TEMPLATE)


class GeneratorTests(unittest.TestCase):
    def test_clean_build_passes_validator(self):
        html, path = build([article(), article(title="Paper Y", category="Research", importance=6)])
        passed, errors = template_validator.validate(path, TEMPLATE)
        self.assertTrue(passed, errors)
        self.assertIn(f"<title>AI News Daily \u2014 {DATE}</title>", html)

    def test_xss_payloads_are_escaped(self):
        payload = '<img src=x onerror="alert(1)">'
        html, path = build([article(title=payload, summary="<script>alert(2)</script>",
                                    source=payload, why_it_matters=payload)])
        self.assertNotIn("<img src=x", html)
        self.assertNotIn("<script>alert", html)
        passed, errors = template_validator.validate(path, TEMPLATE)
        self.assertTrue(passed, errors)

    def test_unsafe_urls_are_dropped_and_bare_hosts_fixed(self):
        cleaned = gen.clean_data(analysis([
            article(url="javascript:alert(1)"),
            article(url="data:text/html,<script>alert(1)</script>"),
            article(url="https://user:pass@evil.example/"),
            article(url="www.marktechpost.com/2026/09/29/story/"),
        ]))
        self.assertEqual([a["url"] for a in cleaned["articles"]],
                         ["https://www.marktechpost.com/2026/09/29/story/"])

    def test_numbers_are_clamped_and_stats_recomputed(self):
        cleaned = gen.clean_data(analysis([article(importance=99), article(importance="<b>"),
                                           article(category="<script>")]))
        self.assertEqual([a["importance"] for a in cleaned["articles"]], [10, 8])
        self.assertEqual(cleaned["articles"][1]["category"], "Industry")
        self.assertEqual(cleaned["stats"]["total"], 2)
        self.assertNotIn("<b>", cleaned["stats"]["categories"])

    def test_all_briefing_paragraphs_rendered(self):
        html, _ = build([article()])
        self.assertIn("<p>First paragraph.</p>", html)
        self.assertIn("<p>Second paragraph.</p>", html)

    def test_no_template_sample_content_leaks(self):
        html, _ = build([article()])
        for sample in ("1,200 test agents", "Hy4", "forbes.com", "2026-08-29"):
            self.assertNotIn(sample, html)

    def test_backslashes_are_not_regex_escapes(self):
        data = analysis([article()])
        data["briefing_paragraphs"] = [r"Path C:\new \1 \g<0>"]
        with contextlib.redirect_stderr(io.StringIO()):
            html = gen.build_briefing(data, DATE, TEMPLATE)
        self.assertIn(r"Path C:\new \1 \g&lt;0&gt;", html)


class ValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.good, _ = build([article()])

    def assertRejected(self, html):
        passed, errors = validate_html(html)
        self.assertFalse(passed, "tampered HTML was accepted")
        return errors

    def test_injected_script_rejected(self):
        self.assertRejected(self.good.replace("</body>", "<script>alert(1)</script></body>"))

    def test_inline_handler_rejected(self):
        self.assertRejected(self.good.replace('<div class="brief-list">', '<div class="brief-list" onmouseover="alert(1)">'))

    def test_javascript_href_rejected(self):
        self.assertRejected(self.good.replace('href="https://example.com/x"', 'href="javascript:alert(1)"', 1))

    def test_missing_csp_rejected(self):
        self.assertRejected(self.good.replace('http-equiv="Content-Security-Policy"', 'http-equiv="X-Removed"'))

    def test_iframe_rejected(self):
        self.assertRejected(self.good.replace("</body>", '<iframe src="https://evil.example"></iframe></body>'))

    def test_three_js_integrity_change_rejected(self):
        self.assertRejected(self.good.replace('integrity="sha384-', 'integrity="sha384-X', 1))


class TelegramTests(unittest.TestCase):
    def setUp(self):
        os.environ["TELEGRAM_BOT_TOKEN"] = FAKE_TOKEN
        os.environ["TELEGRAM_CHAT_ID"] = FAKE_CHAT
        with contextlib.suppress(FileNotFoundError):
            os.remove(tg.log_path())

    def test_no_hardcoded_credentials(self):
        for name in ("telegram_deliver.py", "pipeline_validator.py"):
            with open(os.path.join(SCRIPTS, name), encoding="utf-8") as f:
                self.assertNotRegex(f.read(), r"\d{8,10}:[A-Za-z0-9_-]{35}")

    def test_missing_credentials_fail_closed(self):
        del os.environ["TELEGRAM_BOT_TOKEN"]
        with self.assertRaises(tg.ConfigError):
            tg.build_telegram_url("hi")

    def test_token_is_never_printed(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            tg.build_url("<a href='https://phish.example'>click</a>")
        self.assertNotIn(FAKE_TOKEN, out.getvalue())
        with open(tg.url_output_path(), encoding="utf-8") as f:
            url = f.read()
        self.assertNotIn("parse_mode", url)  # plain text: markup is never rendered

    def test_delivery_log_uses_repo_format_and_blocks_duplicates(self):
        ok = json.dumps({"ok": True, "result": {"message_id": 90, "chat": {"id": int(FAKE_CHAT)}}})
        success, mid, err = tg.validate_response("wrapper text " + ok)
        self.assertTrue(success, err)
        with contextlib.redirect_stdout(io.StringIO()):
            tg.log_delivery_result(success, mid, err, DATE)
            tg.log_delivery_result(True, 91, None, DATE)  # second send for the same day
        log = tg.load_log()
        self.assertEqual([(e["date"], e["message_id"]) for e in log["sent"]], [(DATE, 90)])
        self.assertTrue(tg.is_delivered(DATE))

    def test_wrong_chat_is_not_counted_as_delivered(self):
        bad = {"ok": True, "result": {"message_id": 5, "chat": {"id": 42}}}
        self.assertFalse(tg.validate_response(bad)[0])

    def test_legacy_flat_log_is_migrated(self):
        with open(tg.log_path(), "w", encoding="utf-8") as f:
            json.dump({"date": DATE, "status": "delivered", "message_id": 7}, f)
        self.assertTrue(tg.is_delivered(DATE))


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.html, self.html_path = build([article()])
        self.root = tempfile.mkdtemp(dir=_TMP)
        os.makedirs(os.path.join(self.root, "scripts"))
        shutil.copy(os.path.join(SCRIPTS, "checksums.json"), os.path.join(self.root, "scripts"))
        shutil.copy(os.path.join(ROOT, "master_template.html.gz.b64"), self.root)
        old_argv = sys.argv
        sys.argv = ["prepare_publish.py", self.html_path, DATE]
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                prepare_publish.main()
        finally:
            sys.argv = old_argv
        for name in deploy_gate.PART_NAMES + ["data.manifest.json"]:
            shutil.copy(os.path.join(os.environ["AI_NEWS_WORK"], name), self.root)
        self.out = os.path.join(self.root, "index.html")

    def test_round_trip(self):
        self.assertEqual(deploy_gate.run(self.root, self.out), DATE)
        with open(self.out, encoding="utf-8") as f:
            self.assertEqual(f.read(), self.html)

    def test_tampered_part_rejected(self):
        with open(os.path.join(self.root, "data.gz.b64.part2"), "ab") as f:
            f.write(b"AAAA")
        with self.assertRaises(deploy_gate.GateError):
            deploy_gate.run(self.root, self.out)

    def test_malicious_but_consistent_payload_rejected(self):
        # An attacker who controls both parts and manifest still has to pass the validator.
        evil = self.html.replace("</body>", "<script>alert(1)</script></body>")
        with open(self.html_path, "w", encoding="utf-8") as f:
            f.write(evil)
        old_argv = sys.argv
        sys.argv = ["prepare_publish.py", self.html_path, DATE]
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                prepare_publish.main()
        finally:
            sys.argv = old_argv
        for name in deploy_gate.PART_NAMES + ["data.manifest.json"]:
            shutil.copy(os.path.join(os.environ["AI_NEWS_WORK"], name), self.root)
        with self.assertRaises(deploy_gate.GateError):
            deploy_gate.run(self.root, self.out)


if __name__ == "__main__":
    unittest.main()
