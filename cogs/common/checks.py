from discord.ext import commands
from .errors import OnlyPrivateMessage


def _check_manager(ctx):
    channel = ctx.message.channel
    if channel.is_private:
        return False
    return "manager" in map(str, ctx.message.author.roles)

def is_manager():
    return commands.check(_check_manager)

def _check_private(ctx):
    channel = ctx.message.channel
    if not channel.is_private:
        raise OnlyPrivateMessage
    return True

def only_private():
    return commands.check(_check_private)
