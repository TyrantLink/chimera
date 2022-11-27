#!./venv/bin/python3.10
from time import perf_counter
st = perf_counter()
from discord import ApplicationContext,Interaction,ApplicationCommandInvokeError,Intents
from traceback import format_exc,format_tb
from discord.errors import CheckFailure
from discord.ext.commands import Bot
from datetime import datetime

try:
	with open('nottoken') as file:
		TOKEN = file.readlines(1)[0]
except FileNotFoundError:
	with open('nottoken','w') as file:
		file.write('put your token in this file')
	exit('please add your token to the nottoken file')

class client(Bot):
	def __init__(self) -> None:
		super().__init__('i lika, do, da c00ba',None,intents=Intents.all())
		self.load_extension('extensions.commands')

	async def on_ready(self) -> None:
		print(f'[{datetime.now().strftime("%m/%d/%Y %H:%M:%S")}] [INFO] {self.user.name} connected to discord in {round(perf_counter()-st,2)} seconds')
		await self.sync_commands()

	async def on_application_command_completion(self,ctx:ApplicationContext) -> None:
		print(f'[{datetime.now().strftime("%m/%d/%Y %H:%M:%S")}] [COMMAND] {ctx.author} ran {ctx.command.qualified_name}')

	async def on_unknown_application_command(self,interaction:Interaction):
		await interaction.response.send_message('u wot m8?',ephemeral=True)

	async def on_command_error(self,ctx:ApplicationContext,error:Exception) -> None:
		if isinstance(error,CheckFailure): return
		print("".join(format_tb(error.__traceback__)))

	async def on_application_command_error(self,ctx:ApplicationContext,error:ApplicationCommandInvokeError) -> None:
		if isinstance(error,CheckFailure): return
		await ctx.respond(f'an error has occurred: {error}\n\nthe issue has been automatically reported and should be fixed soon.',ephemeral=True)
		print("".join(format_tb(error.original.__traceback__)))

	async def on_error(self,event:str,*args,**kwargs):
		print(format_exc())


client().run(TOKEN)