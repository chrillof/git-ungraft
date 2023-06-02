#!/usr/bin/env python3
"""
    git-ungraft investigates the grafted commits of the git repository and
    checks whether or not any grafted commits can be ungrafted. This may be the
    case when performing shallow fetches of single commits.

    git-ungraft is a single-file script and may be utilized without any 
    installation, except for Python 3.
"""

import re
import sys
import pathlib
import logging
import argparse
import subprocess as sp

_log = logging.getLogger(__name__)

_PARENT_MATCH = re.compile(r"^parent\s+(?P<commithash>[0-9a-f]{40})$")

class InvalidRepoPath(Exception):
    """ Thrown when an invalid repository path is given."""


class CommandExecutionFailed(Exception):
    """ Thrown when a command execution fails. """


class Gitrepo:
    """ A wrapper class to simplify investigating and altering a git repository.
    """

    def __init__(self, path: str):
        with sp.Popen(["git", "-C", path, "rev-parse", "--show-toplevel"],
                        stdout=sp.PIPE, stderr=sp.PIPE) as proc:

            exitcode = proc.wait()
            if exitcode != 0:
                raise InvalidRepoPath(f"The path {path} is not within a git " \
                                       "repository")
            self.root = pathlib.Path(proc.stdout.read().decode("utf-8")
                                                   .rstrip()).absolute()

        _log.debug("Repo root: %s", self.root)

    @property
    def gitdir(self) -> pathlib.Path:
        """
            Returns the path to the .git directory for which this object
            instance was initiated.
        """
        return self.root / ".git"

    def _gitcmd(self, cmd: list[str], allow_error: bool = False) -> list[str]:
        """
            Invokes the given git-command and returns the standard output to
            the caller. The command `git` is implicit.
        """
        invoke_cmd = ["git", "-C", str(self.root)] + cmd
        _log.debug("Invoke command: %s", invoke_cmd)
        with sp.Popen(invoke_cmd, stdout=sp.PIPE, stderr=sp.PIPE) as proc:
            exitcode = proc.wait()
            if not allow_error and exitcode != 0:
                raise CommandExecutionFailed("Command failed: " + " ".join(cmd))

            output = proc.stdout.read().decode("utf-8").splitlines()

        return output

    def get_grafted_commits(self) -> list[str]:
        """
            Retrieve a list of commit hashes that are grafted in the current git
            repository.
        """
        shallow_file = self.gitdir / "shallow"
        grafted_commits = []

        if shallow_file.exists():
            _log.debug("Reading shallow file: %s", shallow_file)
            with open(shallow_file, "r", encoding="utf-8") as shallow:
                grafted_commits = shallow.read().splitlines()
        else:
            _log.debug("No shallow file present: %s", shallow_file)

        return grafted_commits

    def is_existing_commit(self, commitish: str) -> bool:
        """ Returns whether the given commitish exist locally and refers to a 
            commit.
        """

        out = self._gitcmd(["cat-file", "-t", commitish], allow_error=True)
        return out and out[0] == "commit"

    def get_parent_commits(self, commitish: str) -> list[str]:
        """ Retrieve a list of the given commitishes parent commits as recorded
            in the commit itself. Parents are listed even if they are not
            reachable in the current repository (i.e. in case of a grafted 
            commit).
        """
        parents = []
        catfile = self._gitcmd(["cat-file", "-p", commitish])
        for line in catfile:
            match = _PARENT_MATCH.match(line)
            if match:
                parents.append(match.group("commithash"))
            elif parents:
                break
        else:
            _log.info("No parents found for commit %s. Root?", commitish)

        return parents

    def get_ungraft_candidates(self,
                               commitishes: list[str] = None) -> list[str]:
        """ Retrieve a list of commits that are suitable to ungrafting, giving
            the list of commitishes.

            If a list of commitishes is not given, then it defaults to the
            current repository's set of grafted commits, as given by the
            get_grafted_commits() method.
        """

        grafted_commits = commitishes or self.get_grafted_commits()
        candidates = []
        for commitish in grafted_commits:
            _log.debug("Checking parents of commit %s", commitish)
            parents = self.get_parent_commits(commitish)

            _log.debug("Parents for %s: %s", commitish, parents)
            if all([self.is_existing_commit(p) for p in parents]):
                _log.debug("All parents present. Suitable for ungrafting.")
                candidates.append(commitish)

        return candidates


def _main(args: argparse.Namespace) -> None:
    repo = Gitrepo(args.git_dir)
    grafted = repo.get_grafted_commits()
    candidates = repo.get_ungraft_candidates(grafted)

    if not args.dry_run:
        remaining = [c for c in grafted if c not in candidates]
        with open(repo.gitdir/"shallow", "w", encoding="utf-8") as shallow:
            shallow.writelines(remaining)

    prefix = "Would ungraft " if args.dry_run else "Ungrafted "
    for item in candidates:
        print(prefix + item)

def _parse_args(args: list[str]) -> argparse.Namespace:
    _log.debug("Parsing args: %s", args)
    parser = argparse.ArgumentParser(
        description="Investigates all commits marked as grafted and removes " \
                    "those who actually have their parent present.")

    parser.add_argument("-n", "--dry-run", action="store_true",
                        help="Do not do anything, just show what would be " \
                             "done.")
    parser.add_argument("-C", "--git-dir", default=".",
                        help="Path to the repository.")
    parsed = parser.parse_args(args)
    _log.debug("Parsed args: %s", parsed)
    return parsed

if __name__ == "__main__":
    logging.basicConfig (format="%(levelname)-8s %(funcName)s : %(message)s",
                         level=logging.WARNING)

    cmd_args = _parse_args(sys.argv[1:])
    _main(cmd_args)
