import unittest
from unittest.mock import AsyncMock, MagicMock

import tests.hass_mock

from custom_components.hausfunk.go2rtc.client import Go2rtcClient, _encode_src


class TestGo2rtcUrlEncoding(unittest.TestCase):
    def test_fragment_is_encoded(self):
        url = "rtsp://192.168.178.11:8554/tuer#backchannel=1"
        encoded = _encode_src(url)
        self.assertIn("%23backchannel=1", encoded)
        self.assertNotIn("#", encoded)

    def test_scheme_and_path_preserved(self):
        url = "rtsp://192.168.178.11:8554/tuer#backchannel=1"
        encoded = _encode_src(url)
        self.assertTrue(encoded.startswith("rtsp://192.168.178.11:8554/tuer"))
        self.assertIn("%23backchannel", encoded)

    def test_query_params(self):
        url = "rtsp://u:p@192.168.178.11/stream?proto=Onvif&channel=1#backchannel=1"
        encoded = _encode_src(url)
        self.assertNotIn("&", encoded)  # raw & must not break the query string
        self.assertIn("%26", encoded)

    def test_webrtc_go2rtc_url(self):
        url = "webrtc:ws://192.168.178.11:1984/api/ws?src=tuer"
        encoded = _encode_src(url)
        self.assertTrue(encoded.startswith("webrtc:ws://192.168.178.11:1984"))
        self.assertIn("?src=tuer", encoded)


class TestGo2rtcPersistStream(unittest.IsolatedAsyncioTestCase):
    def _client(self, config_text="api:\n  listen: ':1984'\n"):
        client = Go2rtcClient(url="http://localhost:11984")
        session = MagicMock()
        responses = {
            ("GET", "/api/config"): config_text,
            ("POST", "/api/config"): "ok",
        }
        calls = []

        async def fake_request(method, path, params=None, data=None, content_type=None):
            calls.append((method, path, params, data, content_type))
            if (method, path) == ("POST", "/api/config"):
                self._posted = data
                return "ok"
            return responses[(method, path)]

        client.ensure_session = AsyncMock()
        client._request = fake_request
        return client, calls

    async def test_persist_stream_adds_preload_and_webrtc(self):
        client, calls = self._client()
        await client.persist_stream(
            "tuer",
            ["webrtc:ws://192.168.178.11:1984/api/ws?src=tuer"],
            webrtc_port=8555,
            candidates="sprechanlage.moers.webredirect.org:8555, 192.168.178.99:8555",
        )
        import yaml
        data = yaml.safe_load(self._posted)
        self.assertEqual(
            data["streams"]["tuer"],
            ["webrtc:ws://192.168.178.11:1984/api/ws?src=tuer"],
        )
        self.assertEqual(data["preload"]["tuer"], "video&audio")
        self.assertEqual(data["webrtc"]["listen"], ":8555")
        self.assertEqual(
            data["webrtc"]["candidates"],
            ["sprechanlage.moers.webredirect.org:8555", "192.168.178.99:8555"],
        )
        # existing sections preserved
        self.assertEqual(data["api"]["listen"], ":1984")

    async def test_persist_stream_fills_default_ports_when_missing(self):
        # empty config -> api/rtsp/webrtc listen defaults are filled in
        client, calls = self._client(config_text="streams: {}\n")
        await client.persist_stream(
            "tuer", ["webrtc:ws://192.168.178.11:1984/api/ws?src=tuer"]
        )
        import yaml
        data = yaml.safe_load(self._posted)
        self.assertEqual(data["api"]["listen"], ":1984")
        self.assertEqual(data["rtsp"]["listen"], ":8554")
        self.assertEqual(data["webrtc"]["listen"], ":8555")
        self.assertEqual(data["preload"]["tuer"], "video&audio")

    async def test_persist_stream_keeps_custom_ports(self):
        # existing custom ports survive the merge
        client, calls = self._client(
            config_text="rtsp:\n  listen: ':9000'\nstreams: {}\n"
        )
        await client.persist_stream("tuer", ["webrtc:ws://192.168.178.11:1984/api/ws?src=tuer"])
        import yaml
        data = yaml.safe_load(self._posted)
        self.assertEqual(data["rtsp"]["listen"], ":9000")

    async def test_persist_stream_skips_webrtc_when_not_configured(self):
        client, calls = self._client()
        await client.persist_stream("tuer", ["webrtc:ws://192.168.178.11:1984/api/ws?src=tuer"])
        import yaml
        data = yaml.safe_load(self._posted)
        # webrtc section is still filled with the default listen
        self.assertEqual(data["webrtc"]["listen"], ":8555")
        self.assertNotIn("candidates", data.get("webrtc", {}))
        self.assertEqual(data["preload"]["tuer"], "video&audio")

    async def test_restart(self):
        client, calls = self._client()
        client._request = AsyncMock(return_value="ok")
        await client.restart()
        client._request.assert_called_once()


if __name__ == "__main__":
    unittest.main()
