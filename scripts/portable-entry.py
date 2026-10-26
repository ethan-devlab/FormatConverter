import multiprocessing
import os
import sys

# Windowless Windows processes have no standard streams. Native libraries and
# logging formatters still expect writable stream objects, including in workers.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from server.format_converter.__main__ import main
    main()
