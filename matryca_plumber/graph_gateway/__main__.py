"""Enter the standard-library bootstrap before application imports."""

from .bootstrap import main

if __name__ == "__main__":
    raise SystemExit(main())
