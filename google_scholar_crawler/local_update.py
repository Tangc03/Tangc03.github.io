"""One-command local refresh of the Google Scholar stats feed.

Run from anywhere on a network that can reach scholar.google.com (e.g. a
Qoder terminal, which has a working proxy):

    python google_scholar_crawler/local_update.py

It crawls Scholar with main.py, then publishes results/ to the
google-scholar-stats branch (the same layout the CI workflow uses), so the
homepage badges and citation card pick it up immediately.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)

rc = subprocess.call([sys.executable, str(ROOT / 'google_scholar_crawler' / 'main.py')])
if rc != 0:
    sys.exit(rc)


def git(*args, check=True):
    return subprocess.run(['git', *args], check=check, capture_output=True, text=True).stdout.strip()


BOT = ['-c', 'user.name=scholar-stats-bot', '-c', 'user.email=scholar-stats-bot@users.noreply.github.com']

git('fetch', 'origin', 'google-scholar-stats', '--depth', '1', check=False)
b1 = git('hash-object', '-w', 'results/gs_data.json')
b2 = git('hash-object', '-w', 'results/gs_data_shieldsio.json')
tree_in = f'100644 blob {b1}\tgs_data.json\n100644 blob {b2}\tgs_data_shieldsio.json\n'
tr = subprocess.run(['git', 'mktree'], input=tree_in, check=True, capture_output=True, text=True).stdout.strip()

parent = []
if subprocess.run(['git', 'cat-file', '-e', 'refs/remotes/origin/google-scholar-stats^{commit}'],
                  capture_output=True).returncode == 0:
    parent = ['-p', 'refs/remotes/origin/google-scholar-stats']
cm = git(*BOT, 'commit-tree', tr, *parent, '-m', 'Update Google Scholar stats (local refresh)')
git('push', 'origin', f'{cm}:refs/heads/google-scholar-stats', '--force')
print(f'[local_update] published {cm} to google-scholar-stats')