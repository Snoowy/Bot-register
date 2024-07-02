import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import asyncpg
import hashlib

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Database URLs
DATABASE_URL_LS = 'postgresql://USER:PASSWORD@HOST:PORT/gf_ls'
DATABASE_URL_MS = 'postgresql://USER:PASSWORD@HOST:PORT/gf_ms'

# Create database pools
async def create_pools():
    bot.pool_ls = await asyncpg.create_pool(DATABASE_URL_LS, max_size=10)
    bot.pool_ms = await asyncpg.create_pool(DATABASE_URL_MS, max_size=10)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('BY HXK')
    await create_pools()

class RegisterModal(Modal):
    def __init__(self):
        super().__init__(title="Register")

        self.username = TextInput(label="Username", placeholder="Enter your username", min_length=3, max_length=16)
        self.password = TextInput(label="Password", placeholder="Enter your password", min_length=8, max_length=16, style=discord.TextStyle.short, required=True)
        self.confirm_password = TextInput(label="Confirm Password", placeholder="Confirm your password", min_length=8, max_length=16, style=discord.TextStyle.short, required=True)

        self.add_item(self.username)
        self.add_item(self.password)
        self.add_item(self.confirm_password)

    async def on_submit(self, interaction: discord.Interaction):
        username = self.username.value.lower()
        password = self.password.value
        confirm_password = self.confirm_password.value


        # Input validation
        if not (3 <= len(username) <= 16):
            await interaction.response.send_message("Username must be between 3 and 16 characters.", ephemeral=True)
            return

        if not (5 <= len(password) <= 16):
            await interaction.response.send_message("Password must be between 5 and 16 characters.", ephemeral=True)
            return

        if password != confirm_password:
            await interaction.response.send_message("Passwords do not match.", ephemeral=True)
            return

        username = "".join(filter(str.isalnum, username))

        try:
            async with bot.pool_ls.acquire() as conn_ls, bot.pool_ms.acquire() as conn_ms:

                # Check for existing user in both databases
                existing_user_ls = await conn_ls.fetchrow('SELECT * FROM accounts WHERE username = $1', username)
                existing_user_ms = await conn_ms.fetchrow('SELECT * FROM tb_user WHERE mid = $1', username)

                if existing_user_ls or existing_user_ms:
                    await interaction.response.send_message("Username already exists.", ephemeral=True)
                    return

                # Check number of registrations by user in MS database
                user_registrations = await conn_ms.fetchval('SELECT COUNT(*) FROM tb_user WHERE discord_user_id = $1', str(interaction.user.id))

                if user_registrations >= 3:
                    await interaction.response.send_message("You can only register up to 3 accounts.", ephemeral=True)
                    return

                # Register the user in both databases
                await conn_ls.execute('INSERT INTO accounts (username, password, realname) VALUES ($1, $2, $1)', username, password)
                await conn_ms.execute('INSERT INTO tb_user (mid, password, pwd, bonus, discord_user_id) VALUES ($1, $2, $2, $3, $4)', username, hashlib.md5(password.encode()).hexdigest(), 99999, str(interaction.user.id))

                await interaction.response.send_message("Registration successful!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("Something went wrong during registration. Please try again later.", ephemeral=True)

class RegisterButton(Button):
    def __init__(self):
        super().__init__(label="Register", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(RegisterModal())

class RegisterView(View):
    def __init__(self):
        super().__init__()
        self.add_item(RegisterButton())

class ChangePasswordModal(Modal):
    def __init__(self):
        super().__init__(title="Change Password")

        self.username = TextInput(label="Username", placeholder="Enter your username", min_length=3, max_length=16)
        self.new_password = TextInput(label="New Password", placeholder="Enter your new password", min_length=8, max_length=16, style=discord.TextStyle.short, required=True)
        self.confirm_password = TextInput(label="Confirm Password", placeholder="Confirm your new password", min_length=8, max_length=16, style=discord.TextStyle.short, required=True)

        self.add_item(self.username)
        self.add_item(self.new_password)
        self.add_item(self.confirm_password)

    async def on_submit(self, interaction: discord.Interaction):
        username = self.username.value.lower()
        new_password = self.new_password.value
        confirm_password = self.confirm_password.value


        # Input validation
        if not (3 <= len(username) <= 16):
            await interaction.response.send_message("Username must be between 3 and 16 characters.", ephemeral=True)
            return

        if not (5 <= len(new_password) <= 16):
            await interaction.response.send_message("New password must be between 5 and 16 characters.", ephemeral=True)
            return

        if new_password != confirm_password:
            await interaction.response.send_message("New passwords do not match.", ephemeral=True)
            return

        username = "".join(filter(str.isalnum, username))

        try:
            async with bot.pool_ls.acquire() as conn_ls, bot.pool_ms.acquire() as conn_ms:

                # Check if the user exists and if the Discord user ID matches
                existing_user_ms = await conn_ms.fetchrow('SELECT * FROM tb_user WHERE mid = $1 AND discord_user_id = $2', username, str(interaction.user.id))
                existing_user_ls = await conn_ls.fetchrow('SELECT * FROM accounts WHERE username = $1', username)

                if not existing_user_ms or not existing_user_ls:
                    await interaction.response.send_message("User not found or you do not have permission to change this password.", ephemeral=True)
                    return

                # Update the user's password in both databases
                await conn_ls.execute('UPDATE accounts SET password = $1 WHERE username = $2', new_password, username)
                await conn_ms.execute('UPDATE tb_user SET password = $1, pwd = $1 WHERE mid = $2', hashlib.md5(new_password.encode()).hexdigest(), username)

                await interaction.response.send_message("Password changed successfully!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("Something went wrong during the password change. Please try again later.", ephemeral=True)

class ChangePasswordButton(Button):
    def __init__(self):
        super().__init__(label="Change Password", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ChangePasswordModal())

class ChangePasswordView(View):
    def __init__(self):
        super().__init__()
        self.add_item(ChangePasswordButton())

@bot.command()
async def register(ctx):
    await ctx.send("Click the button to register.", view=RegisterView())

@bot.command()
async def changepw(ctx):
    await ctx.send("Click the button to change your password.", view=ChangePasswordView())

bot.run('TOKEN')
