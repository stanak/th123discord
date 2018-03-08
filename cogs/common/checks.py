from discord.ext import commands
from . import errors


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
        raise errors.OnlyPrivateMessage
    return True


def only_private():
    return commands.check(_check_private)


def _check_not_private(ctx):
    channel = ctx.message.channel
    if channel.is_private:
        raise commands.NoPrivateMessage
    return True


def no_private():
    return commands.check(_check_not_private)
