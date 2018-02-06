from discord.ext import commands


def _check_manager(ctx):
    channel = ctx.message.channel
    if channel.is_private:
        return False
    return "manager" in map(str, ctx.message.author.roles)

def is_manager():
    return commands.check(_check_manager)
