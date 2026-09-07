"""
@Author         : Xiaji-yu
@Date           : 2026-09-08
@Description    : 图片获取 — 从事件 image 段解析并加载为 base64 data URI

跨机器部署下 NoneBot 无法直接读 NapCat 所在主机的本地文件，
因此以事件自带的 url 下载为主。获取优先级（逐级降级）：
  1. file 为本地路径 / file:// URI（同机部署）→ 读文件
  2. url 可下载 → aiohttp 下载字节
  3. 上述都失败 → 原样返回 url，交由模型云端自行抓取

加载结果统一为 OpenAI 多模态 ``image_url`` 可用的值：
``data:image/...;base64,...`` 或原始 ``http(s)://`` url。
"""

from __future__ import annotations

import asyncio
import base64
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import aiohttp

from .log import logger

# 常见图片扩展名 → MIME
_EXT_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}
# 下载超时
_DOWNLOAD_TIMEOUT = aiohttp.ClientTimeout(total=15)
# 单图大小上限（10MB，防滥用）
_MAX_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class ImageRef:
    """一条 image 段中的可获取信息。"""

    file: str = ""   # OneBot file 字段（可能是文件名、路径或 file://）
    url: str = ""    # OneBot url 字段（可下载地址）

    def has_local_path(self) -> bool:
        """file 是否指向可直接读取的本地路径（file:// 或 /绝对路径）。"""
        if not self.file:
            return False
        if self.file.startswith("file://"):
            return True
        parsed = urlparse(self.file)
        # Windows 盘符（C:\\）或 POSIX 绝对路径，或相对路径存在
        return bool(parsed.scheme == "") and (
            self.file.startswith("/")
            or (len(self.file) >= 3 and self.file[1:3] in (":\\", ":/"))
            or Path(self.file).exists()
        )

    def local_path(self) -> Path:
        """取本地路径（file:// 去除前缀）。"""
        if self.file.startswith("file://"):
            return Path(unquote(self.file[len("file://"):]))
        return Path(self.file)


def extract_images(event: Any) -> list[ImageRef]:
    """从事件消息段中提取所有 image 段。

    Args:
        event: NoneBot MessageEvent。

    Returns:
        ImageRef 列表（无图为空）。
    """
    refs: list[ImageRef] = []
    message = getattr(event, "message", None) or []
    for seg in message:
        stype = getattr(seg, "type", None)
        if isinstance(seg, dict):
            stype = seg.get("type")
        if stype != "image":
            continue
        data = seg.data if hasattr(seg, "data") else (seg.get("data") or {})
        refs.append(ImageRef(file=str(data.get("file", "")), url=str(data.get("url", ""))))
    return refs


async def load_image_data_uri(
    ref: ImageRef, session: aiohttp.ClientSession | None = None,
) -> str | None:
    """将图片加载为 data URI（优先本地路径，其次 url 下载）。

    Args:
        ref: 图片引用。
        session: 可复用的 aiohttp session；None 则临时创建。

    Returns:
        data URI 字符串；完全失败返回 None。
    """
    # 1) 本地路径（同机部署）
    if ref.has_local_path():
        path = ref.local_path()
        try:
            data = path.read_bytes()
            if len(data) > _MAX_BYTES:
                logger.warning(f"[image] 本地图片过大，跳过: {path}")
                return None
            mime = _EXT_MIME.get(path.suffix.lower(), "image/jpeg")
            return _to_data_uri(data, mime)
        except OSError as exc:
            logger.warning(f"[image] 读取本地图片失败 {path}: {exc}")
            # 继续尝试 url

    # 2) url 下载
    if ref.url:
        uri = await _download_to_data_uri(ref.url, session)
        if uri:
            return uri
        # 3) 下载失败 → 原样返回 url（模型云端自抓）
        logger.warning(f"[image] url 下载失败，直传原 url 兜底: {ref.url[:80]}...")
        return ref.url

    return None


async def _download_to_data_uri(
    url: str, session: aiohttp.ClientSession | None = None,
) -> str | None:
    """下载图片并转为 data URI；失败返回 None。"""
    own_session = session is None
    s = session or aiohttp.ClientSession(timeout=_DOWNLOAD_TIMEOUT)
    try:
        resp = await s.get(url)
        async with resp:
            if resp.status != 200:
                logger.warning(f"[image] 下载 HTTP {resp.status}: {url[:80]}...")
                return None
            data = await resp.read()
            if len(data) > _MAX_BYTES:
                logger.warning(f"[image] url 图片过大，跳过: {url[:80]}...")
                return None
            ctype = resp.headers.get("Content-Type", "")
            mime = ctype.split(";")[0] if ctype else _guess_mime(url)
            return _to_data_uri(data, mime)
    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        logger.warning(f"[image] 下载异常: {exc}")
        return None
    finally:
        if own_session and s is not None:
            await s.close()


def _to_data_uri(data: bytes, mime: str) -> str:
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _guess_mime(url: str) -> str:
    path = urlparse(url).path
    ext = Path(path).suffix.lower()
    return _EXT_MIME.get(ext, "image/jpeg")


def _ensure_mime_registered() -> None:
    """为无法识别的扩展名注册默认 MIME（mimetypes 兜底）。"""
    for ext, mime in _EXT_MIME.items():
        if mimetypes.guess_type(f"x{ext}")[0] != mime:
            mimetypes.add_type(mime, ext)


_ensure_mime_registered()
