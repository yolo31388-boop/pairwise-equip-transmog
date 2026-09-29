"""装备幻化与外观收集系统

修复点:
1. 外观按 部位(slot)/类型(appearance_type)/稀有度(rarity) 分类, 支持搜索筛选
2. 幻化校验槽位、装备类型(布甲/板甲等)与职业限制
3. 评分按稀有度加权, 传说外观远高于普通
4. 已拥有明确标记, 重复获取自动转化为积分
5. 预览使用临时镜像, 不修改实际幻化数据, 取消即恢复
6. 限时外观过期后自动卸下并标记不可用, 快捷键也无法幻化
7. 记录来源(副本/活动/商城)与获取时间, 支持溯源
"""
from dataclasses import dataclass, field
from time import time

# 稀有度权重: 越稀有分数越高
RARITY_WEIGHTS = {
    "common": 1,
    "uncommon": 5,
    "rare": 10,
    "epic": 25,
    "legendary": 50,
}

# 来源大类: dungeon=副本, event=活动, shop=商城, other=其他
SOURCE_CATEGORIES = ("dungeon", "event", "shop", "other")


@dataclass
class Appearance:
    aid: str
    name: str
    slot: str = ""                       # 部位: weapon/head/chest/legs/...
    appearance_type: str = ""            # 装备类型: cloth/leather/mail/plate/...
    class_restriction: list = field(default_factory=list)
    rarity: str = "common"
    source: str = ""                     # 具体来源, 如 raid_boss / summer_event / cash_shop
    source_category: str = ""            # 来源大类: dungeon/event/shop
    owned: bool = False
    expires_at: float | None = None      # 限时外观过期时间戳, None 表示永久
    obtained_at: float | None = None     # 获取时间戳
    expired: bool = False                # 过期后标记为不可用

    def is_expired(self, current_time: float) -> bool:
        return self.expires_at is not None and current_time >= self.expires_at

    def is_usable(self, current_time: float | None = None) -> bool:
        if self.expired:
            return False
        if current_time is not None and self.is_expired(current_time):
            return False
        return True


