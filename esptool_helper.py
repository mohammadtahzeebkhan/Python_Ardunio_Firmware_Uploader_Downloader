"""Standalone esptool CLI entry point, packaged as its own executable.

main.py is built as a onefile exe, so `sys.executable` inside the frozen app
points at main.exe itself -- it can't be re-invoked as `-m esptool`. This
wrapper is built into a sibling exe (see main.spec) that flash_utils.py
shells out to instead, when running frozen.
"""
from esptool import main

if __name__ == "__main__":
    main()
