#!/usr/bin/env python3
"""Reproduce the temporary P220/#104 integration, without moving branch refs.

CI instrumentation only. Tests run FROM the detached combined source, not
from the instrumentation checkout. No plugin build, real audio or release claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

MAIN = "7213fe1f81f4036f74431cb5b2d7dbd09b73ee5c"
QA = "6cc9579714c56ee14afa8d5b1612aeeec2f4fac1"
TREE = "1d9b5c21866f383a108768e66529bcbd97f0a3b5"
TEST_SHA = "efc78988fb0e359c1205e8d809d856902cd1ac79"
START_BLOB = "1babe74a33783bbddc62b817a3daf1959e824aaa"
ANCHOR = b"## P98 \xe2\x80\x94 Universal audio-input topology and realtime evidence validity (merged to main)"
MESSAGE = "P220 temporary integration preflight: QA 6cc9579 + main 7213fe1\n"
GIT_OPTIONS = ["-c", "core.autocrlf=false", "-c", "core.eol=lf",
               "-c", "user.name=125A integration preflight",
               "-c", "user.email=preflight@125a.invalid", "-c", "commit.gpgsign=false"]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def git(repo, *args, data=None, env=None, allowed=(0,)):
    p = subprocess.run(["git", "-C", str(repo), *GIT_OPTIONS, *args],
                       input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       env=env)
    require(p.returncode in allowed,
            f"git {args[0]} failed ({p.returncode}): " +
            p.stderr.decode("utf-8", errors="replace")[:2000])
    return p.stdout


def refs(repo):
    return git(repo, "for-each-ref", "--format=%(refname) %(objectname)",
               "refs/heads", "refs/remotes").decode().splitlines()


def entries(repo, rev):
    result = {}
    for row in git(repo, "ls-tree", "-r", "-z", rev).split(b"\0"):
        if row:
            info, name = row.split(b"\t", 1)
            mode, kind, oid = info.decode().split()
            require(kind == "blob" and mode in ("100644", "100755"),
                    "Unexpected non-regular tracked file")
            result[name.decode()] = {"mode": mode, "blob": oid}
    return result


def verify_source(repo, worktree):
    require(git(worktree, "rev-parse", "HEAD^{tree}").decode().strip() == TREE,
            "Detached HEAD tree differs from approved combined tree")
    require(git(worktree, "write-tree").decode().strip() == TREE,
            "Index tree differs from approved combined tree")
    files = entries(worktree, "HEAD")
    for name, entry in files.items():
        path = worktree / name
        require(path.is_file(), "Missing combined source: " + name)
        # Raw bytes, independent of Git's platform checkout filters.
        raw = path.read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        require(actual == entry["blob"], "Changed combined source bytes: " + name)
    return files


def prepare(repo, worktree, out):
    require(not worktree.exists(), "Refusing to reuse an existing worktree")
    require(not (out / "integration.json").exists(), "Refusing to replace evidence")
    out.mkdir(parents=True, exist_ok=True)
    original_refs = refs(repo)
    base = git(repo, "merge-base", QA, MAIN).decode().strip()
    main_files, qa_files, base_files = [entries(repo, r) for r in (MAIN, QA, base)]
    main_changes = sorted(p for p in set(base_files) | set(main_files)
                          if base_files.get(p) != main_files.get(p))
    qa_changes = sorted(p for p in set(base_files) | set(qa_files)
                        if base_files.get(p) != qa_files.get(p))
    require(set(main_changes) & set(qa_changes) == {"START-HERE.md"},
            "Inputs no longer have the reviewed one-file overlap")
    git(repo, "worktree", "add", "--detach", str(worktree), QA)
    git(worktree, "merge", "--no-commit", "--no-ff", MAIN, allowed=(1,))
    conflicts = git(worktree, "diff", "--name-only", "--diff-filter=U").decode().splitlines()
    require(conflicts == ["START-HERE.md"], "Unexpected integration conflicts")
    qa_start = git(repo, "show", QA + ":START-HERE.md")
    main_start = git(repo, "show", MAIN + ":START-HERE.md")
    qp, qs = qa_start.split(ANCHOR, 1)
    mp, ms = main_start.split(ANCHOR, 1)
    require(qs == ms, "Shared START-HERE history has changed")
    (worktree / "START-HERE.md").write_bytes(qp + mp + ANCHOR + qs)
    git(worktree, "add", "START-HERE.md")
    require(git(worktree, "write-tree").decode().strip() == TREE,
            "Resolved integration tree differs from reviewed tree")
    combined = entries(worktree, TREE)
    preservation = []
    for name in sorted(set(base_files) | set(main_files) | set(qa_files)):
        if name == "START-HERE.md":
            require(combined[name]["blob"] == START_BLOB, "Wrong START resolution")
            continue
        source = MAIN if name in main_changes else QA
        expected = (main_files if source == MAIN else qa_files).get(name)
        require(combined.get(name) == expected, "Lost parent change: " + name)
        preservation.append({"path": name, "source": source, "entry": expected})
    env = dict(os.environ)
    for role in ("AUTHOR", "COMMITTER"):
        env[f"GIT_{role}_NAME"] = "125A integration preflight"
        env[f"GIT_{role}_EMAIL"] = "preflight@125a.invalid"
        env[f"GIT_{role}_DATE"] = "2026-11-11T02:17:24+00:00"
    # Object only, followed by a detached checkout. No branch merge/ref update.
    test_sha = git(repo, "commit-tree", TREE, "-p", QA, "-p", MAIN,
                   data=MESSAGE.encode(), env=env).decode().strip()
    require(test_sha == TEST_SHA, "Canonical temporary test commit differs")
    git(worktree, "merge", "--quit")
    git(worktree, "reset", "--hard", test_sha)
    verify_source(repo, worktree)
    require(refs(repo) == original_refs, "A repository branch ref moved")
    record = {
        "schema": "125a-p220-main-preflight-v1", "main": MAIN, "qa": QA,
        "merge_base": base, "combined_tree": TREE, "test_sha": test_sha,
        "test_sha_scope": "temporary detached commit; never pushed as a branch merge",
        "ci_trigger_sha": os.environ.get("GITHUB_SHA"),
        "runner_os": os.environ.get("RUNNER_OS", sys.platform),
        "worktree": str(worktree), "conflicts": conflicts,
        "resolution": "complete QA prefix + complete main P99 prefix + identical P98 history",
        "resolved_start_blob": START_BLOB, "main_changed_paths": main_changes,
        "qa_changed_paths": qa_changes,
        "main_only_commits": git(repo, "rev-list", "--reverse", QA + ".." + MAIN).decode().splitlines(),
        "preserved_parent_blobs": preservation, "branch_refs_before": original_refs,
        "instrumentation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "release_approved": False, "native_plugin_build": "NOT RUN",
        "original_creative_audio": "NOT RUN", "real_daw_asio": "NOT RUN",
        "actual_rea_ghidra_provider": "NOT RUN",
    }
    (out / "integration.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print("Prepared actual combined source", test_sha, "tree", TREE, flush=True)


def verify(repo, worktree, out, with_results=False):
    record = json.loads((out / "integration.json").read_text(encoding="utf-8"))
    require(git(worktree, "rev-parse", "HEAD").decode().strip() == record["test_sha"],
            "Detached test commit changed")
    verify_source(repo, worktree)
    require(refs(repo) == record["branch_refs_before"], "Repository branch refs changed")
    if with_results:
        require("P220 integration negative control: changed source rejected" in
                (out / "identity-negative-control.log").read_text(encoding="utf-8"),
                "Missing source-identity negative control")
        stereo = json.loads((out / "p220-stereo-v2.json").read_text(encoding="utf-8"))
        require(stereo["assertions"] == stereo["passed_assertions"] == 13,
                "Missing stereo assertions")
        require(len(stereo["cases"]) == 13 and
                all(r["expected"] == r["actual"] for r in stereo["cases"]), "Bad stereo cases")
        for field, name in (("tool_source_sha256", "p220_awe_sf2_sound_gate.py"),
                            ("test_source_sha256", "test_p220_awe_sf2_sound_gate.py"),
                            ("pcm_oracle_source_sha256", "run_external_daw_capture_check.py")):
            require(stereo[field] == hashlib.sha256((worktree / "tests" / name).read_bytes()).hexdigest(),
                    "Report source identity mismatch")
        full = (out / "p220-full.log").read_text(encoding="utf-8")
        require("P220 SYNTHETIC oracle positive: 77/77 and 154/154" in full and
                "P220 SYNTHETIC MUTATION AUDIT: 10/10 rejected" in full,
                "Incomplete full P220 test output")
        for name, count in (("p220-release", 5), ("p89", 4), ("p90", 10),
                            ("rea", 2), ("universal", 7), ("batch", 6)):
            log = (out / (name + ".log")).read_text(encoding="utf-8")
            require(re.search(rf"Ran {count} tests in .+\n\s*\nOK\s*$", log) is not None,
                    "Unit suite incomplete/failed/skipped: " + name)
        blocked = json.loads((out / "required-real-audio-evidence.json").read_text(encoding="utf-8"))
        require(blocked["status"] == "BLOCKED" and blocked["release_approved"] is False and
                len(blocked["presets"]) == 77 and
                all(x["status"] == "BLOCKED" for x in blocked["presets"]) and
                not blocked.get("passed_presets"), "Original audio release blocker regressed")
        record["results"] = {"stereo_expectations": "13/13", "synthetic_comparisons": "154/154",
                             "legacy_mutants_rejected": "10/10", "compatibility_units": "19/19",
                             "main_preservation_units": "15/15", "real_audio": "77 BLOCKED / 0 PASS"}
        (out / "integration-verified.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print("::notice title=P220 actual combined source::"
              f"TEST_SHA={record['test_sha']} TREE={TREE} MAIN={MAIN} QA={QA} "
              f"OS={record['runner_os']} stereo=13/13 synthetic=154/154 mutants=10/10 "
              "compatibility=19/19 main_units=15/15 real_audio=77_BLOCKED_0_PASS release=false")
    print("Combined source bytes, tree, parent preservation and branch refs verified", flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("prepare", "verify", "results", "self-test"))
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--worktree", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    repo, worktree, out = [x.resolve() for x in (args.repo, args.worktree, args.out)]
    if args.mode == "prepare":
        prepare(repo, worktree, out)
    elif args.mode == "self-test":
        verify(repo, worktree, out)
        path = worktree / "tests" / "test_p220_awe_sf2_sound_gate.py"
        original = path.read_bytes()
        try:
            path.write_bytes(original + b"\n# deliberate preflight source-identity negative control\n")
            try:
                verify(repo, worktree, out)
            except RuntimeError as exc:
                require("Changed combined source bytes" in str(exc), "Wrong negative-control failure")
                print("P220 integration negative control: changed source rejected", flush=True)
            else:
                raise RuntimeError("Mutated test source falsely accepted")
        finally:
            path.write_bytes(original)
        verify(repo, worktree, out)
    else:
        verify(repo, worktree, out, with_results=args.mode == "results")


if __name__ == "__main__":
    main()
