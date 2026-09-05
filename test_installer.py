"""
Smoke tests for the parsing/patching logic in blizzards_installer/. These
don't hit the real network (the sandbox this was written in can't reach
mcjars.app, modrinth.com, or Mojang's servers anyway) - instead they feed
realistic fixture JSON/YAML through the functions to make sure nothing
throws and the output is what we expect. Run with: python3 test_installer.py
"""
import base64
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from blizzards_installer import net as net_mod

from blizzards_installer.config import (
    DEFAULT_PROPERTIES,
    _kill_process_tree,
    _stop_server,
    apply_gameplay_config,
    patch_yaml,
    set_anti_xray,
    set_unsupported_settings,
    write_eula,
    write_server_properties,
)
from blizzards_installer.plugins import (
    _primary_file,
    get_modrinth_plugin_download,
    install_plugins,
    load_plugin_registry,
    resolve_dependencies,
    small_caps,
    write_tab_config,
)
from blizzards_installer.presets import PRESETS, write_plugin_presets
from blizzards_installer.public import (
    agent_asset,
    install_agent,
    open_claim_console,
    store_secret,
    write_public_files,
)
from blizzards_installer.scripts import write_start_scripts
from blizzards_installer.serverjar import (
    _find_jar_url,
    _try_mcjars,
    _try_papermc_fill,
    download_server_jar,
)
from blizzards_installer.versions import choose_minecraft_version
from blizzards_installer.wizard import run_wizard


class TestFindJarUrl(unittest.TestCase):
    def test_downloads_dict_shape(self):
        build = {
            "id": 42,
            "buildNumber": 42,
            "downloads": {"SERVER": {"url": "https://example.com/paper-1.21.4-42.jar", "name": "paper.jar"}},
        }
        self.assertEqual(_find_jar_url(build), "https://example.com/paper-1.21.4-42.jar")

    def test_lowercase_server_key(self):
        build = {"downloads": {"server": {"url": "https://example.com/x.jar"}}}
        self.assertEqual(_find_jar_url(build), "https://example.com/x.jar")

    def test_flat_url_field(self):
        build = {"buildNumber": 1, "jarUrl": "https://example.com/paper.jar"}
        self.assertEqual(_find_jar_url(build), "https://example.com/paper.jar")

    def test_recursive_scan_fallback(self):
        payload = {"builds": [{"nested": {"deep": {"url": "https://example.com/deep.jar"}}}]}
        self.assertEqual(_find_jar_url(payload), "https://example.com/deep.jar")

    def test_no_jar_found(self):
        self.assertIsNone(_find_jar_url({"foo": "bar"}))
        self.assertIsNone(_find_jar_url([1, 2, 3]))
        self.assertIsNone(_find_jar_url("no url here"))


class TestPaperMCFillFallback(unittest.TestCase):
    @patch("blizzards_installer.net.http_get_json")
    def test_picks_stable_build(self, mock_get):
        mock_get.return_value = [
            {"channel": "EXPERIMENTAL", "downloads": {"server:default": {"url": "https://x/exp.jar"}}},
            {"channel": "STABLE", "downloads": {"server:default": {"url": "https://x/stable1.jar"}}},
            {"channel": "STABLE", "downloads": {"server:default": {"url": "https://x/stable2.jar"}}},
        ]
        url = _try_papermc_fill("1.21.4")
        self.assertEqual(url, "https://x/stable2.jar")  # newest stable = last in list per Paper docs

    @patch("blizzards_installer.net.http_get_json")
    def test_empty_response(self, mock_get):
        mock_get.return_value = []
        self.assertIsNone(_try_papermc_fill("1.21.4"))

    @patch("blizzards_installer.net.http_get_json", side_effect=Exception("network error"))
    def test_network_failure_returns_none(self, mock_get):
        self.assertIsNone(_try_papermc_fill("1.21.4"))


class TestModrinthDownload(unittest.TestCase):
    @patch("blizzards_installer.net.http_get_json")
    def test_exact_version_match(self, mock_get):
        mock_get.return_value = [
            {
                "version_type": "release",
                "date_published": "2024-01-01T00:00:00Z",
                "files": [{"primary": True, "url": "https://cdn/tab-old.jar", "filename": "tab-old.jar"}],
            },
            {
                "version_type": "release",
                "date_published": "2024-06-01T00:00:00Z",
                "files": [{"primary": True, "url": "https://cdn/tab-new.jar", "filename": "tab-new.jar"}],
            },
        ]
        url, filename = get_modrinth_plugin_download("tab-was-taken", "1.21.4", "paper")
        self.assertEqual(filename, "tab-new.jar")
        self.assertEqual(url, "https://cdn/tab-new.jar")

    @patch("blizzards_installer.net.http_get_json")
    def test_falls_back_when_no_exact_match(self, mock_get):
        # first call (exact game_version) -> empty, second call (loader only) -> one result
        mock_get.side_effect = [
            [],
            [{"version_type": "release", "date_published": "2024-01-01", "files": [{"primary": True, "url": "https://cdn/x.jar", "filename": "x.jar"}]}],
        ]
        url, filename = get_modrinth_plugin_download("someplugin", "1.99.9", "paper")
        self.assertEqual(filename, "x.jar")

    @patch("blizzards_installer.net.http_get_json")
    def test_no_files_raises(self, mock_get):
        mock_get.return_value = [{"version_type": "release", "date_published": "2024-01-01", "files": []}]
        with self.assertRaises(RuntimeError):
            get_modrinth_plugin_download("broken", "1.21.4", "paper")

    @patch("blizzards_installer.net.http_get_json")
    def test_http_404_on_exact_match_triggers_loader_fallback(self, mock_get):
        # Modrinth answers unsupported loader/version combos with HTTP 404
        # instead of an empty list - that must route into the loose fallback,
        # not abort the install.
        not_found = net_mod.HTTPError("https://x", 404)
        mock_get.side_effect = [
            not_found,
            [{"version_type": "release", "date_published": "2024-01-01", "files": [{"primary": True, "url": "https://cdn/y.jar", "filename": "y.jar"}]}],
        ]
        url, filename = get_modrinth_plugin_download("vault", "99.9", "paper")
        self.assertEqual(filename, "y.jar")
        self.assertEqual(mock_get.call_count, 2)


