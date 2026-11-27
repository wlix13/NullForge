from unittest.mock import patch

import pytest

from nullforge.smithy import github


@pytest.fixture(autouse=True)
def _clear_release_cache() -> None:
    github._RELEASE_CACHE.clear()


SHA_A = "a" * 64
SHA_B = "b" * 64


def _release(assets: list[dict]) -> dict:
    return {"tag_name": "v1.0.0", "assets": assets}


class TestParseDownloadUrl:
    def test_tagged_url(self) -> None:
        url = "https://github.com/telemt/telemt/releases/download/3.4.23/telemt-x86_64-linux-gnu.tar.gz"
        assert github.parse_download_url(url) == ("telemt/telemt", "3.4.23", "telemt-x86_64-linux-gnu.tar.gz")

    def test_latest_url(self) -> None:
        url = "https://github.com/direnv/direnv/releases/latest/download/direnv.linux-amd64"
        assert github.parse_download_url(url) == ("direnv/direnv", "latest", "direnv.linux-amd64")

    def test_non_release_url_returns_none(self) -> None:
        assert github.parse_download_url("https://example.com/foo/bar.tar.gz") is None


class TestAssetSha256:
    def test_prefers_api_digest(self) -> None:
        release = _release([{"name": "tool.tar.gz", "digest": f"sha256:{SHA_A}"}])
        assert github.asset_sha256(release, "tool.tar.gz") == SHA_A

    def test_ignores_malformed_digest(self) -> None:
        release = _release([{"name": "tool.tar.gz", "digest": "sha256:nothex"}])
        with patch.object(github, "fetch_text", side_effect=AssertionError("should not fetch")):
            assert github.asset_sha256(release, "tool.tar.gz") is None

    def test_falls_back_to_manifest(self) -> None:
        release = _release(
            [
                {"name": "tool.tar.gz", "browser_download_url": "https://x/tool.tar.gz"},
                {"name": "checksums.txt", "browser_download_url": "https://x/checksums.txt"},
            ]
        )
        body = f"{SHA_B}  tool.tar.gz\n{SHA_A}  other.tar.gz\n"
        with patch.object(github, "fetch_text", return_value=body) as fetched:
            assert github.asset_sha256(release, "tool.tar.gz") == SHA_B
        fetched.assert_called_once_with("https://x/checksums.txt")

    def test_per_asset_sha256_file(self) -> None:
        release = _release(
            [
                {"name": "tool.tar.gz", "browser_download_url": "https://x/tool.tar.gz"},
                {"name": "tool.tar.gz.sha256", "browser_download_url": "https://x/tool.tar.gz.sha256"},
            ]
        )
        with patch.object(github, "fetch_text", return_value=f"{SHA_A}\n"):
            assert github.asset_sha256(release, "tool.tar.gz") == SHA_A

    def test_no_checksum_available(self) -> None:
        release = _release([{"name": "tool.tar.gz"}])
        assert github.asset_sha256(release, "tool.tar.gz") is None


class TestParseChecksums:
    def test_star_prefixed_binary_mode(self) -> None:
        assert github._parse_checksums(f"{SHA_A} *tool.tar.gz\n", "tool.tar.gz") == SHA_A

    def test_matches_basename_only(self) -> None:
        assert github._parse_checksums(f"{SHA_A}  ./dist/tool.tar.gz\n", "tool.tar.gz") == SHA_A

    def test_lone_hash_is_fallback(self) -> None:
        assert github._parse_checksums(f"  {SHA_A}  \n", "tool.tar.gz") == SHA_A

    def test_named_line_wins_over_wrong_name(self) -> None:
        body = f"{SHA_A}  other\n{SHA_B}  tool\n"
        assert github._parse_checksums(body, "tool") == SHA_B


class TestSha256ForDownloadUrl:
    def test_resolves_end_to_end(self) -> None:
        url = "https://github.com/o/r/releases/download/v1/tool.tar.gz"
        release = _release([{"name": "tool.tar.gz", "digest": f"sha256:{SHA_A}"}])
        with patch.object(github, "fetch_release", return_value=release) as fr:
            assert github.sha256_for_download_url(url) == SHA_A
        fr.assert_called_once_with("o/r", "v1")

    def test_unparseable_url_returns_none(self) -> None:
        assert github.sha256_for_download_url("https://example.com/x") is None

    def test_missing_release_returns_none(self) -> None:
        url = "https://github.com/o/r/releases/download/v1/tool.tar.gz"
        with patch.object(github, "fetch_release", return_value=None):
            assert github.sha256_for_download_url(url) is None


class TestSelectAsset:
    def _sample(self) -> dict:
        return _release(
            [
                {"name": "tool-linux-x86_64-gnu.tar.gz"},
                {"name": "tool-linux-x86_64-musl.tar.gz"},
                {"name": "tool-linux-aarch64-gnu.tar.gz"},
                {"name": "tool-darwin-arm64.tar.gz"},
                {"name": "checksums.txt"},
                {"name": "tool-linux-x86_64.tar.gz.sha256"},
            ]
        )

    def test_picks_x86_64_gnu(self) -> None:
        asset = github.select_asset(self._sample(), arch="x86_64", os_name="linux")
        assert asset is not None
        assert asset["name"] == "tool-linux-x86_64-gnu.tar.gz"

    def test_picks_arm64(self) -> None:
        asset = github.select_asset(self._sample(), arch="arm64", os_name="linux")
        assert asset is not None
        assert asset["name"] == "tool-linux-aarch64-gnu.tar.gz"

    def test_excludes_musl_hint(self) -> None:
        asset = github.select_asset(self._sample(), arch="x86_64", os_name="linux", exclude=("gnu",))
        assert asset is not None
        assert asset["name"] == "tool-linux-x86_64-musl.tar.gz"

    def test_skips_checksum_and_sig_assets(self) -> None:
        asset = github.select_asset(self._sample(), arch="x86_64", os_name="linux")
        assert asset is not None
        assert not asset["name"].endswith((".sha256", ".txt"))

    def test_no_match_returns_none(self) -> None:
        release = _release([{"name": "tool-windows-x86_64.zip"}])
        assert github.select_asset(release, arch="x86_64", os_name="linux") is None


class TestFetchReleaseCaching:
    def test_caches_per_repo_tag(self) -> None:
        with patch.object(github, "fetch_text", return_value="{}") as fetched:
            fetched.return_value = '{"assets": []}'
            github.fetch_release("o/r", "v1")
            github.fetch_release("o/r", "v1")
        assert fetched.call_count == 1

    def test_failure_is_cached_as_none(self) -> None:
        with patch.object(github, "fetch_text", side_effect=OSError("boom")) as fetched:
            assert github.fetch_release("o/r", "v1") is None
            assert github.fetch_release("o/r", "v1") is None
        assert fetched.call_count == 1
