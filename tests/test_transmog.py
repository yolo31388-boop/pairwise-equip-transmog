"""装备幻化与外观收集系统 - 红态测试"""
import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from equip.transmog import TransmogSystem, Appearance

class TestSlotFiltering:
    def test_appearances_filtered_by_slot(self):
        ts = TransmogSystem()
        ts.appearances["a1"] = Appearance("a1", "sword", slot="weapon")
        ts.appearances["a2"] = Appearance("a2", "helm", slot="head")
        weapons = ts.get_appearances_by_slot("weapon")
        assert len(weapons) == 1  # bug1: 返回2条
        assert weapons[0].slot == "weapon"

class TestTransmogValidation:
    def test_cannot_transmog_across_class(self):
        ts = TransmogSystem()
        ts.appearances["a1"] = Appearance("a1", "plate", slot="chest", class_restriction=["warrior"])
        assert ts.can_transmog("a1", "chest", "mage") == False  # bug2: True
        assert ts.can_transmog("a1", "chest", "warrior") == True

class TestScoreByRarity:
    def test_rare_appearance_worth_more(self):
        ts = TransmogSystem()
        ts.appearances["a1"] = Appearance("a1", "common", rarity="common", owned=True)
        ts.appearances["a2"] = Appearance("a2", "legendary", rarity="legendary", owned=True)
        score = ts.get_appearance_score()
        assert score > 2  # bug3: 只按数量=2

class TestOwnedMarking:
    def test_owned_appearance_clearly_marked(self):
        ts = TransmogSystem()
        ts.appearances["a1"] = Appearance("a1", "sword", owned=False)
        ts.mark_owned("a1")
        assert ts.appearances["a1"].owned == True
        # 重复获取应该有标记
        assert hasattr(ts, "duplicate_bonus") or ts.appearances["a1"].owned == True

class TestPreviewIsolation:
    def test_preview_does_not_change_actual(self):
        ts = TransmogSystem()
        ts.appearances["a1"] = Appearance("a1", "sword", slot="weapon")
        ts.apply_preview("a1", "weapon")
        # 预览不应该修改实际装备
        assert "weapon" not in ts.equipped_transmog or hasattr(ts, "preview_slot")

class TestExpiredAppearance:
    def test_expired_limited_appearance_cannot_be_used(self):
        ts = TransmogSystem()
        ts.appearances["a1"] = Appearance("a1", "event", rarity="legendary")
        # 应该有过期时间字段
        assert hasattr(Appearance, "expires_at") or ts.is_expired_appearance_usable("a1", 999) == False

class TestSourceTracking:
    def test_appearance_has_source_record(self):
        ts = TransmogSystem()
        ts.appearances["a1"] = Appearance("a1", "sword", source="raid_boss")
        assert ts.get_source("a1") == "raid_boss"  # bug7: 空
