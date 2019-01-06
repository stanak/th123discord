from .cogmixin import CogMixin
from .common import checks
from discord.ext import commands
import discord
import logging

logger = logging.getLogger(__name__)

"""通常チャンネル・隠れチャンネルの権限"""
_visible_overwrite = {
    "add_reactions": True,
    "read_messages": True,
    "send_messages": True,
    "send_tts_messages": None,
    "manage_messages": None,
    "embed_links": True,
    "attach_files": True,
    "read_message_history": True,
    "mention_everyone": True,
    "external_emojis": True
    }

_hidden_overwrite = {
    "add_reactions": False,
    "read_messages": False,
    "send_messages": False,
    "send_tts_messages": None,
    "manage_messages": None,
    "embed_links": False,
    "attach_files": False,
    "read_message_history": False,
    "mention_everyone": False,
    "external_emojis": False
    }

VISIBLE_OVERWRITE = discord.PermissionOverwrite(**_visible_overwrite)
HIDDEN_OVERWRITE = discord.PermissionOverwrite(**_hidden_overwrite)

def _is_hidden(channel: discord.TextChannel):
    everyone_overwrite = channel.overwrites_for(
        channel.guild.default_role)
    visible = everyone_overwrite.read_messages
    if visible is None:
        return False
    return not visible


class HiddenChannel(CogMixin):
    def __init__(self, bot):
        self.bot = bot

    @commands.group()
    async def ch(self, ctx):
        """
        主に隠れチャンネルに対する操作全般を行います。
        サブコマンドと合わせて使用します。
        joinの使用例「!ch join <channel_name>」
        """
        pass

    @ch.command(
        name="join",
    )
    async def _join_channel(self, ctx, hidden_channel: discord.TextChannel):
        """
        入室を行います。
        隠れチャンネル#devへ入室する例「!ch join dev」
        DMから利用不可。
        """
        my_permission = hidden_channel.permissions_for(ctx.author)
        my_overwrite = hidden_channel.overwrites_for(ctx.author)
        visible = my_permission.read_messages
        if not visible and my_overwrite.is_empty():
            # 隠れch("everyoneのみ"不可視指定) -> overwriteで可視化
            if all([r.is_default() for r in hidden_channel.changed_roles]):
                await hidden_channel.set_permissions(ctx.author, overwrite=VISIBLE_OVERWRITE)
                await ctx.send("{0.name}に入室しました。".format(hidden_channel), delete_after=10)
                return
            # 役職限定ch(everyone不可視、特定の役職可視) -> 不正入力扱い
            else:
                raise commands.BadArgument
        #隠れチャンネルではない又は入室済み
        await ctx.send("このチャンネルには入室済みです。", delete_after=10)

    @ch.command(
        name="leave",
    )
    async def _leave_channel(self, ctx, hidden_channel: discord.TextChannel):
        """
        退室を行います。
        隠れチャンネル#devを退室する例「!ch leave dev」
        DMから利用不可。
        """
        permission = hidden_channel.permissions_for(ctx.author)
        visible = permission.read_messages
        overwrite = hidden_channel.overwrites_for(ctx.author)
        if visible and not overwrite.is_empty():
            await hidden_channel.set_permissions(ctx.author, overwrite=None)
            await ctx.send("{0.name}を退室しました。".format(hidden_channel), delete_after=10)
        else:
            raise commands.BadArgument

    @ch.command(
        name="count",
    )
    async def _count_members(self, ctx, hidden_channel: discord.TextChannel):
        """
        参加者数を表示します。
        隠れチャンネル#devの参加者数を表示する例「!ch count dev」
        """
        # 単純な実装でoverwrites-1(everyone)を表示するので、役職専用チャンネルでは正確な値がでない。
        if _is_hidden(hidden_channel):
            await ctx.send(
                "{0.name}の参加者総数は{1}人です。"
                .format(hidden_channel, len(hidden_channel.overwrites) - 1))
        else:
            await ctx.send(
                "{0.name}は隠れチャンネルではありません。".format(hidden_channel))

    @ch.command(
        name="list",
    )
    async def _shown_channels(self, ctx):
        """
        隠れチャンネルの一覧を表示します。
        使用例「!ch list」
        """
        hidden_channels = [channel for channel in self.bot.get_all_channels()
                           if _is_hidden(channel)]
        output = []
        if hidden_channels:
            for channel in sorted(hidden_channels, key=lambda x:x.position):
                name = channel.name
                topic = channel.topic if channel.topic is not None else ""
                page = "{0}:{1}人\n  {2}".format(name, len(channel.overwrites)-1, topic)
                output.append(page)
            await ctx.send("```" + "\n".join(output) + "```")
        else:
            await ctx.send("隠れチャンネルが見つかりません。")

    @commands.command(
        name="mkhidden",
    )
    @checks.is_manager()
    async def _make_hidden_channel(self, ctx, channel_name: str):
        """
        隠れチャンネルを作成します。
        使用例「!mkhidden new_channel_name」
        """
        overwrites = {ctx.guild.default_role:HIDDEN_OVERWRITE}
        await ctx.guild.create_text_channel(channel_name, overwrites=overwrites)
