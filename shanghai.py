import cogs
from cogs.common.errors import OnlyPrivateMessage
from discord.ext import commands
import discord.utils
import discord
import inspect
import logging


logger = logging.getLogger(__name__)

class UserHelpCommand(commands.DefaultHelpCommand):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.command_attrs['help'] =  'このメッセージを表示します。'

    def get_ending_note(self):
        description = ("helpコマンドでは主に当サーバー特有のコマンドについて説明します。\n"
                       "各チャンネルやサーバーの説明については #ご利用案内・ルール チャンネルのURLを参照してください。\n"
                       "「{prefix}help 各コマンド名」のように入力するとより詳しい情報が表示されます。"
                       ).format(prefix=self.clean_prefix)
        return description


class Shanghai(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, command_prefix="!", help_command=UserHelpCommand(dm_help=True, sort_commands=False), **kwargs)

    """
    events
    """
    async def on_ready(self):
        logger.info("on ready...")
        guild = self.guilds[0]
        channels = guild.channels
        logger.info(guild.name)
        logger.info(channnels)
        logger.info("-----channels\n" + str([c.name for c in channels].join("\n")))
        logger.info('test')
        ch_list = [('info', 'ご利用案内・ルール'), ('hostlist', '募集リスト-hostlist'), ('say-gg', '挨拶・感想-say-gg'), ('beginner', '初心者・初級者交流'), ('th123', '天則雑談'), ('advice', 'アドバイス募集'), ('servermeta', '質問・要望')]
        ch_mention_dict = dict([(key, discord.utils.get(channels, name=name).mention) for key, name in ch_list])
        logger.info("-----dict_channels\n" + [v.name for k, v in ch_mention_dict.items()].join('\n'))
        manager_role_mention = discord.utils.get(roles, name='MANAGER').mention
        logger.info("-----manage-role\n" + manager_role_mention)

        # 元のメッセージ削除
        information_ch =  discord.utils.get(channels, name='ご利用案内・ルール')
        async for message in information_ch.history(limit=10):
            await message.delete() 

        info_str = ("**[このサーバーについて]**\n"
                    "非相天則の対戦やイベントはもちろん、雑談や、偶には他ゲームの話題まで、「非想天則で得られたつながり」をベースに幅広く活動しています。 天則を始めてみたい方から、昔やっていた方まで、誰でも歓迎です。\n\n"
                    "**[ざっくり案内]**\n"
                    "対戦したい -> {hostlist} にBot募集の使い方が書かれているので、指示にしたがってください。対戦後の挨拶は {say-gg} へ\n"
                    "初心者です -> {beginner} に仲間がいるかも？(beginner role coming soon)\n"
                    "天則で真面目に語り合いたい -> {th123} や {advice} 、サーバー下の方にカテゴリのある各キャラch へ\n"
                    "他のことがしたい -> なんでもあり雑談, 又は「!ch list」を入力すると…？(整理予定)\n\n"
                    "**[注意事項]**\n"
                    "皆さんが快適に過ごせるように、以下の項目については注意・警告・BAN対象となる場合があります。お気をつけ下さい。またそれらについて困っている場合も運営にご相談下さい。\n"
                    "・公序良俗に反するもの\n"
                    "・ハラスメント行為\n"
                    "・クラッキング行為\n"
                    "・その他公共の利益に反するもの\n\n"
                    "**[お問い合わせ]**\n"
                    "オープンな要望等については{servermeta}にお願いします。それ以外で管理者にクローズな連絡を取る必要がある場合、{manager} 役職の誰かへメッセージ(DM)を送信してください。近日中に匿名で意見する方法も用意します。")
        await information_ch.send(info_str.format(**ch_mention_dict, manager=manager_role_mention))

    async def on_command_error(self, ctx, exception):
        logger.exception(f"name:{ctx.message.author.name}, nick:{ctx.message.author.nick}, id:{ctx.message.author.id}, {ctx.command.qualified_name}")
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
        else:
            logger.exception(type(exception).__name__, exc_info=exception)

    async def on_member_join(self, member):
        guild = self.guilds[0]
        channels = guild.channels
        information_ch = discord.utils.get(channels, name='ご利用案内・ルール')
        default_ch = discord.utils.get(channels, name='サーバー玄関口・雑談')
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
        level=logging.ERROR,
        format="[%(levelname)s] %(message)s",
        datefmt="%m/%d/%Y %I:%M:%S %p"
    )
    logging.getLogger("cogs").setLevel(logging.DEBUG)
    logging.getLogger("__main__").setLevel(logging.DEBUG)

    token = os.environ["DISCORD_TOKEN"]
    bot = Shanghai(intents=discord.Intents.all())
    bot = load_cogs(bot)
    bot.run(token)
