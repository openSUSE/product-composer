""" Implementation of the command line interface.

"""

from .core import logger
from .utils.loggerutils import (die)

from . import cliparser
from .dispatcher import dispatch

__all__ = "main",

def main(argv=None) -> int:
    parser = cliparser.build_parser()
    args = parser.parse_args()

    filename = args.filename
    if not filename:
        # No subcommand was specified.
        print("No filename")
        parser.print_help()
        die(None)

    dispatch(args)

    return 0


if __name__ == "__main__":
    try:
        status = main()
    except Exception as err:
        # Error handler of last resort.
        logger.error(repr(err))
        logger.critical("shutting down due to fatal error")
        raise  # print stack trace
    else:
        raise SystemExit(status)

# vim: sw=4 et
