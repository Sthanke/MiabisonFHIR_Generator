#!/usr/bin/env python3
"""
MIABIS on FHIR — Batch Validation Script (cross-platform)

Validates FHIR JSON bundles against the latest MIABIS on FHIR IG.
Works on Windows, macOS, and Linux — requires Python 3.8+, Java 17+, Git, Node.js 18+.

Usage:
    python validate-miabis.py                        # validates all *.json in ./bundles/
    python validate-miabis.py /path/to/folder        # validates all *.json in given folder
    python validate-miabis.py /path/to/file.json     # validates a single file
    python validate-miabis.py --skip-setup bundles/  # skip IG clone/build, just validate

Output (in ./miabis-validation/reports/):
    <filename>-validation-report.html   (detailed HTML report per file)
    <filename>-validation-log.txt       (console log per file)
    validation-summary.txt              (one-line-per-file summary table)
"""

import argparse
import glob
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# ===========================================================================
#  Configuration
# ===========================================================================
WORK_DIR = Path("miabis-validation")
REPORTS_DIR = WORK_DIR / "reports"
IG_DIR = WORK_DIR / "miabis-on-fhir"
VALIDATOR = WORK_DIR / "validator_cli.jar"
IG_REPO = "https://github.com/BBMRI-cz/miabis-on-fhir.git"
VALIDATOR_URL = "https://github.com/hapifhir/org.hl7.fhir.core/releases/latest/download/validator_cli.jar"
VALIDATOR_MAX_AGE_DAYS = 30


def banner(msg):
    print(f"\n>>> {msg}")


def check(label, result):
    print(f"    [OK] {label}: {result}")


def fail(msg):
    print(f"\n    [FAIL] {msg}", file=sys.stderr)
    sys.exit(1)


IS_WINDOWS = platform.system() == "Windows"


def run(cmd, cwd=None, capture=False):
    """Run a command, optionally capturing output. Uses shell=True on Windows for .cmd tools."""
    kwargs = dict(cwd=cwd, shell=IS_WINDOWS)
    if capture:
        result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
        return result
    else:
        subprocess.run(cmd, check=True, **kwargs)


def which(name):
    """Cross-platform which."""
    return shutil.which(name)


# ===========================================================================
#  Prerequisite checks
# ===========================================================================
def check_prerequisites():
    banner("Checking prerequisites...")

    # Java
    java = which("java")
    if not java:
        fail("Java not found. Install Java 17+ from https://adoptium.net/")
    r = subprocess.run(["java", "-version"], capture_output=True, text=True, shell=IS_WINDOWS)
    version_line = (r.stderr + r.stdout).split("\n")[0]
    check("Java", version_line.strip())

    # Git
    git = which("git")
    if not git:
        fail("Git not found. Install from https://git-scm.com/")
    r = subprocess.run(["git", "--version"], capture_output=True, text=True, shell=IS_WINDOWS)
    check("Git", r.stdout.strip())

    # Node.js
    node = which("node")
    if not node:
        fail("Node.js not found. Install Node.js 18+ from https://nodejs.org/")
    r = subprocess.run(["node", "-v"], capture_output=True, text=True, shell=IS_WINDOWS)
    check("Node.js", r.stdout.strip())

    # npm
    npm = which("npm")
    if not npm:
        fail("npm not found (should come with Node.js).")
    r = subprocess.run(["npm", "-v"], capture_output=True, text=True, shell=IS_WINDOWS)
    check("npm", r.stdout.strip())


# ===========================================================================
#  Setup steps
# ===========================================================================
def install_sushi():
    banner("STEP 1: Checking SUSHI (FSH compiler)...")
    sushi = which("sushi")
    if sushi:
        r = subprocess.run(["sushi", "--version"], capture_output=True, text=True, shell=IS_WINDOWS)
        check("SUSHI already installed", r.stdout.strip() or "ok")
    else:
        print("    Installing SUSHI...")
        # Use npm prefix on Windows to avoid permission issues
        run(["npm", "install", "-g", "fsh-sushi"])
        check("SUSHI installed", "ok")
        # Refresh PATH awareness
        sushi = which("sushi")
        if not sushi:
            print("    [WARN] sushi not found on PATH after install.")
            print("           You may need to restart your terminal or add npm global bin to PATH.")
            print("           Trying npx sushi as fallback...")


