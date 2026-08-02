import unittest

import tests.hass_mock

from custom_components.hausfunk.pi.installer import _render


class TestTemplateRender(unittest.TestCase):
    def test_go2rtc_yaml_rendered(self):
        out = _render("go2rtc.yaml.j2", {
            "rtsp_port": 8554,
            "stream_name": "tuer",
            "width": 320,
            "height": 240,
            "fps": 10,
            "audio_gain": 2.0,
        })
        self.assertIn('listen: ":8554"', out)
        self.assertIn("rpicam-vid -t 0 --inline --width 320 --height 240 --framerate 10", out)
        # go2rtc {output} placeholder must survive rendering
        self.assertIn("-f rtsp {output}#exec=always", out)
        self.assertIn("#backchannel=1#audio=alaw/8000", out)
        self.assertNotIn("{{", out)

    def test_service_template_rendered(self):
        out = _render("hausfunk-pi.service.j2", {
            "binary_path": "/usr/local/bin/go2rtc",
            "config_path": "/etc/hausfunk/go2rtc.yaml",
            "pi_user": "andreas",
            "uid": "1000",
        })
        self.assertIn("ExecStart=/usr/local/bin/go2rtc -config /etc/hausfunk/go2rtc.yaml", out)
        self.assertIn("User=andreas", out)
        self.assertIn("SupplementaryGroups=video", out)
        self.assertIn("Environment=PULSE_SERVER=unix:/run/user/1000/pulse/native", out)
        self.assertNotIn("{{", out)


if __name__ == "__main__":
    unittest.main()
