from discord import Message,Embed,ApplicationContext,Permissions,PermissionOverwrite,Option as option,Role,Member
from discord.ext.commands import Cog,slash_command
from views.encounter import encounter_view
from json import loads,dumps
from os.path import exists
from random import shuffle
from asyncio import Event
from main import client


class commands(Cog):
	def __init__(self,client:client) -> None:
		self.client = client
		self.question_cache = {}
		if exists('save.json'):
			with open('save.json','r') as file: save:dict = loads(file.read())
		else: save = {}
		self._guild_id = save.get('guild_id',None)
		self._question_channel_id = save.get('question_id',None)
		self._archive_question_id = save.get('archive_question_id',None)
		self._game_broadcast_id = save.get('game_broadcast_id',None)
		self._session_role_id = save.get('session_role_id',None)
		self._player_role_id = save.get('player_role_id',None)
		self._encounter_category_id = save.get('encounter_category_id',None)
		self._team_ids = save.get('team_ids',None)
	
	def save(self):
		with open('save.json','w') as file:
			file.write(dumps({
				'guild_id':self._guild_id,
				'question_id':self._question_channel_id,
				'archive_question_id':self._archive_question_id,
				'game_broadcast_id':self._game_broadcast_id,
				'session_role_id':self._session_role_id,
				'player_role_id':self._player_role_id,
				'encounter_category_id':self._encounter_category_id,
				'team_ids':self._team_ids
				},indent=2))

	@Cog.listener()
	async def on_ready(self):
		self.question_channel,self.game_broadcast,self.archive_question,self.session_role,self.teams = None,None,None,None,None
		# on ready, reconstruct objects from saved ids
		if self._guild_id is not None:
			self.guild = self.client.get_guild(self._guild_id) or self.client.fetch_guild(self._guild_id)

		if self._question_channel_id is not None:
			self.question_channel = self.client.get_channel(self._question_channel_id) or await self.client.fetch_channel(self._question_channel_id)

		if self._archive_question_id is not None:
			self.archive_question = self.client.get_channel(self._archive_question_id) or await self.client.fetch_channel(self._archive_question_id)

		if self._game_broadcast_id is not None:
			self.game_broadcast = self.client.get_channel(self._game_broadcast_id) or await self.client.fetch_channel(self._game_broadcast_id)

		if self._session_role_id is not None:
			self.session_role = self.guild.get_role(self._session_role_id)

		if self._player_role_id is not None:
			self.player_role = self.guild.get_role(self._player_role_id)

		if self._encounter_category_id is not None:
			self.encounter_category = self.guild.get_channel(self._encounter_category_id)

		if self.question_channel is not None:
			self.gm_category = self.question_channel.category

		if self.game_broadcast is not None:
			self.game_category = self.game_broadcast.category

		if self.archive_question is not None:
			self.archive_category = self.archive_question.category

		if self._team_ids is not None:
			self.teams = [self.guild.get_role(role_id) for role_id in self._team_ids]


	@Cog.listener()
	async def on_message(self,message:Message):
		if message.author == self.client.user: return
		if message.reference is None: return
		if self.question_cache.get(message.reference.message_id,None) is None: return

		self.question_cache[message.reference.message_id]['res'] = message
		self.question_cache[message.reference.message_id]['flag'].set()

	@slash_command(
		name='init',
		description='m8',
		guild_only=True,default_member_permissions=Permissions(administrator=True),
		options=[
			option(Role,name='players',description='general player role'),
			option(Role,name='spectators',description='role for users not playing, can view all team channels',default=None),
			option(int,name='players_per_team',description='number of players on each team',default=2)])
	async def slash_init(self,ctx:ApplicationContext,players:Role,spectators:Role,ppt:int):
		# error if players role has odd number of players
		if len(players.members)%ppt:
			await ctx.response.send_message('fuk you buitasdfch youj ainr t got arasirtfgh',ephemeral=True)
			return
		if int(len(players.members)/ppt) > 25:
			await ctx.response.send_message(f'there cannot be more than 25 total teams, because discord.\nthere are currently {int(len(players.members)/ppt)}')
			return
		await ctx.response.defer(ephemeral=True)

		# set active guild to current
		self._guild_id = ctx.guild.id
		self.guild = ctx.guild

		self.session_role = await ctx.guild.create_role(name='session in progress')
		self._session_role_id = self.session_role.id

		self.player_role = players
		self._player_role_id = self.player_role.id

		# create category overwrites
		category_overwrites = {
			ctx.guild.default_role:PermissionOverwrite(view_channel=False,send_messages=False),
			self.session_role:PermissionOverwrite(send_messages=False)
			}
		if spectators is not None: category_overwrites.update({spectators:PermissionOverwrite(view_channel=True)})

		# create GM category and questions channel
		self.gm_category = await ctx.guild.create_category('GM',overwrites=category_overwrites)
		self.question_channel = await self.gm_category.create_text_channel('questions',topic='all player questions will be sent here.\nreply to them with the native discord reply method.')
		self._question_channel_id = self.question_channel.id

		# create encounter category
		self.encounter_category = await ctx.guild.create_category('encounters',overwrites=category_overwrites)
		self._encounter_category_id = self.encounter_category.id

		# create game category and broadcast channel
		self.game_category = await ctx.guild.create_category('eldritchGAME',
			overwrites={
				ctx.guild.default_role:PermissionOverwrite(view_channel=False,send_messages=False),
				players:PermissionOverwrite(view_channel=False),
				})
		self.game_broadcast = await self.game_category.create_text_channel('broadcast',overwrites={players:PermissionOverwrite(view_channel=True,send_messages=False)})
		self._game_broadcast_id = self.game_broadcast.id

		# create archive category and questions channel
		self.archive_category = await ctx.guild.create_category('archive',overwrites=category_overwrites)
		self.archive_question = await self.archive_category.create_text_channel('questions',topic='past questions will be sent to this channel along with their responses.')
		self._archive_question_id = self.archive_question.id

		# duplicate list of players and create a blank teams role
		player_list = players.members
		teams:dict[int,list[Member]] = {}
		shuffle(player_list)

		# establish a team key and list of random players
		for i in range(int(len(player_list)/ppt)):
			teams.update({i:[player_list.pop(0) for p in range(ppt)]})

		# create team roles and assign them to players
		self._team_ids,self.teams = [],[]
		for role_index,team_members in teams.items():
			# create team role
			role = await ctx.guild.create_role(name=f'team-{role_index}')
			self._team_ids.append(role.id)
			self.teams.append(role)

			# give team role to players
			for member in team_members:
				await member.add_roles(role)

			# create channel with role perms
			channel_overwrites = self.game_category.overwrites
			channel_overwrites.update({
				role:PermissionOverwrite(view_channel=True),
				self.session_role:PermissionOverwrite(send_messages=False)})
			await self.game_category.create_text_channel(name=f'team-{role_index}',overwrites=channel_overwrites)

		# save variables to a file
		self.save()

		await ctx.followup.send('successfully initialized game\n use /session start to start the game.',ephemeral=True)

	@slash_command(
		name='question',
		description='ask a question',
		guild_only=True,
		options=[
			option(str,name='question',description='question to be asked',max_length=1970)])
	async def slash_question(self,ctx:ApplicationContext,question:str):
		# check if the question channel exists
		if self.question_channel is None or self.archive_question is None:
			await ctx.response.send_message('error: the question channels have not been initialized',ephemeral=True)
			return

		# send questions channel
		q_embed = Embed(title='question',description=question,color=0x69ff69)
		q_embed.set_author(name=ctx.author.display_name,icon_url=ctx.author.display_avatar.url)
		msg = await self.question_channel.send(embed=q_embed)

		# create watch event and wait for reply
		self.question_cache.update({msg.id:{'res':None,'flag':Event()}})
		await ctx.response.send_message('awaiting response...',ephemeral=True)
		await self.question_cache[msg.id]['flag'].wait()

		# get response
		response = self.question_cache.pop(msg.id,{}).get('res',None)
		if response is None:
			await ctx.followup.send('failed to retrieve response message.',ephemeral=True)
			return

		# send response message
		await ctx.followup.send(response.content,ephemeral=True)

		# send question and response to archive channel
		embed = Embed(title='question archive',description=ctx.author.mention,color=0x69ff69)
		embed.set_author(name=ctx.author.display_name,icon_url=ctx.author.display_avatar.url)
		embed.add_field(name=f'question <t:{int(msg.created_at.timestamp())}:t>',value=question,inline=True)
		embed.add_field(name=f'response <t:{int(response.created_at.timestamp())}:t>',value=response.content,inline=True)
		msg = await self.archive_question.send(embed=embed)

	@slash_command(
		name='session',
		description='start or end a session',
		guild_only=True,default_member_permissions=Permissions(administrator=True),
		options=[
			option(str,name='action',description='pick one bitch',choices=['start','end'])])
	async def slash_session(self,ctx:ApplicationContext,action:str):
		match action:
			case 'start':
				for player in self.player_role.members:
					await player.add_roles(self.session_role)
				await ctx.response.send_message('successfully started session.',ephemeral=True)
			case 'end':
				for player in self.player_role.members:
					await player.remove_roles(self.session_role)
				await ctx.response.send_message('successfully ended session.',ephemeral=True)
			case _: await ctx.response.send_message('u wot m8?')

	@slash_command(name='encounter',
		description='open the encounter menu',
		guild_only=True)
	async def slash_encounter(self,ctx:ApplicationContext) -> None:
		embed = Embed(title='encounter!',color=0x69ff69)
		await ctx.response.send_message(embed=embed,
		view=encounter_view(
			client=self.client,
			embed=embed,
			teams=self.teams,
			encounter_category=self.encounter_category,
			archive_category=self.archive_category),
			ephemeral=True)

def setup(client:client) -> None:
	client.add_cog(commands(client))