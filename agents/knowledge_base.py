"""知识库隔离加载器。

设计原则：每个 Agent 只能加载属于自己分区（owner_agent）的知识库文件，
目录与文件级别物理隔离，杜绝知识交叉污染。

知识库根目录结构（knowledge/）：
    knowledge/<分区>/<文件>.json

每个 JSON 文件的顶层字段 owner_agent 用于二次校验：当某个分区文件
被错误放置时，加载器会拒绝返回不属于该 Agent 的内容。
"""
from __future__ import annotations

import json
import os
from typing import Any

# 知识库根目录（相对本文件：agents/../knowledge）
KNOWLEDGE_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "knowledge")


class KnowledgeBase:
    """一个 Agent 专属的知识库分区。

    每个实例绑定唯一的 `zone`（分区名）。加载时只扫描该分区的 JSON 文件，
    并通过文件内 owner_agent 字段二次校验归属，防止错放文件被其他 Agent 读到。
    """

    def __init__(self, zone: str):
        if not zone:
            raise ValueError("知识库分区名不能为空")
        self.zone = zone
        self.zone_dir = os.path.join(KNOWLEDGE_ROOT, zone)
        if not os.path.isdir(self.zone_dir):
            raise FileNotFoundError(f"知识库分区不存在: {self.zone_dir}")
        self._data: dict[str, Any] = self._load_zone()

    def _load_zone(self) -> dict[str, Any]:
        """加载当前分区的全部 JSON 文件并合并为一个 dict。"""
        merged: dict[str, Any] = {}
        for fname in sorted(os.listdir(self.zone_dir)):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(self.zone_dir, fname)
            with open(path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            # 归属校验：文件声明的 owner_agent 必须属于当前分区（分区名或 分区名_agent）
            declared = payload.get("owner_agent")
            allowed = {self.zone, f"{self.zone}_agent"}
            if declared and declared not in allowed:
                raise ValueError(
                    f"知识库文件 {path} 归属不匹配：文件声明 owner_agent="
                    f"{declared!r}，但被 {self.zone!r} 加载。已拦截，防止交叉污染。"
                )
            # 将 payload 的顶层语义键（如 products/faq/suppliers）合并进本分区数据，
            # 使 kb.get("products") 等可直接访问。
            merged.update(payload)
        return merged

    def get(self, key: str, default: Any = None) -> Any:
        """从本分区获取某个字段。"""
        return self._data.get(key, default)

    def all(self) -> dict[str, Any]:
        """返回本分区完整数据（只读视图）。"""
        return self._data

    @property
    def meta(self) -> dict[str, Any]:
        """返回本分区元信息（知识库名、归属 Agent、描述）。"""
        return {
            "zone": self.zone,
            "knowledge_name": self.get("knowledge_name"),
            "owner_agent": self.get("owner_agent"),
            "description": self.get("description"),
        }


# 五个角色对应的分区名
ZONE_FAQ = "faq"
ZONE_PRODUCT = "product"
ZONE_PROCUREMENT = "procurement"
ZONE_SUPPLIER = "supplier"
ZONE_ORDER = "order"


def create_all_bases() -> dict[str, KnowledgeBase]:
    """一次性创建 5 个角色各自的隔离知识库。"""
    return {
        ZONE_FAQ: KnowledgeBase(ZONE_FAQ),
        ZONE_PRODUCT: KnowledgeBase(ZONE_PRODUCT),
        ZONE_PROCUREMENT: KnowledgeBase(ZONE_PROCUREMENT),
        ZONE_SUPPLIER: KnowledgeBase(ZONE_SUPPLIER),
        ZONE_ORDER: KnowledgeBase(ZONE_ORDER),
    }
