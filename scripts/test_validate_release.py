"""Release guard tests use temporary Git repositories and never contact PyPI."""
from pathlib import Path
import subprocess
import tempfile
import unittest

import validate_release as guard

class ReleaseGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.git('init', '-b', 'main'); self.git('config', 'user.email', 'fixture@example.test'); self.git('config', 'user.name', 'Fixture')
        self.commit('langchain-mailchannels', '0.1.0')
        self.git('update-ref', 'refs/remotes/origin/main', 'HEAD')
        self.git('tag', 'v0.1.0')
    def git(self, *args): return guard.git(self.repo, *args)
    def commit(self, name, version):
        (self.repo / 'pyproject.toml').write_text(f'[project]\nname="{name}"\nversion="{version}"\n')
        self.git('add', '.'); self.git('commit', '-m', 'fixture')
    def test_valid_tag_on_main(self):
        self.assertEqual(guard.validate(self.repo, 'v0.1.0', True)['commit'], self.git('rev-parse', 'HEAD'))
    def test_candidate_can_build_without_tag_but_publish_cannot(self):
        self.assertEqual(guard.validate(self.repo)['version'], '0.1.0')
        with self.assertRaises(ValueError): guard.validate(self.repo, require_tag=True)
    def test_reject_invalid_tag_input(self):
        for tag in ['--help', 'v0.1.0;echo unsafe', 'main', 'v0.1.0rc1']:
            with self.assertRaises(ValueError): guard.validate(self.repo, tag)
    def test_reject_version_mismatch(self):
        self.git('tag', 'v9.9.9')
        with self.assertRaises(ValueError): guard.validate(self.repo, 'v9.9.9')
    def test_reject_tag_outside_main(self):
        self.git('switch', '-c', 'unmerged'); self.commit('langchain-mailchannels', '0.2.0'); self.git('tag', 'v0.2.0')
        with self.assertRaises(subprocess.CalledProcessError): guard.validate(self.repo, 'v0.2.0')
    def test_reject_wrong_project(self):
        self.commit('unrelated', '0.2.0')
        with self.assertRaises(ValueError): guard.validate(self.repo)

if __name__ == '__main__': unittest.main()
