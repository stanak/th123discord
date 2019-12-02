from .cogmixin import CogMixin
from .common import checks
from discord.ext import commands
import discord
import random


class General(CogMixin, commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def roll(self, ctx, dice: str):
        """
        NdNダイスを振った結果を出します。
        6面ダイスを2回振る例「!role 2d6」
        試行回数とダイスは100以下に制限されます。
        """
        try:
            rolls, limit = map(int, dice.split('d'))
        except Exception:
            await ctx.send("「!roll {試行回数}d{ダイスの面数}」の書式で投稿してください。")
            return
        result = [random.randint(1, limit) for r in range(rolls)]
        sum_res = sum(result)
        average = sum_res / len(result)
        expected = sum(range(limit+1)) / limit * rolls
        page = ', '.join(str(r) for r in result)
        await ctx.send("sum:{0}, ave:{1:.2f}, exp:{2:.2f}\n{3}".format(sum_res, average, expected, page))

    @commands.command()
    async def choose(self, ctx, *choices: str):
        """
        スペース区切りの候補からランダムで1つ選びます。
        1人をランダムに選ぶ例「!choose alice iku utsuho」
        """
        await ctx.send(f"{ctx.author.mention}, {random.choice(choices)}")

    @commands.command()
    async def region(self, ctx, region: str=None):
        """
        サーバリージョンを変更します。現在リージョン確認は「!region」、推奨リージョンは「!help region」から。
        サーバーリージョンを日本に変更する例「!region japan」
        推奨リージョン一覧
        japan
        hongkong
        singapore
        """
        if region is None:
            await ctx.send(f"現在のサーバーリージョンは{ctx.guild.region}です")
        else:
            try:
                await ctx.guild.edit(region=region)
            except Exception as e:
                raise commands.BadArgument
            await ctx.send(f"サーバーリージョンを{region}に変更しました。")

    @commands.command()
    async def omikuji(self, ctx):
        """
        おみくじを引きます。なんちゃって浅草寺仕様です。
        大吉＞吉＞半吉＞小吉＞末小吉＞末吉＞凶
        例「!omikuji」
        """
        omikuji_map = ["大吉(17%)"] * 17\
                    + ["吉(35%)"] * 35\
                    + ["半吉(5%)"] * 5\
                    + ["小吉(4%)"] * 4\
                    + ["末小吉(3%)"] * 3\
                    + ["末吉(6%)"] * 6\
                    + ["凶(30%)"] * 30
        await ctx.send(random.choice(omikuji_map))