class TransmogSystem:
    def __init__(self):
        self.appearances: dict[str, Appearance] = {}
        self.equipped_transmog: dict[str, str] = {}   # slot -> aid (实际幻化)
        # 预览临时镜像, 与 equipped_transmog 隔离
        self.preview_transmog: dict[str, str] = {}
        self.preview_slot: str | None = None
        # 重复获取转化的积分
        self.duplicate_bonus: int = 0
        self.duplicate_records: dict[str, int] = {}

    # ---- 1. 分类 / 搜索 / 筛选 ----------------------------------------------

    def get_appearances_by_slot(self, slot: str) -> list[Appearance]:
        return [a for a in self.appearances.values() if a.slot == slot]

    def get_appearances_by_type(self, appearance_type: str) -> list[Appearance]:
        return [a for a in self.appearances.values()
                if a.appearance_type == appearance_type]

    def get_appearances_by_rarity(self, rarity: str) -> list[Appearance]:
        return [a for a in self.appearances.values() if a.rarity == rarity]

    def get_categories(self) -> dict[str, dict[str, list[Appearance]]]:
        """按 部位 -> 稀有度 两级分类浏览。"""
        tree: dict[str, dict[str, list[Appearance]]] = {}
        for appearance in self.appearances.values():
            tree.setdefault(appearance.slot, {}).setdefault(
                appearance.rarity, []
            ).append(appearance)
        return tree

    def search_appearances(self, keyword: str = "", *, slot: str | None = None,
                           appearance_type: str | None = None,
                           rarity: str | None = None,
                           owned_only: bool = False) -> list[Appearance]:
        """按关键字(名称/ID)搜索, 并可叠加部位/类型/稀有度/已拥有筛选。"""
        keyword = (keyword or "").strip().lower()
        result = []
        for appearance in self.appearances.values():
            if keyword and keyword not in appearance.name.lower() \
                    and keyword not in appearance.aid.lower():
                continue
            if slot is not None and appearance.slot != slot:
                continue
            if appearance_type is not None and appearance.appearance_type != appearance_type:
                continue
            if rarity is not None and appearance.rarity != rarity:
                continue
            if owned_only and not appearance.owned:
                continue
            result.append(appearance)
        return result

    # ---- 2. 幻化校验 --------------------------------------------------------

    def can_transmog(self, aid: str, target_slot: str, player_class: str,
                     target_type: str | None = None,
                     current_time: float | None = None) -> bool:
        appearance = self.appearances.get(aid)
        if appearance is None:
            return False
        # 槽位必须一致(武器不能幻化到防具槽)
        if appearance.slot != target_slot:
            return False
        # 装备类型必须一致(布甲不能幻化成板甲)
        if target_type is not None and appearance.appearance_type \
                and appearance.appearance_type != target_type:
            return False
        # 职业限制
        if appearance.class_restriction \
                and player_class not in appearance.class_restriction:
            return False
        # 限时外观过期后不可用
        if not appearance.is_usable(current_time):
            return False
        return True

    def apply_transmog(self, aid: str, target_slot: str, player_class: str,
                       target_type: str | None = None,
                       current_time: float | None = None) -> bool:
        """实际幻化: 校验通过才写入幻化槽。"""
        if not self.can_transmog(aid, target_slot, player_class,
                                 target_type, current_time):
            return False
        self.equipped_transmog[target_slot] = aid
        return True

    def quick_transmog(self, aid: str, player_class: str,
                       current_time: float | None = None) -> bool:
        """快捷键幻化: 依据外观自身槽位进行, 过期外观一律拒绝。"""
        appearance = self.appearances.get(aid)
        if appearance is None:
            return False
        return self.apply_transmog(
            aid, appearance.slot, player_class,
            appearance.appearance_type or None, current_time,
        )

    def unequip(self, slot: str) -> bool:
        return self.equipped_transmog.pop(slot, None) is not None

    # ---- 3. 稀有度加权评分 --------------------------------------------------

    def get_appearance_score(self) -> int:
        return sum(RARITY_WEIGHTS.get(a.rarity, 0)
                   for a in self.appearances.values() if a.owned)

    # ---- 4. 拥有标记 / 重复获取转积分 ---------------------------------------

    def mark_owned(self, aid: str, source: str | None = None,
                   source_category: str | None = None,
                   obtained_at: float | None = None) -> str:
        """标记已拥有; 重复获取自动按稀有度转化为积分。

        返回 "owned"(新获取) 或 "duplicate"(重复转化)。
        """
        appearance = self.appearances.get(aid)
        if appearance is None:
            raise KeyError(f"unknown appearance: {aid}")
        if appearance.owned:
            points = RARITY_WEIGHTS.get(appearance.rarity, 1)
            self.duplicate_bonus += points
            self.duplicate_records[aid] = self.duplicate_records.get(aid, 0) + 1
            return "duplicate"
        appearance.owned = True
        appearance.obtained_at = obtained_at if obtained_at is not None else time()
        if source is not None:
            appearance.source = source
        if source_category is not None:
            appearance.source_category = source_category
        return "owned"

    # ---- 5. 预览镜像 --------------------------------------------------------

    def apply_preview(self, aid: str, slot: str) -> None:
        """开启预览: 只写临时镜像, 实际幻化数据不变。"""
        self.preview_transmog[slot] = aid
        self.preview_slot = slot

    def cancel_preview(self) -> None:
        """取消预览: 清空镜像, 实际外观保持不变。"""
        self.preview_transmog.clear()
        self.preview_slot = None

    def confirm_preview(self, player_class: str,
                        current_time: float | None = None) -> bool:
        """确认预览: 逐项校验通过后才提交到实际幻化槽。"""
        pending = dict(self.preview_transmog)
        for slot, aid in pending.items():
            appearance = self.appearances.get(aid)
            target_type = appearance.appearance_type if appearance else None
            if not self.can_transmog(aid, slot, player_class,
                                     target_type or None, current_time):
                return False
        self.equipped_transmog.update(pending)
        self.cancel_preview()
        return True

    def get_preview(self, slot: str) -> str | None:
        return self.preview_transmog.get(slot)

    # ---- 6. 限时外观过期 ----------------------------------------------------

    def is_expired_appearance_usable(self, aid: str, current_time: float) -> bool:
        appearance = self.appearances.get(aid)
        if appearance is None:
            return False
        return appearance.is_usable(current_time)

    def sweep_expired(self, current_time: float) -> list[str]:
        """过期外观自动从幻化槽卸下并标记不可用, 返回被清理的 aid 列表。"""
        removed = []
        for aid, appearance in self.appearances.items():
            # 已拥有或正装备在幻化槽中的外观过期后都要处理
            equipped = aid in self.equipped_transmog.values()
            if (appearance.owned or equipped) and not appearance.expired \
                    and appearance.is_expired(current_time):
                appearance.expired = True
                removed.append(aid)
        for aid in removed:
            for slot in [s for s, equipped in self.equipped_transmog.items()
                         if equipped == aid]:
                del self.equipped_transmog[slot]
        return removed

    # ---- 7. 来源溯源 --------------------------------------------------------

    def get_source(self, aid: str) -> str:
        appearance = self.appearances.get(aid)
        return appearance.source if appearance else ""

    def get_source_info(self, aid: str) -> dict:
        """返回来源详情: 具体来源/来源大类/获取时间, 便于溯源。"""
        appearance = self.appearances.get(aid)
        if appearance is None:
            return {}
        return {
            "aid": appearance.aid,
            "name": appearance.name,
            "source": appearance.source,
            "source_category": appearance.source_category,
            "obtained_at": appearance.obtained_at,
        }

    def get_obtained_time(self, aid: str) -> float | None:
        appearance = self.appearances.get(aid)
        return appearance.obtained_at if appearance else None
