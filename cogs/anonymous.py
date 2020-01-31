from .cogmixin import CogMixin
from .common import checks
from discord.ext import commands
import discord
import random
import string
from datetime import date


def get_anonymous_ch(bot):
    return discord.utils.get(bot.get_all_channels(), name="anonymous")


def get_id():
    randlst = [random.choice(string.ascii_letters + string.digits) for i in range(6)]
    return ''.join(randlst)


class Anonymous(CogMixin, commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.author2id = {}
        self.day = date.today()

    def update_aid(self):
        now = date.today()
        if self.day < now:
            self.day = now
            self.author2id = {}

    @commands.command(
        name="a"
    )
    async def anonymous(self, ctx, *comment):
        """
        #anonymousに匿名(毎日変わるID付き)でメッセージを送信します。どこからでも利用可。
        過激な発言はご遠慮ください。問題発生時のみ、管理者が特定の上警告します。
        """
        await ctx.message.delete()
        self.update_aid()
        author = ctx.message.author
        if author not in self.author2id:
            aid = get_id()
            while aid in self.author2id.values():
                aid = get_id()
            self.author2id[author] = aid

        ch = get_anonymous_ch(self.bot)
        await ch.send(f'{self.author2id[author]}: {" ".join(comment)}')


    @checks.only_private()
    @checks.is_manager()
    @commands.command()
    async def check_ids(self, ctx, aid):
        self.update_aid()
        author = [key for key, value in self.author2id.items() if value == aid]
        if author:
            author = author[0]
        else:
            author = 'not found'
        await ctx.send(author)
