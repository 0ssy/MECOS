"""
Root entrypoint for MECOS domain expansion.

Delegates to the package implementation in `mecos.domain_expansion`
so running from repository root works:

    python domain_expansion.py --status
    python domain_expansion.py --fast
"""

from mecos.domain_expansion import main


if __name__ == "__main__":
    main()