def clone_or_update_ig():
    banner("STEP 2: Fetching latest MIABIS on FHIR IG...")
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    if (IG_DIR / ".git").is_dir():
        print("    Updating existing repository...")
        # Try main, then master
        try:
            run(["git", "fetch", "--depth", "1", "origin", "main"], cwd=IG_DIR)
            run(["git", "reset", "--hard", "FETCH_HEAD"], cwd=IG_DIR)
        except subprocess.CalledProcessError:
            try:
                run(["git", "fetch", "--depth", "1", "origin", "master"], cwd=IG_DIR)
                run(["git", "reset", "--hard", "FETCH_HEAD"], cwd=IG_DIR)
            except subprocess.CalledProcessError:
                print("    [WARN] Could not update, using existing checkout.")
        check("Repository updated", str(IG_DIR))
    else:
        print("    Cloning repository...")
        if IG_DIR.exists():
            shutil.rmtree(IG_DIR)
        run(["git", "clone", "--depth", "1", IG_REPO, str(IG_DIR)])
        check("Repository cloned", str(IG_DIR))


def build_ig():
    banner("STEP 3: Building IG with SUSHI...")
    sushi = which("sushi")
    if sushi:
        run(["sushi", "build"], cwd=IG_DIR)
    else:
        # Fallback: npx
        run(["npx", "fsh-sushi", "build"], cwd=IG_DIR)
    check("SUSHI build complete", "fsh-generated/resources/")


def download_validator():
    banner("STEP 4: Checking HL7 FHIR Validator...")
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    need_download = False
    if not VALIDATOR.exists():
        need_download = True
    else:
        age_days = (time.time() - VALIDATOR.stat().st_mtime) / 86400
        if age_days > VALIDATOR_MAX_AGE_DAYS:
            print(f"    Validator is {age_days:.0f} days old, re-downloading...")
            need_download = True

    if need_download:
        print(f"    Downloading latest FHIR Validator (~300 MB)...")
        urllib.request.urlretrieve(VALIDATOR_URL, str(VALIDATOR))
        check("Validator downloaded", str(VALIDATOR))
    else:
        check("Validator present and recent", str(VALIDATOR))


# ===========================================================================
#  Validation
# ===========================================================================
def validate_file(json_file, ig_resources):
    """Run the FHIR validator on a single file. Returns (errors, warnings, notes, log_path, report_path)."""
    basename = Path(json_file).stem
    report_html = REPORTS_DIR / f"{basename}-validation-report.html"
    report_log = REPORTS_DIR / f"{basename}-validation-log.txt"

    cmd = [
        "java", "-jar", str(VALIDATOR),
        str(json_file),
        "-ig", str(ig_resources),
        "-version", "4.0.1",
        "-allow-example-urls", "true",
        "-extension", "http://example.org/",
        "-output", str(report_html),
    ]

    # Run and capture output
    result = subprocess.run(cmd, capture_output=True, text=True, shell=IS_WINDOWS)
    full_output = result.stdout + result.stderr

    # Write log
    with open(report_log, "w", encoding="utf-8") as f:
        f.write(full_output)

    # Also print to console
    print(full_output)

    # Parse counts from output
    errors = _parse_count(r"(\d+)\s+error", full_output)
    warnings = _parse_count(r"(\d+)\s+warning", full_output)
    notes = _parse_count(r"(\d+)\s+note", full_output)

    return errors, warnings, notes, report_log, report_html


def _parse_count(pattern, text):
    """Extract the last occurrence of a count pattern."""
    matches = re.findall(pattern, text, re.IGNORECASE)
    if matches:
        return int(matches[-1])
    return None


