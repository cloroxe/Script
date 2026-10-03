import multiprocessing

from uefn_vibe.setup_project import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
