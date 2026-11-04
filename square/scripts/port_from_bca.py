r"""What it is:   The porting tool from bca-oslo.
What it does: Brings changes from the bca-oslo repo into square/ with a 3-way merge per file; only reads the bca repo.
How to run:   python square/scripts/port_from_bca.py <base> <theirs> [--apply] (dry run without --apply).
Read before:  docs/setup/19-square-app.md section 'Porting from bca-oslo' and docs/setup/16-bca-oslo-reuse.md.
Read after:   Resolve conflicts, chain new migrations, run the square tests, record the new base in docs/MEMORY.md.

Port changes from the bca-oslo repo into square/ with a 3-way merge per file (W13-R52, guide 19 section "Porting from bca-oslo").

    python square/scripts/port_from_bca.py <base> <theirs> [--apply]

<base>   the bca-oslo commit the square was last in step with (the first time: d937d1d; after W13-R52: cbdebf4; after W16-R3: ffa0802)
<theirs> the bca-oslo commit to bring in (for example master)
Without --apply it only says what it would do. Per file under backend/ and frontend/ that changed between base and theirs:
  NEW       not in the square: written as it is
  COPIED    the square still has the base version: replaced by theirs
  MERGED    the square changed it too and the changes do not touch: both kept
  CONFLICT  both changed the same lines: the file gets <<<<<<< markers, resolve by hand (the square keeps its module flags and wording)
Only reads the bca repo (git show / diff); never opens its .env files. After merging: chain any new migration onto the square's own alembic
head, run the square's tests and vue-tsc, then record the new base commit in docs/MEMORY.md."""
import os
import subprocess
import sys
import tempfile

BCA = r'C:\diPpY_devLocal\Digital\Master_BCA_Oslo\bca_oslo'
SQUARE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


def git(*args: str) -> bytes:
    return subprocess.run(['git', '-C', BCA, *args], capture_output=True).stdout  # a file that did not exist at that commit gives b''


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    base, theirs, apply = sys.argv[1], sys.argv[2], '--apply' in sys.argv
    files = [f for f in git('diff', '--name-only', base, theirs).decode().split('\n') if f.startswith(('backend/', 'frontend/'))]
    for f in files:
        path = os.path.join(SQUARE, f)
        new = git('show', f'{theirs}:{f}')
        if not os.path.exists(path):
            print('NEW      ', f)
            if apply:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                open(path, 'wb').write(new)
            continue
        old = git('show', f'{base}:{f}')
        ours = open(path, 'rb').read().replace(b'\r\n', b'\n')  # the working tree is CRLF on Windows
        if ours == old:
            print('COPIED   ', f)
            if apply:
                open(path, 'wb').write(new)
            continue
        tmp = tempfile.mkdtemp()
        for name, data in (('ours', ours), ('base', old), ('theirs', new)):
            open(os.path.join(tmp, name), 'wb').write(data)
        merged = subprocess.run(['git', 'merge-file', '-p', '-L', 'square', '-L', 'bca-base', '-L', 'bca-new', *(os.path.join(tmp, n) for n in ('ours', 'base', 'theirs'))], capture_output=True)
        print('MERGED   ' if merged.returncode == 0 else f'CONFLICT{merged.returncode:2d}', f)
        if apply:
            open(path, 'wb').write(merged.stdout)
    if not apply:
        print('(dry run: nothing written; add --apply)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
