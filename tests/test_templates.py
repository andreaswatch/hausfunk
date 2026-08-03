import unittest

import tests.hass_mock

from custom_components.hausfunk.pi.installer import _render


class TestTemplateRender(unittest.TestCase):
    def test_go2rtc_yaml_rendered(self):
        out = _render("go2rtc.yaml.j2", {
            "pi_go2rtc_port": 1984,
            "rtsp_port": 8554,
            "stream_name": "tuer",
            "width": 320,
            "height": 240,
            "fps": 10,
            "audio_gain": 2.0,
            "webrtc_section": "",
        })
        self.assertIn('api:\n  listen: ":1984"', out)
        self.assertIn('listen: ":8554"', out)
        self.assertIn("rpicam-vid -t 0 --inline --width 320 --height 240 --framerate 10", out)
        # go2rtc {output} placeholder must survive rendering
        self.assertIn("-f rtsp {output}#exec=always", out)
        self.assertIn("#backchannel=1#audio=alaw/8000", out)
        self.assertNotIn("webrtc:", out)
        self.assertNotIn("{{", out)

    def test_go2rtc_yaml_rendered_with_webrtc_section(self):
        out = _render("go2rtc.yaml.j2", {
            "pi_go2rtc_port": 1984,
            "rtsp_port": 8554,
            "stream_name": "tuer",
            "width": 320,
            "height": 240,
            "fps": 10,
            "audio_gain": 2.0,
            "webrtc_section": (
                "\nwebrtc:\n"
                "  listen: \":8555\"\n"
                "  candidates:\n"
                "    - 192.168.178.11:8555\n"
            ),
        })
        self.assertIn("webrtc:\n  listen: \":8555\"", out)
        self.assertIn("candidates:\n    - 192.168.178.11:8555", out)
        self.assertNotIn("{{", out)

    def test_service_template_rendered(self):
        out = _render("hausfunk-pi.service.j2", {
            "binary_path": "/home/andreas/hausfunk/go2rtc",
            "config_path": "/home/andreas/hausfunk/go2rtc.yaml",
            "pi_user": "andreas",
            "uid": "1000",
        })
        self.assertIn("ExecStart=/home/andreas/hausfunk/go2rtc -config /home/andreas/hausfunk/go2rtc.yaml", out)
        self.assertNotIn("User=", out)  # User-Service, kein User= nötig
        self.assertIn("WantedBy=default.target", out)
        self.assertIn("Environment=PULSE_SERVER=unix:/run/user/1000/pulse/native", out)
        self.assertNotIn("{{", out)


if __name__ == "__main__":
    unittest.main()
