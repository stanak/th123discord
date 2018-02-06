from .cogmixin import CogMixin
from discord.ext import commands
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
        result = ', '.join(str(random.randint(1, limit)) for r in range(rolls))
        await self.bot.say(result)

    @commands.command()
    async def choose(self, *choices: str):
        """
        スペース区切りの候補からランダムで1つ選びます。
        1人をランダムに選ぶ例「!choose alice iku utsuho」
        """
        await self.bot.say(random.choice(choices))
