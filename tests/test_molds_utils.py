import pytest

from nullforge.models.dns import DnsMode
from nullforge.molds import DnsMold, FeaturesMold, NetSecMold, ProfilesMold, SystemMold, UserMold, WarpMold
from nullforge.molds.features import iter_runes
from nullforge.molds.utils import (
    _deep_merge_dicts,
    ensure_features,
    ensure_system,
    merge_features,
    merge_system,
)


class TestDeepMergeDicts:
    def test_simple_override(self) -> None:
        assert _deep_merge_dicts({"a": 1}, {"a": 2}) == {"a": 2}

    def test_new_key(self) -> None:
        assert _deep_merge_dicts({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}

    def test_nested_merge(self) -> None:
        a = {"x": {"a": 1, "b": 2}}
        b = {"x": {"b": 3, "c": 4}}
        assert _deep_merge_dicts(a, b) == {"x": {"a": 1, "b": 3, "c": 4}}

    def test_none_in_b_overwrites(self) -> None:
        assert _deep_merge_dicts({"a": 1}, {"a": None}) == {"a": None}

    def test_does_not_mutate_a(self) -> None:
        a = {"x": {"y": 1}}
        _deep_merge_dicts(a, {"x": {"z": 2}})
        assert a == {"x": {"y": 1}}

    def test_empty_b(self) -> None:
        assert _deep_merge_dicts({"a": 1}, {}) == {"a": 1}

    def test_empty_a(self) -> None:
        assert _deep_merge_dicts({}, {"a": 1}) == {"a": 1}


class TestMergeFeatures:
    def test_none_layer_is_ignored(self) -> None:
        base = FeaturesMold()
        result = merge_features(base, None)
        assert result == base

    def test_sub_mold_overrides_field(self) -> None:
        base = FeaturesMold()
        dns = DnsMold(mode=DnsMode.NONE)
        result = merge_features(base, dns)
        assert result.dns.mode == DnsMode.NONE

    def test_multiple_layers_applied_in_order(self) -> None:
        base = FeaturesMold()
        dns1 = DnsMold(mode=DnsMode.BLOCKY)
        dns2 = DnsMold(mode=DnsMode.DOT_RESOLVED)
        result = merge_features(base, dns1, dns2)
        assert result.dns.mode == DnsMode.DOT_RESOLVED

    def test_unsupported_type_raises(self) -> None:
        base = FeaturesMold()
        with pytest.raises(TypeError):
            merge_features(base, 42)

    def test_non_feature_base_mold_raises(self) -> None:
        base = FeaturesMold()
        with pytest.raises(TypeError, match="Unsupported features layer type"):
            merge_features(base, SystemMold())


class TestEnsureFeatures:
    def test_none_returns_default(self) -> None:
        assert isinstance(ensure_features(None), FeaturesMold)

    def test_passthrough_features_mold(self) -> None:
        f = FeaturesMold()
        assert ensure_features(f) is f

    def test_dict_coerced(self) -> None:
        result = ensure_features({})
        assert isinstance(result, FeaturesMold)

    def test_unsupported_type_raises(self) -> None:
        with pytest.raises(TypeError):
            ensure_features(123)


class TestMergeSystem:
    def test_none_layer_is_ignored(self) -> None:
        base = SystemMold()
        assert merge_system(base, None) == base

    def test_dict_layer_overrides(self) -> None:
        base = SystemMold()
        result = merge_system(base, {"hostname": "myserver.example.com"})
        assert result.hostname == "myserver.example.com"

    def test_system_mold_layer(self) -> None:
        base = SystemMold()
        overlay = SystemMold(hostname="overlay.example.com")
        result = merge_system(base, overlay)
        assert result.hostname == "overlay.example.com"


class TestEnsureSystem:
    def test_none_returns_default(self) -> None:
        assert isinstance(ensure_system(None), SystemMold)

    def test_passthrough_system_mold(self) -> None:
        s = SystemMold()
        assert ensure_system(s) is s

    def test_dict_coerced(self) -> None:
        result = ensure_system({})
        assert isinstance(result, SystemMold)

    def test_unsupported_type_raises(self) -> None:
        with pytest.raises(TypeError):
            ensure_system(42)


def _active(features: FeaturesMold) -> list[str]:
    return [name for name, active in iter_runes(features) if active]


class TestIterRunes:
    def test_order_and_membership_do_not_depend_on_activation(self) -> None:
        bare = [name for name, _ in iter_runes(FeaturesMold())]
        loaded = [
            name
            for name, _ in iter_runes(
                FeaturesMold(
                    warp=WarpMold(install=True),
                ),
            )
        ]

        assert bare == loaded
        assert len(bare) == len(set(bare))

    def test_defaults_activate_dns_users_netsec_profiles(self) -> None:
        f = FeaturesMold()
        names = _active(f)
        assert "dns" in names
        assert "users" in names
        assert "netsec" in names
        assert "profiles" in names
        # install=False by default are inactive
        assert "warp" not in names
        assert "monitoring" not in names

    def test_dns_none_deactivates(self) -> None:
        f = FeaturesMold(dns=DnsMold(mode=DnsMode.NONE))
        assert "dns" not in _active(f)

    def test_profiles_compound_activation(self) -> None:
        f = FeaturesMold(profiles=ProfilesMold(for_root=False, for_user=False))
        assert "profiles" not in _active(f)

        f2 = FeaturesMold(profiles=ProfilesMold(for_root=False, for_user=True))
        assert "profiles" in _active(f2)

    def test_users_manage_flag(self) -> None:
        f = FeaturesMold(users=UserMold(manage=False))
        assert "users" not in _active(f)

    def test_active_install_flag(self) -> None:
        f = FeaturesMold(warp=WarpMold(install=True))
        assert "warp" in _active(f)

    def test_netsec_can_be_disabled(self) -> None:
        f = FeaturesMold(netsec=NetSecMold(install=False))
        assert "netsec" not in _active(f)

        f2 = FeaturesMold()  # default install=True
        assert "netsec" in _active(f2)
