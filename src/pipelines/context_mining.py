"""Legacy graph and CLI wrapper; prefer :mod:`code_engine.graph.context_mining`."""

from code_engine.graph.context_mining import *  # noqa: F401,F403
from code_engine.graph.context_mining import main


if __name__ == "__main__":
    main()
