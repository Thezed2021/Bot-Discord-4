import discord
from discord.ext import commands
import os
import asyncio
from gtts import gTTS
from keep_alive import keep_alive

# Configuração das permissões (Intents)
intents = discord.Intents.default()
intents.message_content = True
intents.members = True 

# Criando o bot com o prefixo "!"
bot = commands.Bot(command_prefix="!", intents=intents)

# EVENTO: Quando o bot ligar
@bot.event
async def on_ready():
    print(f'🤖 Bot conectado com sucesso como {bot.user}')

# EVENTO: Quando alguém mandar mensagem e o bot estiver na call
@bot.event
async def on_message(message):
    # Ignora as mensagens do próprio bot
    if message.author == bot.user:
        return

    voice_client = message.guild.voice_client
    
    # Se o bot estiver na call, ele fala a mensagem
    if voice_client and voice_client.is_connected():
        texto_para_falar = f"{message.author.display_name} disse: {message.content}"
        
        try:
            tts = gTTS(text=texto_para_falar, lang='pt', tld='com.br')
            tts.save("mensagem.mp3")

            # Espera a frase anterior terminar antes de falar a próxima
            while voice_client.is_playing():
                await asyncio.sleep(1)

            voice_client.play(discord.FFmpegPCMAudio("mensagem.mp3"))
        except Exception as e:
            print(f"Erro ao tentar falar: {e}")

    # Processa os comandos normais (!entrar, !limpar, etc)
    await bot.process_commands(message)

# COMANDO: Entrar na call
@bot.command(name='entrar', help='Faz o bot entrar no seu canal de voz')
async def entrar(ctx):
    if ctx.author.voice:
        canal_voz = ctx.author.voice.channel
        await canal_voz.connect()
        await ctx.send("🔊 Cheguei na call! Tudo que digitarem aqui eu vou ler em voz alta.")
    else:
        await ctx.send("❌ Você precisa entrar em um canal de voz primeiro!")

# COMANDO: Sair da call
@bot.command(name='sair', help='Faz o bot sair da call')
async def sair(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("🔇 Saí da call. Até a próxima!")
    else:
        await ctx.send("❌ Eu não estou em nenhuma call.")

# COMANDO DE MODERAÇÃO: Limpar Chat
@bot.command(name='limpar', help='Apaga mensagens do chat (Ex: !limpar 10)')
@commands.has_permissions(manage_messages=True)
async def limpar(ctx, quantidade: int):
    await ctx.channel.purge(limit=quantidade + 1)
    mensagem = await ctx.send(f"🧹 {quantidade} mensagens foram apagadas por {ctx.author.mention}!")
    await asyncio.sleep(5)
    await mensagem.delete()

# COMANDO DE MODERAÇÃO: Expulsar
@bot.command(name='kick', help='Expulsa um usuário (Ex: !kick @usuario motivo)')
@commands.has_permissions(kick_members=True)
async def kick(ctx, membro: discord.Member, *, motivo="Nenhum motivo informado."):
    await membro.kick(reason=motivo)
    await ctx.send(f"👢 {membro.mention} foi expulso. Motivo: {motivo}")

# COMANDO DE MODERAÇÃO: Banir
@bot.command(name='ban', help='Bane um usuário (Ex: !ban @usuario motivo)')
@commands.has_permissions(ban_members=True)
async def ban(ctx, membro: discord.Member, *, motivo="Nenhum motivo informado."):
    await membro.ban(reason=motivo)
    await ctx.send(f"🔨 {membro.mention} foi banido. Motivo: {motivo}")

# MENSAGEM DE ERRO: Sem permissão
@limpar.error
@kick.error
@ban.error
async def erro_permissao(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Ops! Você não tem permissão para usar comandos de moderação.")

# Liga o site e o Bot
keep_alive()
TOKEN = os.environ.get("TOKEN")
bot.run(TOKEN)
