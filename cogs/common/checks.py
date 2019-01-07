from discord.ext import commands
from . import errors
import discord


def _check_manager(ctx):
    if isinstance(ctx.channel, discord.DMChannel):
        return False
    return "manager" in map(str, ctx.message.author.roles)


def is_manager():
    return commands.check(_check_manager)


def _check_private(ctx):
    if not isinstance(ctx.channel, discord.DMChannel):
        raise errors.OnlyPrivateMessage
    return True


def only_private():
    return commands.check(_check_private)


def _check_not_private(ctx):
    if isinstance(ctx.channel, discord.DMChannel):
        raise commands.NoPrivateMessage
    return True


def no_private():
    return commands.check(_check_not_private)
