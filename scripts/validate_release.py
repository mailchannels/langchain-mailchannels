"""Validate a stable release tag against main and package metadata before building."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tomllib


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True, stderr=subprocess.DEVNULL).strip()


def validate(repo, tag='', require_tag=False):
    if require_tag and not tag:
        raise ValueError('Publishing requires a release tag')
    if tag and not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+', tag):
        raise ValueError('Expected a stable vMAJOR.MINOR.PATCH tag')
    commit = git(repo, 'rev-parse', '--verify', f'refs/tags/{tag}^{{commit}}' if tag else 'HEAD')
    if tag:
        subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', commit, 'origin/main'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    metadata = tomllib.loads(git(repo, 'show', f'{commit}:pyproject.toml'))['project']
    if metadata['name'] != 'langchain-mailchannels':
        raise ValueError('Unexpected project name')
    version = metadata['version']
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version) or (tag and tag != 'v' + version):
        raise ValueError('Release version and tag must agree')
    return {'project': metadata['name'], 'version': version, 'commit': commit, 'tag': tag or None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', default='')
    parser.add_argument('--require-tag', action='store_true')
    parser.add_argument('--checkout', action='store_true')
    args = parser.parse_args()
    repo = Path.cwd()
    try:
        result = validate(repo, args.tag, args.require_tag)
        if args.checkout:
            subprocess.run(['git', 'checkout', '--detach', result['commit']], check=True)
    except (ValueError, KeyError, subprocess.CalledProcessError):
        raise SystemExit('Release validation failed: verify tag, main ancestry and package metadata.')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
