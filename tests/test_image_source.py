"""
@Author         : Xiaji-yu
@Date           : 2026-09-08
@Description    : 图片获取模块测试
"""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock

import pytest

from chat.image_source import ImageRef, extract_images, load_image_data_uri


class TestExtractImages:
    def test_dict_segments(self) -> None:
        ev = MagicMock()
        ev.message = [
            {"type": "text", "data": {"text": "hi"}},
            {"type": "image", "data": {"file": "a.png", "url": "http://x/a.png"}},
        ]
        refs = extract_images(ev)
        assert len(refs) == 1
        assert refs[0].file == "a.png"
        assert refs[0].url == "http://x/a.png"

    def test_no_images(self) -> None:
        ev = MagicMock()
        ev.message = [{"type": "text", "data": {"text": "hi"}}]
        assert extract_images(ev) == []

    def test_object_segments(self) -> None:
        seg = MagicMock()
        seg.type = "image"
        seg.data = {"file": "b.png", "url": "http://x/b.png"}
        ev = MagicMock()
        ev.message = [seg]
        refs = extract_images(ev)
        assert len(refs) == 1
        assert refs[0].file == "b.png"


class TestImageRefLocalPath:
    def test_file_uri_recognized(self) -> None:
        ref = ImageRef(file="file:///tmp/x.png", url="")
        assert ref.has_local_path() is True
        assert str(ref.local_path()) == "/tmp/x.png"

    def test_plain_filename_not_local(self) -> None:
        """纯文件名（NapCat 缓存名）不视为可直接读的本地路径。"""
        ref = ImageRef(file="D7A93433.png", url="http://x")
        assert ref.has_local_path() is False


class TestLoadImageDataUri:
    @pytest.mark.asyncio
    async def test_loads_local_file(self, tmp_path) -> None:
        p = tmp_path / "pic.png"
        p.write_bytes(b"\x89PNG fake")
        ref = ImageRef(file=str(p), url="")
        uri = await load_image_data_uri(ref)
        assert uri is not None
        assert uri.startswith("data:image/png;base64,")
        # 解码验证内容一致
        payload = uri.split(",", 1)[1]
        assert base64.b64decode(payload) == b"\x89PNG fake"

    @pytest.mark.asyncio
    async def test_downloads_url(self) -> None:
        ref = ImageRef(file="", url="http://img/x.png")
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.headers = {"Content-Type": "image/png"}
        mock_resp.read = AsyncMock(return_value=b"PNGDATA")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        mock_sess = AsyncMock()
        mock_sess.get = AsyncMock(return_value=mock_resp)
        mock_sess.__aenter__ = AsyncMock(return_value=mock_sess)
        mock_sess.__aexit__ = AsyncMock(return_value=False)

        uri = await load_image_data_uri(ref, session=mock_sess)
        assert uri is not None
        assert uri.startswith("data:image/png;base64,")

    @pytest.mark.asyncio
    async def test_download_fail_falls_back_to_raw_url(self) -> None:
        ref = ImageRef(file="", url="http://img/x.png")
        mock_resp = AsyncMock()
        mock_resp.status = 403
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        mock_sess = AsyncMock()
        mock_sess.get = AsyncMock(return_value=mock_resp)
        mock_sess.__aenter__ = AsyncMock(return_value=mock_sess)
        mock_sess.__aexit__ = AsyncMock(return_value=False)

        uri = await load_image_data_uri(ref, session=mock_sess)
        assert uri == "http://img/x.png"

    @pytest.mark.asyncio
    async def test_nothing_available_returns_none(self) -> None:
        ref = ImageRef(file="", url="")
        assert await load_image_data_uri(ref) is None
