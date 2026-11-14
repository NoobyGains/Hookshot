"""The Hookshot Launcher takes its releases from the repository the builder takes them from, and follows a fork the same way.

The launcher (launcher/Core/Repository.cs) and the Windows Builder (builder/HookshotBuilder/Repository.cs) each fall back to a
built-in owner/name when the program was not stamped with the repository its release was built in; nx2/version.py's
DEFAULT_REPOSITORY is the rule both follow. If the launcher's fallback drifted, a launcher built from a checkout would install
builders from another repository than the builder it installs updates itself from. This holds the three to one name, the
launcher's owner/name check to the builder's, and the launcher's workflow to stamping the repository it runs in, so a fork's
launcher follows the fork. Game-free.

    python -I -B tests/test_launcher_repository.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nx2"))
import version  # noqa: E402


def check(cond, what):
    if not cond:
        raise SystemExit("FAIL: " + what)


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def one(pattern, text, what):
    found = re.findall(pattern, text, re.M)
    check(len(found) == 1, "%s: expected one match of %s, found %r" % (what, pattern, found))
    return found[0]


def main():
    launcher = read("launcher/Core/Repository.cs")
    builder = read("builder/HookshotBuilder/Repository.cs")
    name = version.DEFAULT_REPOSITORY
    ours = one(r'public const string Default = "([^"]+)";', launcher, "launcher/Core/Repository.cs")
    theirs = one(r'const string Default = "([^"]+)";', builder, "builder/HookshotBuilder/Repository.cs")
    check(ours == theirs == name, "the launcher falls back to %s, the builder to %s, nx2/version.py to %s" % (ours, theirs, name))
    # (the same owner/name rule: a stamp the builder takes, the launcher takes, and the other way round)
    rule = one(r'Regex\.IsMatch\(line, "([^"]+)"\)', builder, "builder/HookshotBuilder/Repository.cs")
    check(one(r'static readonly Regex Name = new\("([^"]+)"', launcher, "launcher/Core/Repository.cs") == rule,
          "the launcher's owner/name check differs from the builder's (%s)" % rule)
    # (the program is stamped with the repository its release is built in, and reads that stamp)
    project = read("launcher/App/HookshotLauncher.csproj")
    check('<AssemblyMetadata Include="HookshotRepository" Value="$(HookshotRepository)"' in project,
          "launcher/App/HookshotLauncher.csproj does not stamp HookshotRepository")
    check(one(r'public const string StampKey = "([^"]+)";', launcher, "launcher/Core/Repository.cs") == "HookshotRepository",
          "launcher/Core/Repository.cs reads another stamp than the one the project writes")
    # (the release build is stamped with the repository its workflow runs in: launcher.yml hands it to package.sh, which passes it on)
    workflow = read(".github/workflows/launcher.yml")
    check(re.search(r"HOOKSHOT_REPOSITORY: \$\{\{ github\.repository \}\}\n\s+run: launcher/scripts/package\.sh ", workflow),
          ".github/workflows/launcher.yml does not give package.sh the repository it runs in (HOOKSHOT_REPOSITORY)")
    package = read("launcher/scripts/package.sh")
    check('-p:HookshotRepository="$HOOKSHOT_REPOSITORY"' in package and '"${repository[@]}"' in package,
          "launcher/scripts/package.sh does not stamp HOOKSHOT_REPOSITORY into the program")
    print("launcher repository: %s, as the builder's; stamped from the workflow's repository" % name)


if __name__ == "__main__":
    main()
