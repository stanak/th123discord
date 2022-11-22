import cogs
from cogs.common.errors import OnlyPrivateMessage

from discord.ext import commands
import discord.utils
import inspect
import logging


logger = logging.getLogger(__name__)

information_ch = discord.utils.get(guild.channels, name="ご利用案内・ルール")

class UserHelpCommand(commands.DefaultHelpCommand):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.command_attrs['help'] =  'このメッセージを表示します。'

    def get_ending_note(self):
        description = ("helpコマンドでは主に当サーバー特有のコマンドについて説明します。\n"
                       "各チャンネルやサーバーの説明については#{information}チャンネルのURLを参照してください。\n"
                       "「{prefix}help 各コマンド名」のように入力するとより詳しい情報が表示されます。"
                       ).format(information=information_ch.name, prefix=self.clean_prefix)
        return description



class Shanghai(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, command_prefix="!", help_command=UserHelpCommand(dm_help=True, sort_commands=False), **kwargs)


    """
    events
    """
    async def on_ready(self):
        logger.info("on ready...")
        await information_ch.delete_messages(*(await information_ch.history(limit=5)))
        info_str = ("**[このサーバーは、どんなサーバー？]**\n"
"非相天則の対戦やイベントはもちろん、雑談や、偶には他ゲームの話題まで、「非想天則で得られたつながり」をベースに幅広く活動しています。 天則を始めてみたい方から、昔やっていた方まで、誰でも歓迎です。\n\n"
"**[ざっくり案内]**\n"
"対戦したい -> #募集リスト-hostlist にBot募集の使い方が書かれているので、指示にしたがってください。対戦後の挨拶は #挨拶・感想-say-gg へ\n"
"初心者です -> #初心者・初級者交流 に仲間がいるかも？(beginner role coming soon)\n"
"天則で真面目に語り合いたい -> #天則雑談 や #アドバイス募集 各キャラch へ\n"
"他のことがしたい -> なんでもあり雑談, 又は「!ch list」を入力すると…？(整理予定)\n\n"
"**[注意事項]**\n"
"皆さんが快適に過ごせるように、以下の項目については注意・警告・BAN対象となる場合があります。お気をつけ下さい。またそれらについて困っている場合も運営にご相談下さい。\n"
"・公序良俗に反するもの\n"
"・ハラスメント行為\n"
"・クラッキング行為\n"
"・その他公共の利益に反するもの\n\n"
"**[お問い合わせ]**\n"
"オープンな要件については #質問・要望 にお願いします。それ以外で管理者にクローズな連絡を取る必要がある場合、@MANAGER 役職の誰かへメッセージ(DM)を送信してください。大体midoristが対応早いです。")

        await information_ch.send(info_str)

    async def on_command_error(self, ctx, exception):
        if isinstance(exception, commands.CommandNotFound):
            await ctx.channel.send("コマンドが存在しません。")
        elif isinstance(exception,
                        (commands.MissingRequiredArgument,
                         commands.TooManyArguments,
                         commands.CheckFailure)):
            await ctx.send_help()
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
            logger.exception(f"{ctx.message.author.mention}: {ctx.command.qualified_name}")
            logger.exception(type(exception).__name__, exc_info=exception)

    async def on_member_join(self, member):
        guild = member.guild
        default_ch = discord.utils.get(guild.channels, id=guild.id)
        members_count = len(guild.members)
        fmt = ("{0.mention}さん、ようこそ{1.name}サーバーへ。\n"
               "あなたは{2}人目の参加者です。\n"
               "サーバー概要は{3.mention}を御覧ください。\n"
               "コマンドについて分からないことがあれば「!help」と入力してみてくださいと言いたいところですが、現在色々工事中です。")
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
        format="[%(levelname)s] %(message)s",
        datefmt="%m/%d/%Y %I:%M:%S %p"
    )
    logging.getLogger("cogs").setLevel(logging.DEBUG)
    logging.getLogger("__main__").setLevel(logging.DEBUG)

    token = os.environ["DISCORD_TOKEN"]
    bot = Shanghai(intents=discord.Intents.all())
    bot = load_cogs(bot)
    bot.run(token)
