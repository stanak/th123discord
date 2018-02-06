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

def _is_hidden(channel: discord.Channel):
    everyone_overwrite = channel.overwrites_for(
        channel.server.default_role)
    visible = everyone_overwrite.read_messages
    if visible is None:
        return False
    return not visible


class HiddenChannel(CogMixin):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(
        pass_context=True
    )
    async def ch(self, ctx):
        """
        主に隠れチャンネルに対する操作全般を行います。
        サブコマンドと合わせて使用します。
        joinの使用例「!ch join <channel_name>」
        """
        pass

    @ch.command(
        name="join",
        pass_context=True
    )
    async def _join_channel(self, ctx, hidden_channel: discord.Channel):
        """
        入室を行います。
        隠れチャンネル#devへ入室する例「!ch join dev」
        DMから利用不可。
        """
        message = ctx.message
        member = message.author
        my_permission = hidden_channel.permissions_for(member)
        my_overwrite = hidden_channel.overwrites_for(member)
        visible = my_permission.read_messages
        if not visible and my_overwrite.is_empty():
            # 隠れch("everyoneのみ"不可視指定) -> overwriteで可視化
            if all([r.is_everyone for r in hidden_channel.changed_roles]):
                await self.bot.edit_channel_permissions(hidden_channel, member, VISIBLE_OVERWRITE)
                await self.bot.say("{0.name}に入室しました。".format(hidden_channel))
                return
            # 役職限定ch(everyone不可視、特定の役職可視) -> 不正入力扱い
            else:
                raise commands.BadArgument
        #隠れチャンネルではない又は入室済み
        await self.bot.say("このチャンネルには入室済みです。")

    @ch.command(
        name="leave",
        pass_context=True
    )
    async def _leave_channel(self, ctx, hidden_channel: discord.Channel):
        """
        退室を行います。
        隠れチャンネル#devを退室する例「!ch leave dev」
        DMから利用不可。
        """
        message = ctx.message
        member = message.author
        permission = hidden_channel.permissions_for(member)
        visible = permission.read_messages
        overwrite = hidden_channel.overwrites_for(member)
        if visible and not overwrite.is_empty():
            await self.bot.delete_channel_permissions(hidden_channel, member)
            await self.bot.say("{0.name}を退室しました。".format(hidden_channel))
        else:
            raise commands.BadArgument

    @ch.command(
        name="count",
        pass_context=True
    )
    async def _count_members(self, ctx, hidden_channel: discord.Channel):
        """
        参加者数を表示します。
        隠れチャンネル#devの参加者数を表示する例「!ch count dev」
        """
        # 単純な実装でoverwrites-1(everyone)を表示するので、役職専用チャンネルでは正確な値がでない。
        if _is_hidden(hidden_channel):
            await self.bot.say(
                "{0.name}の参加者総数は{1}人です。"
                .format(hidden_channel, len(hidden_channel.overwrites) - 1))
        else:
            await self.bot.say(
                "{0.name}は隠れチャンネルではありません。".format(hidden_channel))

    @ch.command(
        name="list",
        pass_context=True
    )
    async def _shown_channels(self, ctx):
        """
        隠れチャンネルの一覧を表示します。
        使用例「!ch list」
        """
        server = ctx.message.server
        hidden_channels = [channel for channel in server.channels
                           if _is_hidden(channel)]
        output = []
        if hidden_channels:
            for c in hidden_channels:
                name = c.name
                topic = c.topic if c.topic is not None else ""
                output.append(name + ":\n    " + topic)
            await self.bot.say("```" + "\n".join(output) + "```")
        else:
            await self.bot.say("隠れチャンネルが見つかりません。")

    @commands.command(
        name="mkhidden",
        pass_context=True
    )
    @checks.is_manager()
    async def _make_hidden_channel(self, ctx, channel_name: str):
        """
        隠れチャンネルを作成します。
        使用例「!mkhidden new_channel_name」
        """
        server = ctx.message.server
        everyone_perm = discord.ChannelPermissions(
            target=server.default_role,
            overwrite=HIDDEN_OVERWRITE)
        await self.bot.create_channel(server, channel_name, everyone_perm)
