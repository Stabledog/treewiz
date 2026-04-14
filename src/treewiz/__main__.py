"""Entry point: python -m treewiz, or `treewiz` console script."""

import sys
from pathlib import Path


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print("Usage: treewiz <other-tree>")
        print("       treewiz <tree-a> <tree-b>")
        sys.exit(0 if args else 1)

    if len(args) == 1:
        left = Path.cwd()
        right = Path(args[0]).resolve()
    elif len(args) == 2:
        left = Path(args[0]).resolve()
        right = Path(args[1]).resolve()
    else:
        print("treewiz: expected 1 or 2 arguments", file=sys.stderr)
        sys.exit(1)

    for p in (left, right):
        if not p.is_dir():
            print(f"treewiz: not a directory: {p}", file=sys.stderr)
            sys.exit(1)

    from treewiz.tui.app import TreewizApp

    app = TreewizApp(left_root=left, right_root=right)
    app.run()


if __name__ == "__main__":
    main()
