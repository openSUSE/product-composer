from .commands import COMMANDS

def dispatch(args):
    print(COMMANDS)
    cmd_class = COMMANDS.get(args.command)
    print(args.command)
    if not cmd_class:
        raise ValueError(f"Unknown command: {args.command}")
    cmd_instance = cmd_class()
    cmd_instance.run(args)