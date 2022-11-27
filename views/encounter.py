from discord import SelectOption,Interaction,Embed,Role,CategoryChannel,PermissionOverwrite
from discord.ui import View,Button,Select,button,Item
from secrets import token_hex


class select_menu(Select):
	def __init__(self,client,options:list[SelectOption]) -> None:
		self.client = client
		super().__init__(
			placeholder='choose teams for the encounter',
			min_values=2,
			max_values=len(options),
			options=options)

	async def callback(self,interaction:Interaction) -> None:
		description = []
		self.view.selected = []
		for role in self.values:
			role = interaction.guild.get_role(int(role))
			self.view.selected.append(role)
			description.append(role.mention if role in self.view.current else f'***{role.mention}***')
		for role in self.view.current:
			if role not in self.view.selected:
				description.append(f'~~{role.mention}~~')
		self.view.embed.description = '\n'.join(description)
		await interaction.response.edit_message(embed=self.view.embed)

class encounter_view(View):
	def __init__(self,*,client,embed:Embed,teams:list[Role],encounter_category:CategoryChannel,archive_category:CategoryChannel) -> None:
		super().__init__()
		self.client = client
		self.embed = embed
		self.teams = teams
		self.encounter_category = encounter_category
		self.archive_category = archive_category
		self.active_encounter = None
		self.current = []
		self.selected = []
		self.remove_item(self.button_update)
		self.remove_item(self.button_end)

		options = []
		for role in self.teams:
			description = ', '.join([member.display_name for member in role.members])
			if len(description) > 100: description = f'{description[:97]}...'
			options.append(SelectOption(label=role.name,value=str(role.id),description=description))

		self.select_menu = select_menu(self.client,options)

		self.add_item(self.select_menu)

	async def on_error(self,error:Exception,item:Item,interaction:Interaction) -> None:
		await interaction.response.send_message(error,ephemeral=True)
		raise error

	@button(label='start',style=3,row=1)
	async def button_start(self,button:Button,interaction:Interaction):
		self.current = self.selected
		perms = {role:PermissionOverwrite(view_channel=True,send_messages=True) for role in self.current}
		perms.update({interaction.guild.default_role:PermissionOverwrite(view_channel=False,send_messages=False)})
		self.active_encounter = await self.encounter_category.create_text_channel(f'encounter-{token_hex(2)}',
			overwrites=perms)
		self.embed.description = '\n'.join([role.mention if role in self.current else f'*{role.mention}*' for role in self.current])
		self.remove_item(button)
		self.add_item(self.button_update)
		self.add_item(self.button_end)
		await interaction.response.edit_message(embed=self.embed,view=self)

	@button(label='update',style=1,row=1)
	async def button_update(self,button:Button,interaction:Interaction):
		perms = self.active_encounter.overwrites
		update = {}
		for role in self.current:
			if role not in self.selected: update.update({role:PermissionOverwrite(view_channel=None,send_messages=None)})
		for role in self.selected:
			if role not in perms.keys(): update.update({role:PermissionOverwrite(view_channel=True,send_messages=True)})
		for role,overwrite in update.items():
			await self.active_encounter.set_permissions(target=role,overwrite=overwrite)
		self.current = self.selected
		self.embed.description = '\n'.join([role.mention for role in self.current])
		await interaction.response.edit_message(embed=self.embed,view=self)

	@button(label='end',style=4,row=1)
	async def button_end(self,button:Button,interaction:Interaction):
		await self.active_encounter.edit(name=f'encounter-{len(self.archive_category.channels)-1}',category=self.archive_category,
			overwrites={k:PermissionOverwrite(view_channel=False,send_messages=False) for k in self.active_encounter.overwrites.keys() if k != interaction.guild.default_role})
		self.embed = Embed(title='encounter complete!',description='you may dismiss this message',color=0x69ff69)
		self.clear_items()
		await interaction.response.edit_message(embed=self.embed,view=self)