def run_batch_validation(input_files):
    banner("STEP 5: Running validation...")
    print("=" * 64)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ig_resources = IG_DIR / "fsh-generated" / "resources"

    if not ig_resources.is_dir():
        fail(f"IG resources not found at {ig_resources}. Did SUSHI build succeed?")

    summary_path = REPORTS_DIR / "validation-summary.txt"
    results = []
    total = len(input_files)

    for i, json_file in enumerate(input_files, 1):
        fname = os.path.basename(json_file)
        print(f"\n--- [{i}/{total}] Validating: {fname} ---")

        errors, warnings, notes, log_path, report_path = validate_file(json_file, ig_resources)

        e_str = str(errors) if errors is not None else "?"
        w_str = str(warnings) if warnings is not None else "?"
        n_str = str(notes) if notes is not None else "?"

        if errors == 0:
            status = "PASS"
        elif errors is None:
            status = "CHECK LOG"
        else:
            status = "FAIL"

        results.append((fname, e_str, w_str, n_str, status))

        print(f"    -> Errors: {e_str}  Warnings: {w_str}  Notes: {n_str}  [{status}]")
        print(f"    -> Report: {report_path}")

    # Write summary
    passed = sum(1 for r in results if r[4] == "PASS")
    failed = total - passed

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("MIABIS on FHIR — Validation Summary\n")
        f.write(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n")
        f.write(f"Files validated: {total}\n")
        f.write("=" * 64 + "\n\n")
        f.write(f"{'FILE':<50s} {'ERRORS':>8s} {'WARNINGS':>8s} {'NOTES':>8s} {'RESULT'}\n")
        f.write(f"{'----':<50s} {'------':>8s} {'--------':>8s} {'-----':>8s} {'------'}\n")
        for fname, e, w, n, status in results:
            f.write(f"{fname:<50s} {e:>8s} {w:>8s} {n:>8s} {status}\n")
        f.write(f"\n{'=' * 64}\n")
        f.write(f"TOTALS: {total} files | {passed} passed | {failed} failed\n")
        f.write(f"{'=' * 64}\n")

    # Print summary
    print("\n" + "=" * 64)
    print("  VALIDATION COMPLETE")
    print("=" * 64)
    print(f"\n  Files validated: {total}")
    print(f"  Passed (0 errors): {passed}")
    print(f"  Failed / check:    {failed}")
    print(f"\n  Reports directory: {REPORTS_DIR}/")
    print(f"  Summary:           {summary_path}\n")

    with open(summary_path, "r", encoding="utf-8") as f:
        print(f.read())

    return failed


# ===========================================================================
#  Main
# ===========================================================================
def collect_input_files(input_path):
    """Resolve input to a list of .json file paths."""
    p = Path(input_path)

    if p.is_file() and p.suffix.lower() == ".json":
        return [str(p)]

    if p.is_dir():
        files = sorted(glob.glob(str(p / "*.json")))
        if not files:
            fail(f"No .json files found in: {p}")
        return files

    fail(f"Input not found: {input_path}\n\n"
         "Usage:\n"
         "  python validate-miabis.py                       # validates all *.json in ./bundles/\n"
         "  python validate-miabis.py /path/to/folder       # validates all *.json in folder\n"
         "  python validate-miabis.py /path/to/file.json    # validates a single file")


def main():
    parser = argparse.ArgumentParser(
        description="MIABIS on FHIR — Batch Validation Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python validate-miabis.py                         # validates ./bundles/*.json
  python validate-miabis.py /path/to/folder         # validates folder/*.json
  python validate-miabis.py my-bundle.json          # validates a single file
  python validate-miabis.py --skip-setup bundles/   # skip clone/build, just validate
        """,
    )
    parser.add_argument(
        "input", nargs="?", default="bundles",
        help="Path to a .json file or a folder containing .json files (default: ./bundles/)",
    )
    parser.add_argument(
        "--skip-setup", action="store_true",
        help="Skip IG clone/build and validator download (use existing setup)",
    )

    args = parser.parse_args()

    print("=" * 64)
    print("  MIABIS on FHIR — Batch Validation")
    print(f"  Platform: {platform.system()} {platform.release()}")
    print(f"  Python:   {sys.version.split()[0]}")
    print(f"  Input:    {args.input}")
    print("=" * 64)

    # Collect files first (fail early if none found)
    input_files = collect_input_files(args.input)
    print(f"  Files to validate: {len(input_files)}")

    if not args.skip_setup:
        check_prerequisites()
        install_sushi()
        clone_or_update_ig()
        build_ig()
        download_validator()
    else:
        banner("Skipping setup (--skip-setup). Using existing IG and validator.")
        if not VALIDATOR.exists():
            fail(f"Validator not found at {VALIDATOR}. Run without --skip-setup first.")
        if not (IG_DIR / "fsh-generated" / "resources").is_dir():
            fail(f"IG resources not found. Run without --skip-setup first.")

    failed = run_batch_validation(input_files)
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
