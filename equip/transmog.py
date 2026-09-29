"""装备幻化与外观收集系统 - 含7个bug"""
from dataclasses import dataclass, field

@dataclass
class Appearance:
    aid: str
    name: str
    slot: str  # weapon/head/chest/legs
    class_restriction: list = field(default_factory=list)
    rarity: str = "common"
    source: str = ""
    owned: bool = False

class TransmogSystem:
    def __init__(self):
        self.appearances: dict[str, Appearance] = {}
        self.equipped_transmog: dict[str, str] = {}  # slot -> aid
        self.preview_active: dict = {}  # bug5: 预览改实际数据

    def get_appearances_by_slot(self, slot: str) -> list:
        # bug1: 不分类
        return list(self.appearances.values())

    def can_transmog(self, aid: str, target_slot: str, player_class: str) -> bool:
        # bug2: 不检查类型和职业
        return aid in self.appearances

    def get_appearance_score(self) -> int:
        # bug3: 按数量不按稀有度
        return sum(1 for a in self.appearances.values() if a.owned)

    def mark_owned(self, aid: str):
        # bug4: 已拥有无标记
        if aid in self.appearances:
            self.appearances[aid].owned = True

    def apply_preview(self, aid: str, slot: str):
        # bug5: 预览改实际数据
        self.equipped_transmog[slot] = aid

    def is_expired_appearance_usable(self, aid: str, current_time: float) -> bool:
        # bug6: 过期还能用
        return True

    def get_source(self, aid: str) -> str:
        # bug7: 无来源记录
        return ""
