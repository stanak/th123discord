from .cogmixin import CogMixin
from discord.ext import commands
import discord
import requests
import os

import logging

logger = logging.getLogger(__name__)

DEEPL_ENDPOINT = "https://api-free.deepl.com/v2/translate"
AUTH_KEY = os.environ['DEEPL_TOKEN']


def translate(text, target_lang):
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded; utf-8'
    }
    params = {
        'auth_key': AUTH_KEY,
        'text': text,
        'target_lang': target_lang,
    }
    response = requests.post(DEEPL_ENDPOINT,
                             data=params,
                             headers=headers)
    if response.status_code != 200:
        raise Exception
    return response.json()


class Deepl(CogMixin, commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.jp_en_ch = None
        self.en_jp_ch = None

    @commands.Cog.listener(name='on_message')
    async def translate(self, message):
        if message.author.bot:
            return
        if self.jp_en_ch is None:
            self.jp_en_ch = discord.utils.get(self.bot.get_all_channels(), name="jp-en")
            self.jp_en_hook = (await self.jp_en_ch.webhooks())[0]
        if self.en_jp_ch is None:
            self.en_jp_ch = discord.utils.get(self.bot.get_all_channels(), name="en-jp")
            self.en_jp_hook = (await self.en_jp_ch.webhooks())[0]

        if message.channel == self.jp_en_ch:
            try:
                json_response = translate(message.content, "EN")
            except Exception:
                await self.en_jp_ch.send('May be API limit')
                await self.jp_en_ch.send('APILimitかもしれません')
                return
            translated_text = json_response["translations"][0]["text"]
            await self.en_jp_hook.send(content=translated_text,
                                       username=message.author.name,
                                       avatar_url=message.author.avatar_url)
        if message.channel == self.en_jp_ch:
            try:
                json_response = translate(message.content, 'JA')
            except Exception:
                await self.en_jp_ch.send('May be API limit')
                await self.jp_en_ch.send('APILimitかもしれません')
                return
            translated_text = json_response["translations"][0]["text"]
            await self.jp_en_hook.send(content=translated_text,
                                       username=message.author.name,
                                       avatar_url=message.author.avatar_url)
