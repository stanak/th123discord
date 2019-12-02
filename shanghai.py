import cogs
from cogs.common.errors import OnlyPrivateMessage

from discord.ext import commands
import discord.utils
import inspect
import logging


logger = logging.getLogger(__name__)


class UserHelpCommand(commands.HelpCommand):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.command_attrs.setdefault('help', 'このメッセージを表示します')

    def get_ending_note(self):
        command_name = self.context.invoked_with
        description = ("helpコマンドでは主に当サーバー特有のコマンドについて説明します。\n"
                       "各チャンネルやサーバーの説明については#informationチャンネルのURLを参照してください。\n"
                       "「{0}{1} 各コマンド名」のように入力するとより詳しい情報が表示されます。"
                       ).format(self.clean_prefix, command_name)
        return description



class Shanghai(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, command_prefix="!", pm_help=True, help_command=UserHelpCommand(), **kwargs)

    async def send_command_help(self, ctx):
        if ctx.invoked_subcommand is None:
            pages = await self.formatter.format_help_for(ctx, ctx.command)
        else:
            pages = await self.formatter.format_help_for(ctx, ctx.invoked_subcommand)
        await ctx.send( "\n".join(pages))

    """
    events
    """
    async def on_ready(self):
        logger.info("on ready...")

    async def on_command_error(self, ctx, exception):
        if isinstance(exception, commands.CommandNotFound):
            await ctx.channel.send("コマンドが存在しません。")
        elif isinstance(exception,
                        (commands.MissingRequiredArgument,
                         commands.TooManyArguments,
                         commands.CheckFailure)):
            await self.send_command_help(ctx)
        elif isinstance(exception, commands.BadArgument):
            await ctx.channel.send("不正な入力です。")
        elif isinstance(exception, commands.NoPrivateMessage):
            await ctx.channel.send("このコマンドはDMでは利用できません。")
        elif isinstance(exception, OnlyPrivateMessage):
            await ctx.author.send("このコマンドはDMからのみ利用できます。")
        elif isinstance(exception, commands.DisabledCommand):
            await ctx.channel.send("このコマンドは無効化されています。")
        elif isinstance(exception, commands.CommandOnCooldown):
            await ctx.channel.send("投稿間隔が短すぎます。")
            logger.exception(type(exception).__name__, exc_info=exception)
        elif isinstance(exception, commands.CommandInvokeError):
            await ctx.channel.send("コマンド呼び出しに失敗しました。")
            logger.exception(type(exception.original).__name__, exc_info=exception.original)
        else:
            logger.exception(type(exception).__name__, exc_info=exception)

    async def on_member_join(self, member):
        guild = member.guild
        default_ch = discord.utils.get(guild.channels, id=guild.id)
        information_ch = discord.utils.get(guild.channels, name="information")
        members_count = len(guild.members)
        fmt = ("{0.mention}さん、ようこそ{1.name}サーバーへ。\n"
               "あなたは{2}人目の参加者です。\n"
               "サーバー概要は{3.mention}を御覧ください。\n"
               "コマンドについて分からないことがあれば「!help」と入力してみてください。上海が伺います。")
        await default_ch.send(fmt.format(member, guild, members_count, information_ch))


"""
main
"""


def _get_cog_classes():
    inspected_cogs_classes = inspect.getmembers(cogs, inspect.isclass)
    cog_classes = [c for name, c in inspected_cogs_classes
                   if "Mixin" not in name]
    return cog_classes


def load_cogs(bot):
    cog_classes = _get_cog_classes()
    print(cog_classes)
    for cog_class in cog_classes:
        cog_class.setup(bot)
    return bot

if __name__ == "__main__":
    import os

    logging.basicConfig(
        level=logging.ERROR
    )
    logging.getLogger("cogs").setLevel(logging.DEBUG)
    logging.getLogger("__main__").setLevel(logging.DEBUG)

    token = os.environ["DISCORD_TOKEN"]
    bot = Shanghai()
    bot = load_cogs(bot)
    bot.run(token)
