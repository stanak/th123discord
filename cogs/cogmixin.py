class CogMixin:
    @classmethod
    def setup(cls, bot):
        cog = cls(bot)
        bot.add_cog(cog)

    async def on_ready(self):
        print("load {0}".format(self.__class__.__name__))