class TestHttpOptional(unittest.TestCase):
    @patch("blizzards_installer.net.http_get_json")
    def test_swallows_404(self, mock_get):
        mock_get.side_effect = net_mod.HTTPError("https://x", 404)
        self.assertIsNone(net_mod.http_get_json_optional("https://x"))

    @patch("blizzards_installer.net.http_get_json")
    def test_propagates_other_errors(self, mock_get):
        mock_get.side_effect = net_mod.ConnectionError("boom")
        with self.assertRaises(net_mod.ConnectionError):
            net_mod.http_get_json_optional("https://x")

    @patch("blizzards_installer.net.http_get_json")
    def test_returns_payload_on_success(self, mock_get):
        mock_get.return_value = {"ok": True}
        self.assertEqual(net_mod.http_get_json_optional("https://x"), {"ok": True})


class TestPrimaryFileSelection(unittest.TestCase):
    def test_prefers_primary_marked_file(self):
        files = [
            {"primary": False, "url": "https://cdn/a.jar", "filename": "a.jar"},
            {"primary": True, "url": "https://cdn/b.jar", "filename": "b.jar"},
        ]
        self.assertEqual(_primary_file(files)["filename"], "b.jar")

    def test_falls_back_to_first_when_none_primary(self):
        files = [
            {"primary": False, "url": "https://cdn/a.jar", "filename": "a.jar"},
            {"primary": False, "url": "https://cdn/b.jar", "filename": "b.jar"},
        ]
        self.assertEqual(_primary_file(files)["filename"], "a.jar")

    def test_empty_returns_none(self):
        self.assertIsNone(_primary_file([]))


