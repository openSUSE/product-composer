from argparse import ArgumentParser
from productcomposer.config import DEFAULT_EULADIR

def build_parser():
    parser = ArgumentParser('productcomposer')
    #subparsers = parser.add_subparsers(required=True, help='sub-command help')
    subparsers = parser.add_subparsers(dest="command", required=True, help='sub-command help')

    # One sub parser for each command
    verify_parser = subparsers.add_parser('verify', help='Verify the build recipe')
    build_parser = subparsers.add_parser('build', help='Run a product build')

    #verify_parser.set_defaults(func=verify)
    #build_parser.set_defaults(func=build)

    # Generic options
    for cmd_parser in (verify_parser, build_parser):
        cmd_parser.add_argument('-f', '--flavor', help='Build a given flavor')
        cmd_parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
        cmd_parser.add_argument('--reposdir', action='store', help='Take packages from this directory')
        cmd_parser.add_argument('filename', default='default.productcompose', help='Filename of product YAML spec')

    # build command options
    build_parser.add_argument('-r', '--release', default=None, help='Define a build release counter')
    build_parser.add_argument('--disturl', default=None, help='Define a disturl')
    build_parser.add_argument('--build-option', action='append', nargs='+', default=[], help='Set a build option')
    build_parser.add_argument('--vcs', default=None, help='Define a source repository identifier')
    build_parser.add_argument('--clean', action='store_true', help='Remove existing output directory first')
    build_parser.add_argument('--euladir', default=DEFAULT_EULADIR, help='Directory containing EULA data')
    build_parser.add_argument('out', help='Directory to write the result')

    return parser