#!/usr/bin/env python

from __future__ import print_function

import argparse
import json
import os
import platform
import string
import sys


PATHOLOGICAL_DIRS = [
    '.git',
    '.rbenv',
    'pkgs',
]
PACKAGES_FOR_GUESS_VERSIONS = [
    'conda',
    'python',
]
N_A = '(?)' # 'n/a'


def _print_stderr(*args, **kwargs):
    kwargs['file'] = sys.stderr
    print(*args, **kwargs)


def survey(starting_directory, report=print, onerror=_print_stderr, avoid=PATHOLOGICAL_DIRS):
    avoidset = set(avoid)
    for dirpath, dirnames, _ in os.walk(starting_directory, onerror=onerror):
        prune = False
        guess = make_guess(dirpath)
        if guess.is_conda_environment():
            report(guess)
            prune = True
        else:
            name = os.path.basename(dirpath)
            if name in avoidset:
                prune = True
        if prune:
            dirnames[:] = []


def make_guess(dirpath):
    path = os.path.abspath(dirpath)
    if path not in Guess.GUESSES:
        Guess.GUESSES[path] = Guess(dirpath)
    guess = Guess.GUESSES[path]
    base = guess.base
    if type(base) == str:
        guess.base = make_guess(base)
    return guess


class Guess(object):
    GUESSES = {}

    def __init__(self, dirpath):
        self.dirpath = dirpath
        self.path = os.path.abspath(self.dirpath)
        self.meta_dir = os.path.join(self.path, 'conda-meta')
        self.history_file = os.path.join(self.meta_dir, 'history')
        self.bin_dir = os.path.join(self.path, 'bin')
        self.activate_file = os.path.join(self.bin_dir, 'activate')
        self._find_base()
        self._find_versions()

    def __str__(self):
        return str(self.path)

    def is_conda_environment(self):
        if not os.path.isdir(self.meta_dir):
            return False
        if not os.path.isfile(self.history_file):
            return False
        return True

    def _find_base(self):
        base = None
        if self.is_conda_environment():
            if os.path.islink(self.activate_file):
                base_activate_file = resolve_link(self.activate_file)
                base_bin_dir = os.path.dirname(base_activate_file)
                base_dir = os.path.dirname(base_bin_dir)
                if os.path.islink(base_activate_file):
                    # mitigate unlikely but pathological symlink loop
                    base = base_dir
                else:
                    base = make_guess(base_dir)
            elif os.path.isfile(self.activate_file):
                base = self
        self.base = base

    def _find_versions(self):
        versions = {}
        if self.is_conda_environment():
            meta_names = os.listdir(self.meta_dir)
            for meta_name in meta_names:
                if not meta_name.endswith('.json'):
                    continue
                if not any([meta_name.startswith(_) for _ in PACKAGES_FOR_GUESS_VERSIONS]):
                    continue
                meta_file = os.path.join(self.meta_dir, meta_name)
                f = open(meta_file)
                with f:
                    try:
                        data = json.load(f)
                    except:
                        print('!! meta_file:', meta_file, file=sys.stderr)
                        raise
                name = data.get('name', None)
                version = data.get('version', None)
                if name:
                    versions[name] = version
        self.versions = versions


def resolve_link(link):
    target = os.readlink(link)
    if not os.path.isabs(target):
        link_dir = os.path.dirname(link)
        target = os.path.join(link_dir, target)
    return target


def report_for_jira(guess):
    host = platform.node().split('.', 1)[0]

    conda_ver = guess.versions.get('conda', N_A)
    python_ver = guess.versions.get('python', N_A)
    if python_ver.startswith('2.'):
        python_ver += '(!)'

    base = guess.base or N_A
    if base == guess:
        base = '-' # '(base)'

    line = ' '.join([
        '|',
        ' | '.join([str(_) for _ in [
            host,
            guess.path,
            conda_ver,
            python_ver,
            base,
        ]]),
        '|',
    ])

    print(line)


REPORT_CHOICES = {
    'jira': report_for_jira,
    'print': print,
}


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog=argv[0],
        description='Search directories for conda environments',
    )
    parser.add_argument('starts', metavar='DIR', nargs='+')
    parser.add_argument(
        '--report',
        choices=REPORT_CHOICES.keys(),
        default='print',
    )
    args = parser.parse_args(argv[1:])
    return args


def main(argv=sys.argv):
    args = parse_args(argv)
    for start in args.starts:
        survey(start, report=REPORT_CHOICES[args.report])
    sys.exit(0)


if __name__ == '__main__':
    main()
