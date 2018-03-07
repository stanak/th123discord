import cogs
from cogs.common.errors import OnlyPrivateMessage

from discord.ext import commands
import discord.utils
import inspect
import logging


logger = logging.getLogger(__name__)


class Shanghai(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, command_prefix="!", pm_help=True, **kwargs)

    async def send_command_help(self, ctx):
        if ctx.invoked_subcommand is None:
            pages = self.formatter.format_help_for(ctx, ctx.command)
        else:
            pages = self.formatter.format_help_for(ctx, ctx.invoked_subcommand)
        await self.send_message(ctx.message.channel, "\n".join(pages))

    """
    events
    """
    async def on_ready(self):
        logger.info("on ready...")

    async def on_command_error(self, exception, ctx):
        channel = ctx.message.channel
        user = ctx.message.author
        if isinstance(exception, commands.CommandNotFound):
            await self.send_message(channel, "コマンドが存在しません。")
        elif isinstance(exception,
                        (commands.MissingRequiredArgument,
                         commands.TooManyArguments,
                         commands.CheckFailure)):
            await self.send_command_help(ctx)
        elif isinstance(exception, commands.BadArgument):
            await self.send_message(channel, "不正な入力です。")
        elif isinstance(exception, commands.NoPrivateMessage):
            await self.send_message(channel, "このコマンドはDMでは利用できません。")
        elif isinstance(exception, OnlyPrivateMessage):
            await self.send_message(user, "このコマンドはDMからのみ利用できます。")
        elif isinstance(exception, commands.DisabledCommand):
            await self.send_message(channel, "このコマンドは無効化されています。")
        elif isinstance(exception, commands.CommandOnCooldown):
            await self.send_message(channel, "投稿間隔が短すぎます。")
            logger.exception(type(exception).__name__, exc_info=exception)
        elif isinstance(exception, commands.CommandInvokeError):
            await self.send_message(channel, "コマンド呼び出しに失敗しました。")
            logger.exception(type(exception.original).__name__, exc_info=exception.original)
        else:
            logger.exception(type(exception).__name__, exc_info=exception)

    async def on_member_join(self, member):
        server = member.server
        information_ch = discord.utils.get(server.channels,
                                           name="information")
        members_count = len(server.members)
        fmt = ("{0.mention}さん、ようこそ{1.name}サーバーへ。\n"
               "あなたは{2}人目の参加者です。\n"
               "サーバー概要は{3.mention}を御覧ください。\n"
               "コマンドについて分からないことがあれば「!help」と入力してみてください。上海が伺います。")
        await self.send_message(server,
                                fmt.format(member, server,
                                           members_count, information_ch))


"""
main
"""


def _get_cog_classes(cog_names):
    inspected_cogs_classes = inspect.getmembers(cogs, inspect.isclass)
    cog_classes = [c for name, c in inspected_cogs_classes
                   if name in cog_names and "Mixin" not in name]
    return cog_classes


def load_cogs(bot, cog_names):
    cog_classes = _get_cog_classes(cog_names)
    for cog_class in cog_classes:
        cog_class.setup(bot)
    return bot

class Formatter(commands.HelpFormatter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def shorten(self, text):
        # 完全にダメだけどとりいそぎ
        if text.startswith("  help"):
            text = "  help     このメッセージを表示します。"
        return super().shorten(text)

    def get_ending_note(self):
        command_name = self.context.invoked_with
        description = ("helpコマンドでは主に当サーバー特有のコマンドについて説明します。\n"
                       "各チャンネルやサーバーの説明については#informationチャンネルのURLを参照してください。\n"
                       "「{0}{1} 各コマンド名」のように入力するとより詳しい情報が表示されます。"
                       ).format(self.clean_prefix, command_name)
        return description


if __name__ == "__main__":
    import os

    logging.basicConfig(
        level=logging.ERROR
    )
    logging.getLogger("cogs").setLevel(logging.DEBUG)
    logging.getLogger("__main__").setLevel(logging.DEBUG)

    token = os.environ["DISCORD_TOKEN"]
    cog_names = ["General", "HiddenChannel", "Manager", "Hosting", "Role"]
    bot = Shanghai(formatter=Formatter())
    bot = load_cogs(bot, cog_names)
    bot.run(token)
