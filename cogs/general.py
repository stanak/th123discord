from .cogmixin import CogMixin
from .common import checks
from discord.ext import commands
import discord
from discord.enums import ServerRegion
import random


class General(CogMixin):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def roll(self, dice: str):
        """
        NdNダイスを振った結果を出します。
        6面ダイスを2回振る例「!role 2d6」
        試行回数とダイスは100以下に制限されます。
        """
        try:
            rolls, limit = map(int, dice.split('d'))
        except Exception:
            self.bot.say("「!roll {試行回数}d{ダイスの面数}」の書式で投稿してください。")
        result = [random.randint(1, limit) for r in range(rolls)]
        sum_res = sum(result)
        average = sum_res / len(result)
        expected = sum(range(limit+1)) / limit * rolls
        page = ', '.join(str(r) for r in result)
        await self.bot.say("sum:{0}, ave:{1:.2f}, exp:{2:.2f}\n{3}".format(sum_res, average, expected, page))

    @commands.command(
        pass_context=True
    )
    async def choose(self, ctx, *choices: str):
        """
        スペース区切りの候補からランダムで1つ選びます。
        1人をランダムに選ぶ例「!choose alice iku utsuho」
        """
        author = ctx.message.author
        await self.bot.say(f"{author.mention}, {random.choice(choices)}")

    @commands.command(
        pass_context=True
    )
    async def region(self, ctx, region: str=None):
        """
        サーバリージョンを変更します。現在リージョン確認は「!region」、推奨リージョンは「!help region」から。
        サーバーリージョンを日本に変更する例「!region japan」
        推奨リージョン一覧
        japan
        hongkong
        singapore
        """
        server = ctx.message.server
        if region is None:
            await self.bot.say(f"現在のサーバーリージョンは{server.region}です")
        else:
            try:
                await self.bot.edit_server(server, region=region)
            except Exception as e:
                raise commands.BadArgument
            await self.bot.say(f"サーバーリージョンを{region}に変更しました。")
