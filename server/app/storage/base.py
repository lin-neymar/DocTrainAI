"""文件存储后端抽象：业务只认 storage_key，不认绝对路径或桶 URL。"""

from __future__ import annotations

from abc import ABC, abstractmethod


class StorageBackend(ABC):
    """阶段 1 仅 Local 实现；阶段 2+ 可增 S3 兼容实现。"""

    @abstractmethod
    def put(self, storage_key: str, content: bytes) -> None:
        """写入对象；storage_key 由调用方生成（相对键，禁止 ..）。"""

    @abstractmethod
    def read(self, storage_key: str) -> bytes:
        """读取全部字节；不存在则由实现抛出合适异常。"""

    @abstractmethod
    def delete(self, storage_key: str) -> None:
        """删除对象；不存在时视为成功。"""

    @abstractmethod
    def exists(self, storage_key: str) -> bool:
        """对象是否存在。"""
