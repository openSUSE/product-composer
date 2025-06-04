from .commands import COMMANDS

def dispatch(args):
    cmd_class = COMMANDS.get(args.command)
    if not cmd_class:
        raise ValueError(f"Unknown command: {args.command}")
    cmd_instance = cmd_class()
    cmd_instance.run(args)
