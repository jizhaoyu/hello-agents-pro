import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import app


class ShareSiteTestCase(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_homepage_and_learning_content(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        response.close()

        overview = self.client.get('/api/learning')
        self.assertEqual(overview.status_code, 200)
        learning = overview.get_json()['data']
        self.assertEqual(len(learning['chapters']), 16)
        self.assertEqual(len(learning['phases']), 5)

        note = self.client.get('/api/learning/chapter-08')
        self.assertEqual(note.status_code, 200)
        self.assertIn('RAG', note.get_json()['data']['content'])

    def test_local_agent_keeps_core_learning_modes(self):
        status = self.client.get('/api/agent/status').get_json()['data']
        capability_ids = {item['id'] for item in status['capabilities']}
        self.assertEqual(capability_ids, {
            'foundation',
            'reasoning_patterns',
            'memory_tools_context',
            'learning_assistant',
        })
        self.assertNotIn('facts', status['memory'])
        self.assertNotIn('preferences', status['memory'])

        calculation = self.client.post('/api/agent/chat', json={
            'message': '帮我计算 123 + 456',
            'mode': 'auto',
            'use_real_ai': False,
        })
        self.assertEqual(calculation.status_code, 200)
        self.assertIn('579', calculation.get_json()['answer'])

        reasoning = self.client.post('/api/agent/chat', json={
            'message': '用 ReAct 解释什么是智能体',
            'mode': 'reasoning_patterns',
            'use_real_ai': False,
        })
        self.assertEqual(reasoning.status_code, 200)
        self.assertIn('Action:', reasoning.get_json()['answer'])

    def test_chat_rejects_invalid_or_unbounded_input(self):
        for payload in ('text', 123, []):
            with self.subTest(payload=payload):
                self.assertEqual(
                    self.client.post('/api/agent/chat', json=payload).status_code,
                    400,
                )

        self.assertEqual(
            self.client.post('/api/agent/chat', json={'message': 'x' * 2001}).status_code,
            413,
        )
        self.assertEqual(
            self.client.post('/api/agent/chat', json={
                'message': '你好',
                'use_real_ai': True,
            }).status_code,
            400,
        )

    def test_development_only_routes_are_not_available(self):
        self.assertIn(self.client.post('/api/agent/upgrade', json={}).status_code, {404, 405})
        self.assertIn(
            self.client.post('/api/run/chapter01/interactive_agent', json={}).status_code,
            {404, 405},
        )

    def test_cors_is_not_open_to_arbitrary_origins(self):
        response = self.client.get('/api/health', headers={
            'Origin': 'https://example.test',
        })
        self.assertIsNone(response.headers.get('Access-Control-Allow-Origin'))


if __name__ == '__main__':
    unittest.main()
