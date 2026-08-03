"""Client for the go2rtc HTTP API on the Home Assistant host."""

import json
import logging
from urllib.parse import quote

import aiohttp
import yaml

from ..const import DEFAULT_GO2RTC_URL, DEFAULT_GO2RTC_WEBRTC_PORT

_LOGGER = logging.getLogger(__name__)

_SAFE = ":/?=@%.+-_~"


def _encode_src(src: str) -> str:
    """Percent-encode a stream URL for use as query value (# -> %23 etc.)."""
    return quote(src, safe=_SAFE)


class Go2rtcError(Exception):
    """Raised when the go2rtc API returns an error."""


class Go2rtcClient:
    """Thin client for the go2rtc stream/config API."""

    def __init__(self, url=DEFAULT_GO2RTC_URL, username=None, password=None):
        self.url = url.rstrip("/")
        self.username = username
        self.password = password
        self._session: aiohttp.ClientSession | None = None

    async def _request(self, method, path, params=None, data=None, content_type=None):
        headers = {}
        if data is not None:
            headers["Content-Type"] = content_type or "application/json"
        auth = (
            aiohttp.BasicAuth(self.username, self.password)
            if self.username
            else None
        )
        try:
            async with self._session.request(
                method, f"{self.url}{path}", params=params, data=data,
                headers=headers, auth=auth, timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status >= 400:
                    raise Go2rtcError(
                        f"go2rtc {method} {path} -> {resp.status}: {await resp.text()}"
                    )
                return await resp.text()
        except aiohttp.ClientError as err:
            await self.close()
            raise Go2rtcError(f"go2rtc nicht erreichbar: {err}") from err

    async def ensure_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    async def close(self):
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    async def get_streams(self) -> dict:
        """Return all currently known streams."""
        await self.ensure_session()
        text = await self._request("GET", "/api/streams")
        return json.loads(text)

    async def stream_exists(self, name: str) -> bool:
        streams = await self.get_streams()
        return name in streams

    async def ensure_stream(self, name: str, urls: list[str]):
        """Create or update a stream so it exists in go2rtc."""
        await self.ensure_session()
        params = [("name", name)] + [("src", u) for u in urls]
        if await self.stream_exists(name):
            await self._request("PATCH", "/api/streams", params=params)
        else:
            await self._request("PUT", "/api/streams", params=params)

    async def remove_stream(self, name: str):
        """Delete a stream from go2rtc."""
        await self.ensure_session()
        if await self.stream_exists(name):
            await self._request("DELETE", "/api/streams", params={"name": name})

    async def restart(self):
        """Restart the go2rtc process to apply config changes."""
        await self.ensure_session()
        await self._request("POST", "/api/restart")

    async def persist_stream(
        self,
        name: str,
        urls: list[str],
        webrtc_port: int | None = None,
        candidates: str | None = None,
    ):
        """Merge the stream into go2rtc's config file so it survives restarts.

        Reads the current config, merges the stream (and, when configured, the
        ``preload`` and ``webrtc`` sections) into it and writes it back.
        ``api``/``rtsp`` listen ports are only added if missing, so existing
        custom ports are preserved. Other streams are never touched (unlike
        go2rtc's clobber-prone PATCH /api/config merge semantics).
        """
        await self.ensure_session()
        text = await self._request("GET", "/api/config")
        data = yaml.safe_load(text) or {}
        streams = data.setdefault("streams", {})
        streams[name] = list(urls)
        preload = data.setdefault("preload", {})
        preload[name] = "video&audio"
        # Only fill in defaults when the sections/keys are missing, so a
        # user's existing custom ports survive the merge.
        data.setdefault("api", {}).setdefault("listen", ":1984")
        data.setdefault("rtsp", {}).setdefault("listen", ":8554")
        webrtc = data.setdefault("webrtc", {})
        webrtc.setdefault("listen", f":{webrtc_port or 8555}")
        if candidates:
            entries = [c.strip() for c in candidates.split(",") if c.strip()]
            if entries:
                webrtc["candidates"] = entries
        body = yaml.safe_dump(data, default_flow_style=False, sort_keys=False)
        await self._request(
            "POST", "/api/config", data=body, content_type="application/yaml"
        )
