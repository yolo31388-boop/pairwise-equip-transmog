"""装备幻化与外观收集系统"""
import time
from dataclasses import dataclass, field

RARITY_SCORES = {
    "common": 1,
    "uncommon": 3,
    "rare": 5,
    "epic": 10,
    "legendary": 25,
}

DUPLICATE_POINTS = {
    "common": 1,
    "uncommon": 2,
    "rare": 5,
    "epic": 10,
    "legendary": 20,
}


@dataclass
class Appearance:
    aid: str
    name: str
    slot: str = ""  # weapon/head/chest/legs
    class_restriction: list = field(default_factory=list)
    rarity: str = "common"
    source: str = ""  # 来源：副本/活动/商城等
    owned: bool = False
    expires_at: float = None  # 限时外观过期时间戳，None 表示永久
    acquired_at: float = None  # 获取时间戳

    def is_expired(self, current_time: float = None) -> bool:
        if self.expires_at is None:
            return False
        now = current_time if current_time is not None else time.time()
        return now >= self.expires_at


class TransmogSystem:
    def __init__(self):
        self.appearances: dict[str, Appearance] = {}
        self.equipped_transmog: dict[str, str] = {}  # slot -> aid
        self.preview_slot: dict = {}  # 预览镜像，不触碰实际数据
        self.duplicate_bonus: int = 0  # 重复获取转化的积分

    # ---- bug1: 分类 / 搜索 / 筛选 ----
    def get_appearances_by_slot(self, slot: str) -> list:
        return [a for a in self.appearances.values() if a.slot == slot]

    def get_appearances_by_rarity(self, rarity: str) -> list:
        return [a for a in self.appearances.values() if a.rarity == rarity]

    def search_appearances(self, keyword: str = "", slot: str = None,
                           rarity: str = None, owned_only: bool = False) -> list:
        results = []
        for a in self.appearances.values():
            if keyword and keyword.lower() not in a.name.lower():
                continue
            if slot is not None and a.slot != slot:
                continue
            if rarity is not None and a.rarity != rarity:
                continue
            if owned_only and not a.owned:
                continue
            results.append(a)
        return results

    # ---- bug2: 槽位类型与职业校验 ----
    def can_transmog(self, aid: str, target_slot: str, player_class: str) -> bool:
        app = self.appearances.get(aid)
        if app is None:
            return False
        if app.slot != target_slot:
            return False
        if app.class_restriction and player_class not in app.class_restriction:
            return False
        return True

    # ---- bug3: 按稀有度加权评分 ----
    def get_appearance_score(self) -> int:
        return sum(
            RARITY_SCORES.get(a.rarity, 1)
            for a in self.appearances.values()
            if a.owned
        )

    # ---- bug4: 已拥有标记 + 重复获取转积分 ----
    def mark_owned(self, aid: str, current_time: float = None):
        app = self.appearances.get(aid)
        if app is None:
            return
        if app.owned:
            self.duplicate_bonus += DUPLICATE_POINTS.get(app.rarity, 1)
            return
        app.owned = True
        app.acquired_at = current_time if current_time is not None else time.time()

    # ---- bug5: 预览用临时镜像，不改实际数据 ----
    def apply_preview(self, aid: str, slot: str):
        self.preview_slot[slot] = aid

    def cancel_preview(self, slot: str = None):
        if slot is None:
            self.preview_slot.clear()
        else:
            self.preview_slot.pop(slot, None)

    def confirm_preview(self, slot: str, player_class: str = ""):
        aid = self.preview_slot.get(slot)
        if aid is None:
            return False
        if not self.can_transmog(aid, slot, player_class):
            return False
        self.equipped_transmog[slot] = aid
        self.preview_slot.pop(slot, None)
        return True

    # ---- bug6: 过期外观不可用并自动卸下 ----
    def is_expired_appearance_usable(self, aid: str, current_time: float) -> bool:
        app = self.appearances.get(aid)
        if app is None:
            return False
        return not app.is_expired(current_time)

    def cleanup_expired(self, current_time: float = None) -> list:
        now = current_time if current_time is not None else time.time()
        removed = []
        for slot, aid in list(self.equipped_transmog.items()):
            app = self.appearances.get(aid)
            if app is not None and app.is_expired(now):
                del self.equipped_transmog[slot]
                removed.append(aid)
        return removed

    # ---- bug7: 来源与获取时间溯源 ----
    def get_source(self, aid: str) -> str:
        app = self.appearances.get(aid)
        return app.source if app is not None else ""

    def get_acquired_at(self, aid: str) -> float:
        app = self.appearances.get(aid)
        return app.acquired_at if app is not None else None
