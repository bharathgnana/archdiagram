"""Browser shell routing and hosted MCP integration."""
import json
import os
import unittest
from unittest.mock import patch

try:
    from starlette.testclient import TestClient
    from mcp_server.server import mcp
except ImportError:
    TestClient = None

from mcp_server.access import ApiKeyGate, InvalidApiKey, key_digest
from mcp_server.web import BrowserApp


@unittest.skipUnless(TestClient, "MCP extra not installed")
class BrowserTests(unittest.TestCase):
    def test_browser_routes_and_mcp_remains_key_protected(self):
        class Store:
            async def consume(self, key_id, digest, month):
                if key_id != "buyer" or digest != key_digest("x" * 32, "pepper"):
                    raise InvalidApiKey("invalid key")

        # Cloud Run sets PORT before the server module initializes FastMCP.
        mcp.settings.stateless_http = True
        store = Store()
        app = BrowserApp(ApiKeyGate(mcp.streamable_http_app(), store, "pepper"), store, "pepper")
        with patch.dict(os.environ, {"PORT": "8080", "GOOGLE_CLOUD_PROJECT": "test-project",
                                    "ARCHDIAGRAM_FIREBASE_API_KEY": "public-web-key",
                                    "ARCHDIAGRAM_AUTH_DOMAIN": "test.firebaseapp.com"}), TestClient(app) as client:
            page = client.get("/")
            self.assertEqual(page.status_code, 200)
            self.assertIn("Diagram spec", page.text)
            self.assertEqual(client.get('/assets/app.js').status_code, 200)
            self.assertEqual(client.get('/api/browser-config').json()['projectId'], 'test-project')
            spec = {"nodes": [{"id": "a", "shape": "start"}], "edges": []}
            body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": "generate_diagram", "arguments": {"spec": spec, "format": "svg"}}}
            headers = {"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-03-26"}
            self.assertEqual(client.post('/mcp', json=body, headers=headers).status_code, 401)
            headers['Authorization'] = 'Bearer adgm_buyer_' + 'x' * 32
            response = client.post('/mcp', json=body, headers=headers)
            self.assertEqual(response.status_code, 200, response.text)
            payload = next(line[5:].strip() for line in response.text.splitlines() if line.startswith('data:'))
            rpc_result = json.loads(payload)['result']
            self.assertFalse(rpc_result.get('isError'), rpc_result)
            result = rpc_result.get('structuredContent') or json.loads(rpc_result['content'][0]['text'])
            self.assertTrue(result['ok'], result)
            self.assertIn('<svg', result['content'])
            browser_headers = {'X-Firebase-Token': 'firebase-token', 'Authorization': headers['Authorization']}
            with patch('mcp_server.web.verify_browser_identity', return_value=False):
                self.assertEqual(client.post('/api/render', json={'spec': spec}, headers=browser_headers).status_code, 401)
            with patch('mcp_server.web.verify_browser_identity', return_value=True):
                self.assertEqual(client.post('/api/render', json={'spec': spec}, headers={'X-Firebase-Token': 'firebase-token'}).status_code, 401)
                browser_result = client.post('/api/render', json={'spec': spec, 'format': 'svg'}, headers=browser_headers)
                self.assertTrue(browser_result.json()['ok'], browser_result.text)
                self.assertIn('<svg', browser_result.json()['content'])


if __name__ == '__main__':
    unittest.main()