class TestYamlPatching(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_patch_modern_global_config(self):
        path = self.tmpdir / "paper-global.yml"
        path.write_text(
            "_version: 30\n"
            "unsupported-settings:\n"
            "  allow-piston-duplication: false\n"
            "  allow-permanent-block-break-exploits: false\n"
            "  allow-headless-pistons: false\n",
            encoding="utf-8",
        )
        patch_yaml(path, lambda d: set_unsupported_settings(d, {
            "tnt_dupe": True, "block_break_exploits": True, "headless_pistons": False,
        }))
        text = path.read_text(encoding="utf-8")
        self.assertIn("allow-piston-duplication: true", text)
        self.assertIn("allow-permanent-block-break-exploits: true", text)
        self.assertIn("allow-headless-pistons: false", text)

    def test_patch_anti_xray_modern(self):
        path = self.tmpdir / "paper-world-defaults.yml"
        path.write_text("anticheat:\n  anti-xray:\n    enabled: false\n    engine-mode: 1\n", encoding="utf-8")
        patch_yaml(path, lambda d: set_anti_xray(d, True, 2))
        text = path.read_text(encoding="utf-8")
        self.assertIn("enabled: true", text)
        self.assertIn("engine-mode: 2", text)

    def test_patch_anti_xray_legacy_layout(self):
        path = self.tmpdir / "paper.yml"
        path.write_text("world-settings:\n  default:\n    some-other-setting: true\n", encoding="utf-8")
        patch_yaml(path, lambda d: set_anti_xray(d, True, 1))
        text = path.read_text(encoding="utf-8")
        self.assertIn("anti-xray", text)
        self.assertIn("enabled: true", text)

    def test_patch_missing_section_is_created(self):
        path = self.tmpdir / "paper-global.yml"
        path.write_text("_version: 30\n", encoding="utf-8")
        patch_yaml(path, lambda d: set_unsupported_settings(d, {
            "tnt_dupe": True, "block_break_exploits": False, "headless_pistons": True,
        }))
        text = path.read_text(encoding="utf-8")
        self.assertIn("unsupported-settings", text)
        self.assertIn("allow-piston-duplication: true", text)


class TestServerProperties(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_overrides_applied_and_defaults_kept(self):
        write_server_properties(self.tmpdir, {"motd": "Hello!", "max-players": "50"})
        content = (self.tmpdir / "server.properties").read_text(encoding="utf-8")
        self.assertIn("motd=Hello!", content)
        self.assertIn("max-players=50", content)
        # a default we did not override should still be present
        self.assertIn("view-distance=10", content)

    def test_bool_and_int_overrides_serialized(self):
        write_server_properties(self.tmpdir, {"online-mode": True, "pvp": False, "max-players": 20})
        content = (self.tmpdir / "server.properties").read_text(encoding="utf-8")
        self.assertIn("online-mode=true", content)
        self.assertIn("pvp=false", content)
        self.assertIn("max-players=20", content)

    def test_all_default_keys_are_strings(self):
        for k, v in DEFAULT_PROPERTIES.items():
            self.assertIsInstance(k, str)
            self.assertIsInstance(v, str)


class TestDependencyResolution(unittest.TestCase):
    def test_pulls_in_required_plugin(self):
        plugins_by_id = {
            "essentialsx": {"name": "EssentialsX", "requires": ["vault"]},
            "vault": {"name": "Vault", "requires": []},
        }
        resolved = resolve_dependencies({"essentialsx"}, plugins_by_id)
        self.assertEqual(resolved, {"essentialsx", "vault"})

    def test_transitive_dependency(self):
        plugins_by_id = {
            "floodgate": {"name": "Floodgate", "requires": ["geyser"]},
            "geyser": {"name": "Geyser", "requires": []},
        }
        resolved = resolve_dependencies({"floodgate"}, plugins_by_id)
        self.assertEqual(resolved, {"floodgate", "geyser"})


class TestPluginRegistry(unittest.TestCase):
    def test_registry_loads_and_has_required_fields(self):
        plugins, categories = load_plugin_registry()
        self.assertTrue(len(plugins) > 0)
        self.assertTrue(len(categories) > 0)
        ids = set()
        plugin_ids = [p["id"] for p in plugins]
        for p in plugins:
            for field in ("id", "name", "modrinth_slug", "category", "question"):
                self.assertIn(field, p)
            self.assertNotIn(p["id"], ids, f"duplicate plugin id {p['id']}")
            ids.add(p["id"])
            for dep in p.get("requires", []):
                self.assertIn(dep, plugin_ids, f"unknown dependency {dep} for {p['id']}")

    def test_tab_slug_matches_known_modrinth_project(self):
        plugins, _ = load_plugin_registry()
        tab = next(p for p in plugins if p["id"] == "tab")
        self.assertEqual(tab["modrinth_slug"], "tab-was-taken")


class TestStartScripts(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_two_gig_ram_flags(self):
        # A "2G server" must get -Xms2048M -Xmx2048M in both start scripts.
        write_start_scripts(self.tmpdir, "paper-1.21.4.jar", 2048)
        bat = (self.tmpdir / "start.bat").read_text(encoding="utf-8")
        sh = (self.tmpdir / "start.sh").read_text(encoding="utf-8")
        for content in (bat, sh):
            self.assertIn("-Xms2048M -Xmx2048M", content)
            self.assertIn('-jar "paper-1.21.4.jar" --nogui', content)
        self.assertTrue(sh.startswith("#!/usr/bin/env bash"))

    def test_ram_value_is_used_verbatim(self):
        write_start_scripts(self.tmpdir, "purpur-1.20.1.jar", 7168)
        bat = (self.tmpdir / "start.bat").read_text(encoding="utf-8")
        self.assertIn("-Xms7168M -Xmx7168M", bat)


class TestEula(unittest.TestCase):
    def test_writes_eula_agreement(self):
        tmpdir = Path(tempfile.mkdtemp())
        try:
            write_eula(tmpdir)
            content = (tmpdir / "eula.txt").read_text(encoding="utf-8")
            self.assertIn("eula=true", content)
            self.assertIn("MinecraftEULA", content)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestMcjarsLookup(unittest.TestCase):
    @patch("blizzards_installer.net.http_get_json")
    def test_picks_newest_build_number(self, mock_get):
        # Builds arrive out of order -> must be sorted by buildNumber, newest first.
        mock_get.return_value = {
            "builds": [
                {"buildNumber": 3, "downloads": {"SERVER": {"url": "https://x/old.jar"}}},
                {"buildNumber": 9, "downloads": {"SERVER": {"url": "https://x/new.jar"}}},
                {"buildNumber": 5, "downloads": {"SERVER": {"url": "https://x/mid.jar"}}},
            ]
        }
        self.assertEqual(_try_mcjars("PAPER", "1.21.4"), "https://x/new.jar")

    @patch("blizzards_installer.net.http_get_json")
    def test_unusable_responses_return_none(self, mock_get):
        # Four lookup attempts (2 bases x 2 paths); none yield a jar URL.
        mock_get.side_effect = [
            {"builds": [{"buildNumber": 1, "some": "field"}]},  # no url anywhere
            {"builds": []},
            Exception("network error"),
            {"not": "builds at all"},
        ]
        self.assertIsNone(_try_mcjars("FOLIA", "1.20"))

    @patch("blizzards_installer.net.http_get_json")
    def test_returns_first_usable_response(self, mock_get):
        mock_get.return_value = {"builds": [{"jarUrl": "https://x/works.jar"}]}
        self.assertEqual(_try_mcjars("PURPUR", "1.21"), "https://x/works.jar")


class TestDownloadServerJar(unittest.TestCase):
    @patch("blizzards_installer.net.download_file")
    @patch("blizzards_installer.serverjar._try_mcjars", return_value=None)
    def test_paper_falls_back_to_papermc_api(self, mock_mcjars, mock_dl):
        with patch("blizzards_installer.serverjar._try_papermc_fill", return_value="https://x/fallback.jar") as mock_fill:
            dest = Path("paper-1.21.4.jar")
            download_server_jar("paper", "1.21.4", dest)
            mock_fill.assert_called_once_with("1.21.4")
            mock_dl.assert_called_once_with("https://x/fallback.jar", dest, "paper-1.21.4.jar")

    @patch("blizzards_installer.net.download_file")
    @patch("blizzards_installer.serverjar._try_mcjars", return_value=None)
    def test_non_paper_without_fallback_raises(self, mock_mcjars, mock_dl):
        # PaperMC fallback must NOT be consulted for non-paper servers.
        with patch("blizzards_installer.serverjar._try_papermc_fill") as mock_fill:
            with self.assertRaises(RuntimeError):
                download_server_jar("purpur", "1.21.4", Path("purpur-1.21.4.jar"))
            mock_fill.assert_not_called()
            mock_dl.assert_not_called()

    @patch("blizzards_installer.net.download_file")
    @patch("blizzards_installer.serverjar._try_mcjars", return_value="https://x/direct.jar")
    def test_mcjars_url_used_directly(self, mock_mcjars, mock_dl):
        download_server_jar("purpur", "1.21.4", Path("purpur-1.21.4.jar"))
        mock_dl.assert_called_once()
        self.assertEqual(mock_dl.call_args.args[0], "https://x/direct.jar")


class TestChooseMinecraftVersion(unittest.TestCase):
    @patch("blizzards_installer.net.http_get_json")
    def test_picks_release_from_manifest(self, mock_get):
        mock_get.return_value = {
            "versions": [
                {"id": "1.21.4", "type": "release"},
                {"id": "1.21.4-pre2", "type": "snapshot"},
                {"id": "1.21.3", "type": "release"},
            ]
        }
        with patch("blizzards_installer.versions.ask_choice", return_value=0) as mock_choice:
            self.assertEqual(choose_minecraft_version(), "1.21.4")
            # snapshots must not be offered
            self.assertNotIn("1.21.4-pre2", mock_choice.call_args.args[1])

    @patch("blizzards_installer.net.http_get_json")
    def test_manual_entry_option(self, mock_get):
        mock_get.return_value = {
            "versions": [{"id": "1.21.4", "type": "release"}, {"id": "1.21.3", "type": "release"}]
        }
        with patch("blizzards_installer.versions.ask_choice", return_value=2) as mock_choice:
            with patch("blizzards_installer.versions.ask_text", return_value="1.20") as mock_text:
                self.assertEqual(choose_minecraft_version(), "1.20")
                mock_text.assert_called_once()

    @patch("blizzards_installer.net.http_get_json", side_effect=Exception("network down"))
    def test_manifest_failure_asks_manually(self, mock_get):
        with patch("blizzards_installer.versions.ask_choice") as mock_choice:
            with patch("blizzards_installer.versions.ask_text", return_value="1.19.4") as mock_text:
                self.assertEqual(choose_minecraft_version(), "1.19.4")
                mock_choice.assert_not_called()
                self.assertIn("Enter the Minecraft version", mock_text.call_args.args[0])


class TestInstallPlugins(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("blizzards_installer.net.download_file")
    def test_continues_past_failed_plugin(self, mock_dl):
        chosen = [
            {"name": "GoodPlugin", "modrinth_slug": "good"},
            {"name": "BadPlugin", "modrinth_slug": "bad"},
        ]
        with patch(
            "blizzards_installer.plugins.get_modrinth_plugin_download",
            side_effect=[("https://u/good.jar", "good.jar"), Exception("modrinth down")],
        ):
            installed = install_plugins(chosen, "1.21.4", "paper", self.tmpdir)
        self.assertEqual([p["name"] for p in installed], ["GoodPlugin"])
        mock_dl.assert_called_once_with("https://u/good.jar", self.tmpdir / "good.jar", "good.jar")


class TestApplyGameplayConfig(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @staticmethod
    def _write_fixture_configs(server_dir):
        (server_dir / "config").mkdir(parents=True, exist_ok=True)
        (server_dir / "config" / "paper-global.yml").write_text(
            "_version: 30\n"
            "unsupported-settings:\n"
            "  allow-piston-duplication: false\n"
            "  allow-permanent-block-break-exploits: false\n"
            "  allow-headless-pistons: false\n",
            encoding="utf-8",
        )
        (server_dir / "config" / "paper-world-defaults.yml").write_text(
            "anticheat:\n  anti-xray:\n    enabled: false\n    engine-mode: 1\n", encoding="utf-8"
        )

    def test_successful_bootstrap_patches_configs(self):
        def fake_bootstrap(server_dir, jar_path):
            self._write_fixture_configs(server_dir)
            return True

        answers = {
            "tnt_dupe": True,
            "block_break_exploits": False,
            "headless_pistons": True,
            "anti_xray": True,
            "anti_xray_mode": 2,
        }
        with patch("blizzards_installer.config.bootstrap_configs", side_effect=fake_bootstrap):
            apply_gameplay_config(self.tmpdir, Path("server.jar"), answers)
        global_text = (self.tmpdir / "config" / "paper-global.yml").read_text(encoding="utf-8")
        self.assertIn("allow-piston-duplication: true", global_text)
        self.assertIn("allow-permanent-block-break-exploits: false", global_text)
        self.assertIn("allow-headless-pistons: true", global_text)
        world_text = (self.tmpdir / "config" / "paper-world-defaults.yml").read_text(encoding="utf-8")
        self.assertIn("enabled: true", world_text)
        self.assertIn("engine-mode: 2", world_text)
        self.assertFalse((self.tmpdir / "MANUAL_CONFIG_NOTES.txt").exists())

    def test_failed_bootstrap_writes_manual_notes(self):
        answers = {
            "tnt_dupe": True,
            "block_break_exploits": True,
            "headless_pistons": False,
            "anti_xray": True,
            "anti_xray_mode": 1,
        }
        with patch("blizzards_installer.config.bootstrap_configs", return_value=False):
            apply_gameplay_config(self.tmpdir, Path("server.jar"), answers)
        notes = (self.tmpdir / "MANUAL_CONFIG_NOTES.txt").read_text(encoding="utf-8")
        self.assertIn("allow-piston-duplication: true", notes)
        self.assertIn("allow-permanent-block-break-exploits: true", notes)
        self.assertIn("allow-headless-pistons: false", notes)
        self.assertIn("engine-mode: 1", notes)


class TestStopServer(unittest.TestCase):
    def _make_proc(self, pid=4242):
        proc = MagicMock()
        proc.pid = pid
        proc.poll.return_value = None
        return proc

    def test_graceful_stop_succeeds_without_force(self):
        proc = self._make_proc()
        with patch("blizzards_installer.config._kill_process_tree") as mock_kill, \
                patch("blizzards_installer.config.warn") as mock_warn:
            _stop_server(proc)
        proc.stdin.write.assert_called_once_with("stop\n")
        proc.wait.assert_called_once_with(timeout=60)
        mock_kill.assert_not_called()
        mock_warn.assert_not_called()

    def test_graceful_timeout_escalates_to_tree_kill(self):
        proc = self._make_proc()
        proc.wait.side_effect = [subprocess.TimeoutExpired("java", 60), None]
        with patch("blizzards_installer.config._kill_process_tree") as mock_kill, \
                patch("blizzards_installer.config.warn") as mock_warn:
            _stop_server(proc)
        # After the in-game stop timed out, the whole tree must be killed,
        # never just the tracked PID (which could orphan the JVM child).
        mock_kill.assert_called_once_with(4242)
        self.assertEqual(proc.wait.call_count, 2)
        self.assertTrue(mock_warn.called)

    def test_stop_skipped_when_process_already_exited(self):
        proc = self._make_proc()
        proc.poll.return_value = 0
        with patch("blizzards_installer.config._kill_process_tree") as mock_kill:
            _stop_server(proc)
        proc.stdin.write.assert_not_called()
        proc.wait.assert_not_called()
        mock_kill.assert_not_called()

    def test_tree_kill_windows_uses_taskkill(self):
        with patch("blizzards_installer.config.os.name", "nt"), \
                patch("blizzards_installer.config.subprocess.run") as mock_run:
            _kill_process_tree(4321)
        mock_run.assert_called_once_with(
            ["taskkill", "/PID", "4321", "/T", "/F"],
            capture_output=True,
        )

    def test_tree_kill_posix_signals_process_group(self):
        with patch("blizzards_installer.config.os.name", "posix"), \
                patch("os.getpgid", return_value=4321, create=True) as mock_getpgid, \
                patch("os.killpg", create=True) as mock_killpg:
            _kill_process_tree(4321)
        mock_getpgid.assert_called_once_with(4321)
        mock_killpg.assert_called_once_with(4321, 9)  # SIGKILL

    def test_tree_kill_posix_ignores_missing_group(self):
        with patch("blizzards_installer.config.os.name", "posix"), \
                patch("os.getpgid", side_effect=ProcessLookupError, create=True), \
                patch("os.killpg", create=True) as mock_killpg:
            _kill_process_tree(4321)  # must not raise
        mock_killpg.assert_not_called()


class TestPublicIntegration(unittest.TestCase):
    ASSETS = [
        {"name": "playit-windows-x86_64-signed.exe", "browser_download_url": "https://x/win-signed.exe"},
        {"name": "playit-windows-x86_64.exe", "browser_download_url": "https://x/win.exe"},
        {"name": "playit-windows-x86-signed.exe", "browser_download_url": "https://x/win32-signed.exe"},
        {"name": "playit-linux-amd64", "browser_download_url": "https://x/linux-amd64"},
        {"name": "playit-linux-aarch64", "browser_download_url": "https://x/linux-aarch64"},
    ]

    @patch("blizzards_installer.net.http_get_json")
    def test_windows_prefers_signed_x64(self, mock_get):
        mock_get.return_value = {"assets": self.ASSETS}
        with patch("sys.platform", "win32"), patch("platform.machine", return_value="AMD64"):
            name, url = agent_asset()
        self.assertEqual(name, "playit-windows-x86_64-signed.exe")
        self.assertEqual(url, "https://x/win-signed.exe")

    @patch("blizzards_installer.net.http_get_json")
    def test_linux_amd64_asset(self, mock_get):
        mock_get.return_value = {"assets": self.ASSETS}
        with patch("sys.platform", "linux"), patch("platform.machine", return_value="x86_64"):
            name, _ = agent_asset()
        self.assertEqual(name, "playit-linux-amd64")

    @patch("blizzards_installer.net.http_get_json")
    def test_macos_not_on_github_raises(self, mock_get):
        mock_get.return_value = {"assets": self.ASSETS}
        with patch("sys.platform", "darwin"):
            with self.assertRaises(RuntimeError):
                agent_asset()

    @patch("blizzards_installer.net.http_get_json")
    def test_no_matching_asset_raises(self, mock_get):
        mock_get.return_value = {"assets": []}
        with patch("sys.platform", "win32"), patch("platform.machine", return_value="AMD64"):
            with self.assertRaises(RuntimeError):
                agent_asset()

    def test_install_agent_downloads_into_playit_dir(self):
        server_dir = Path(tempfile.mkdtemp())
        try:
            with patch("blizzards_installer.public.agent_asset", return_value=("playit-linux-amd64", "https://x/agent")), \
                    patch("blizzards_installer.net.download_file") as mock_dl, \
                    patch("blizzards_installer.public.os.name", "posix"), \
                    patch("blizzards_installer.public.os.chmod") as mock_chmod:
                dest = install_agent(server_dir)
            self.assertEqual(dest, server_dir / "playit" / "playit-linux-amd64")
            mock_dl.assert_called_once_with("https://x/agent", dest, "playit.gg agent")
            mock_chmod.assert_called_once_with(dest, 0o755)
        finally:
            shutil.rmtree(server_dir, ignore_errors=True)

    def test_write_public_files_without_secret(self):
        server_dir = Path(tempfile.mkdtemp())
        try:
            playit_dir = server_dir / "playit"
            playit_dir.mkdir()
            (playit_dir / "playit-linux-amd64").write_bytes(b"agent")
            write_public_files(server_dir, "paper-1.21.4.jar", 2048)
            bat = (server_dir / "start-public.bat").read_text(encoding="utf-8")
            self.assertIn("playit-linux-amd64", bat)
            self.assertIn('-jar "paper-1.21.4.jar" --nogui', bat)
            self.assertIn("-Xms2048M -Xmx2048M", bat)
            self.assertNotIn("--secret", bat)
            sh = (server_dir / "start-public.sh").read_text(encoding="utf-8")
            self.assertIn('"./playit/playit-linux-amd64"', sh)
            self.assertNotIn("--secret", sh)
            self.assertTrue(sh.startswith("#!/usr/bin/env bash"))
            notes = (server_dir / "PUBLIC_SERVER.txt").read_text(encoding="utf-8")
            self.assertIn("playit.gg", notes)
            self.assertIn("127.0.0.1:25565", notes)
        finally:
            shutil.rmtree(server_dir, ignore_errors=True)

    def test_write_public_files_with_secret_embeds_key(self):
        server_dir = Path(tempfile.mkdtemp())
        try:
            playit_dir = server_dir / "playit"
            playit_dir.mkdir()
            (playit_dir / "playit-linux-amd64").write_bytes(b"agent")
            store_secret(server_dir, "secret_abc-123")
            write_public_files(server_dir, "paper-1.21.4.jar", 2048)
            bat = (server_dir / "start-public.bat").read_text(encoding="utf-8")
            self.assertIn('--secret "secret_abc-123"', bat)
            sh = (server_dir / "start-public.sh").read_text(encoding="utf-8")
            self.assertIn('--secret "secret_abc-123"', sh)
            self.assertIn('-jar "paper-1.21.4.jar" --nogui', sh)
        finally:
            shutil.rmtree(server_dir, ignore_errors=True)

    def test_store_secret_validates_and_chmods(self):
        server_dir = Path(tempfile.mkdtemp())
        try:
            (server_dir / "playit").mkdir()
            with patch("blizzards_installer.public.os.name", "posix"), \
                    patch("blizzards_installer.public.os.chmod") as mock_chmod:
                path = store_secret(server_dir, " abc-123.def ")
            self.assertIsNotNone(path)
            self.assertEqual(path.read_text(encoding="utf-8"), "abc-123.def\n")
            mock_chmod.assert_called_once_with(path, 0o600)
        finally:
            shutil.rmtree(server_dir, ignore_errors=True)

    def test_store_secret_empty_returns_none(self):
        server_dir = Path(tempfile.mkdtemp())
        try:
            self.assertIsNone(store_secret(server_dir, "   "))
            self.assertFalse((server_dir / "playit" / "secret.key").exists())
        finally:
            shutil.rmtree(server_dir, ignore_errors=True)

    def test_store_secret_rejects_dangerous_chars(self):
        server_dir = Path(tempfile.mkdtemp())
        try:
            with self.assertRaises(ValueError):
                store_secret(server_dir, "abc&echo pwned")
        finally:
            shutil.rmtree(server_dir, ignore_errors=True)

    @patch("blizzards_installer.public.subprocess.Popen")
    def test_open_claim_console_windows(self, mock_popen):
        agent = Path("C:/playit/playit-windows-x86_64-signed.exe")
        with patch("sys.platform", "win32"):
            self.assertTrue(open_claim_console(agent))
        mock_popen.assert_called_once()
        self.assertEqual(mock_popen.call_args.args[0], [str(agent)])
        self.assertEqual(
            mock_popen.call_args.kwargs["creationflags"],
            getattr(subprocess, "CREATE_NEW_CONSOLE", 0x10),
        )

    @patch("blizzards_installer.public.subprocess.Popen")
    def test_open_claim_console_nonwindows_prints_instructions(self, mock_popen):
        with patch("sys.platform", "linux"):
            self.assertFalse(open_claim_console(Path("/x/playit-linux-amd64")))
        mock_popen.assert_not_called()


class TestTabConfig(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_small_caps_maps_letters_keeps_digits(self):
        self.assertEqual(small_caps("Minecraft Server 123"), "ᴍɪɴᴇᴄʀᴀꜰᴛ ꜱᴇʀᴠᴇʀ 123")

    def test_small_caps_leaves_unmapped_chars_alone(self):
        # x has no small-cap form and stays as-is; digits/punctuation pass through.
        self.assertEqual(small_caps("xXyY!"), "xxʏʏ!")

    def test_writes_minimal_tablist_with_server_name(self):
        write_tab_config(self.tmpdir, "Test Server")
        text = (self.tmpdir / "plugins" / "TAB" / "config.yml").read_text(encoding="utf-8")
        self.assertIn("header-footer:", text)
        self.assertIn('- "ᴛᴇꜱᴛ ꜱᴇʀᴠᴇʀ"', text)
        self.assertIn('"&7Online: %online%"', text)
        self.assertIn("footer: []", text)

    def test_color_code_prefixes_name_line(self):
        write_tab_config(self.tmpdir, "Test Server", "&6")
        text = (self.tmpdir / "plugins" / "TAB" / "config.yml").read_text(encoding="utf-8")
        self.assertIn('- "&6ᴛᴇꜱᴛ ꜱᴇʀᴠᴇʀ"', text)

    def test_quotes_in_name_are_yaml_escaped(self):
        write_tab_config(self.tmpdir, 'Say "hi"')
        text = (self.tmpdir / "plugins" / "TAB" / "config.yml").read_text(encoding="utf-8")
        self.assertIn('- "ꜱᴀʏ \\"ʜɪ\\""', text)


class TestPresetConfigs(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_presets_cover_known_blizzard_plugins(self):
        self.assertIn("simpletpa", PRESETS)
        self.assertIn("simplehomes", PRESETS)
        # folder names must match what the plugin's plugin.yml creates on disk
        self.assertEqual(PRESETS["simpletpa"][0], "SimpleTPA")
        self.assertEqual(PRESETS["simplehomes"][0], "Simplehomes")

    def test_write_plugin_presets_writes_decodable_files(self):
        chosen = [{"id": "simpletpa", "name": "SimpleTPA"}, {"id": "simplehomes", "name": "SimpleHomes"}]
        write_plugin_presets(self.tmpdir, chosen)
        tpa = (self.tmpdir / "plugins" / "SimpleTPA" / "config.yml").read_bytes()
        homes = (self.tmpdir / "plugins" / "Simplehomes" / "config.yml").read_bytes()
        self.assertEqual(tpa, base64.b64decode(PRESETS["simpletpa"][2]))
        self.assertEqual(homes, base64.b64decode(PRESETS["simplehomes"][2]))
        self.assertTrue(tpa.startswith(b"settings:"))
        self.assertTrue(homes.startswith(b"max-homes:"))

    def test_write_plugin_presets_skips_unknown_plugins(self):
        chosen = [{"id": "dynmap", "name": "Dynmap"}]
        write_plugin_presets(self.tmpdir, chosen)
        self.assertFalse((self.tmpdir / "plugins").exists())


class TestWizardEndToEnd(unittest.TestCase):
    """Drives the real run_wizard() with only the network/bootstrap mocked:
    exercises the Quick and Full question flows, registry loading, downloads,
    TAB config generation, config presets, config patching and start scripts."""

    def _fake_get_json(self, url, params=None):
        if "piston-meta" in url:
            return {
                "versions": [
                    {"id": "1.21.4", "type": "release"},
                    {"id": "1.21.3", "type": "release"},
                    {"id": "1.21.4-pre1", "type": "snapshot"},
                ]
            }
        if "mcjars" in url or "fill.papermc" in url:
            return {"builds": [{"buildNumber": 1, "downloads": {"SERVER": {"url": "https://cdn.example/paper-1.21.4.jar"}}}]}
        if "api.modrinth.com" in url:
            slug = url.split("/project/")[1].split("/")[0]
            return [{
                "version_type": "release",
                "date_published": "2024-06-01T00:00:00Z",
                "files": [{"primary": True, "url": f"https://cdn.example/{slug}.jar", "filename": f"{slug}.jar"}],
            }]
        raise AssertionError(f"unexpected URL: {url}")

    @staticmethod
    def _fake_download(url, dest, label):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"fake jar")

    def test_quick_wizard_installs_essentials_only(self):
        server_dir = Path(tempfile.mkdtemp()) / "quick"
        # Prompt order in Quick mode: mode (default = Quick), server name,
        # install dir, RAM. Everything else is decided for you.
        answers = [
            "\n",  # mode -> Quick start (index 0)
            "My Quick Server\n",
            str(server_dir) + "\n",
            "\n",  # RAM -> default 4096
        ]

        calls = iter(answers)
        with patch("blizzards_installer.ui.input", side_effect=lambda *a: next(calls)), \
                patch("blizzards_installer.net.http_get_json", side_effect=self._fake_get_json), \
                patch("blizzards_installer.net.download_file", side_effect=self._fake_download), \
                patch("blizzards_installer.config.bootstrap_configs") as mock_bootstrap:
            run_wizard()
        mock_bootstrap.assert_not_called()  # Quick mode skips the config bootstrap

        # MOTD comes from the server name; no extra questions were asked.
        props = (server_dir / "server.properties").read_text(encoding="utf-8")
        self.assertIn("motd=My Quick Server", props)
        self.assertIn("eula=true", (server_dir / "eula.txt").read_text(encoding="utf-8"))
        self.assertTrue((server_dir / "paper-1.21.4.jar").exists())
        self.assertIn("-Xms4096M -Xmx4096M", (server_dir / "start.bat").read_text(encoding="utf-8"))
        self.assertIn("-Xms4096M -Xmx4096M", (server_dir / "start.sh").read_text(encoding="utf-8"))

        # Only the essential plugins (registry "essential": true) landed.
        plugins_dir = server_dir / "plugins"
        self.assertTrue((plugins_dir / "tab-was-taken.jar").exists())
        self.assertTrue((plugins_dir / "viaversion.jar").exists())
        self.assertTrue((plugins_dir / "simpletpaplugin.jar").exists())
        self.assertFalse((plugins_dir / "luckperms.jar").exists())
        self.assertFalse((plugins_dir / "essentialsx.jar").exists())

        # TAB tablist uses the entered server name; SimpleTPA gets its preset.
        tab_text = (plugins_dir / "TAB" / "config.yml").read_text(encoding="utf-8")
        self.assertIn('- "ᴍʏ ǫᴜɪᴄᴋ ꜱᴇʀᴠᴇʀ"', tab_text)
        self.assertTrue((plugins_dir / "SimpleTPA" / "config.yml").exists())

        # No Paper config bootstrap ran, no playit files were created.
        self.assertFalse((server_dir / "config").exists())
        self.assertFalse((server_dir / "MANUAL_CONFIG_NOTES.txt").exists())
        self.assertFalse((server_dir / "playit").exists())

    def test_full_wizard_install_with_2g_ram_and_tab(self):
        server_dir = Path(tempfile.mkdtemp()) / "server"
        # One input per wizard prompt, in ask order (see run_full_wizard): mode,
        # software, version, dir, server name, name color, motd, max players,
        # difficulty, online/whitelist/pvp/hardcore/flight, view/sim distance,
        # TNT dupe, block break, headless pistons, anti-xray(+mode), 17 plugin
        # prompts, RAM, proceed, playit. Defaults ("\n") answer the rest.
        answers = ["\n"] * 41
        answers[0] = "2\n"  # mode -> Full setup (index 1)
        answers[3] = str(server_dir) + "\n"  # install directory
        answers[5] = "2\n"  # server name color -> index 1 = Gray (&7)
        answers[16] = "y\n"  # allow TNT duplication -> patched to true below
        answers[24] = "y\n"  # install TAB (4th plugin prompt)
        answers[38] = "2048\n"  # RAM for the start scripts

        def fake_bootstrap(dir_path, jar_path):
            TestApplyGameplayConfig._write_fixture_configs(dir_path)
            return True

        calls = iter(answers)
        with patch("blizzards_installer.ui.input", side_effect=lambda *a: next(calls)), \
                patch("blizzards_installer.net.http_get_json", side_effect=self._fake_get_json), \
                patch("blizzards_installer.net.download_file", side_effect=self._fake_download), \
                patch("blizzards_installer.config.bootstrap_configs", side_effect=fake_bootstrap):
            run_wizard()

        # 2 GB RAM reached the start scripts.
        bat = (server_dir / "start.bat").read_text(encoding="utf-8")
        sh = (server_dir / "start.sh").read_text(encoding="utf-8")
        self.assertIn("-Xms2048M -Xmx2048M", bat)
        self.assertIn("-Xms2048M -Xmx2048M", sh)

        # Base files + server jar landed. The server name stays separate from the
        # MOTD (its own question) and only feeds the TAB tablist config below.
        self.assertIn("eula=true", (server_dir / "eula.txt").read_text(encoding="utf-8"))
        props = (server_dir / "server.properties").read_text(encoding="utf-8")
        self.assertIn("online-mode=true", props)
        self.assertIn("difficulty=easy", props)
        self.assertIn("motd=A Minecraft Server", props)
        self.assertTrue((server_dir / "paper-1.21.4.jar").exists())

        # TAB was selected -> minimal config with the (default) server name in
        # small caps prefixed with the chosen gray color; plugin jars downloaded.
        tab_cfg = server_dir / "plugins" / "TAB" / "config.yml"
        self.assertTrue(tab_cfg.exists())
        tab_text = tab_cfg.read_text(encoding="utf-8")
        self.assertIn('- "&7ᴍɪɴᴇᴄʀᴀꜰᴛ ꜱᴇʀᴠᴇʀ"', tab_text)
        self.assertIn('"&7Online: %online%"', tab_text)
        self.assertTrue((server_dir / "plugins" / "luckperms.jar").exists())
        self.assertTrue((server_dir / "plugins" / "spark.jar").exists())

        # Gameplay config patched (bootstrap succeeded -> no manual notes).
        global_text = (server_dir / "config" / "paper-global.yml").read_text(encoding="utf-8")
        self.assertIn("allow-piston-duplication: true", global_text)
        world_text = (server_dir / "config" / "paper-world-defaults.yml").read_text(encoding="utf-8")
        self.assertIn("enabled: true", world_text)
        self.assertFalse((server_dir / "MANUAL_CONFIG_NOTES.txt").exists())
        # The public-access question defaults to no: nothing playit-related
        # may be created unless the user opts in.
        self.assertFalse((server_dir / "playit").exists())
        self.assertFalse((server_dir / "start-public.bat").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
