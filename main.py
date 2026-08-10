import discord
from discord.ext import commands
import os
import asyncio
from gtts import gTTS
import re
from keep_alive import keep_alive
from dotenv import load_dotenv

# Carrega variáveis locais se houver um arquivo .env
load_dotenv()

TOKEN = os.getenv('TOKEN')

# NOVA ABORDAGEM: Sem bloco try/except para não dar erro de sintaxe no celular!
_canal_env = os.getenv('CANAL_TEXTO_ID', '0')
CANAL_TEXTO_ID = int(_canal_env) if _canal_env.isdigit() else 0

# Configuração de Intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
from gtts import gTTS
import asyncio


bot = commands.Bot(command_prefix='!', intents=intents)

# Classe para gerenciar o estado da fila
class GuildState:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.is_playing = False
        self.afk_task = None

guild_states = {}

def get_state(guild_id):
    if guild_id not in guild_states:
        guild_states[guild_id] = GuildState()
    return guild_states[guild_id]

async def play_next(guild, voice_client):
    state = get_state(guild.id)
    
    if state.queue.empty():
        state.is_playing = False
        return

    state.is_playing = True
    text, message_id = await state.queue.get()
    
    file_name = f"tts_{guild.id}_{message_id}.mp3"
    
    try:
        tts = gTTS(text=text, lang='pt')
        tts.save(file_name)
        
        def after_playing(error):
            if error:
                print(f"Erro no playback: {error}")
            try:
                if os.path.exists(file_name):
                    os.remove(file_name)
            except Exception as e:
                pass
            
            coro = play_next(guild, voice_client)
            asyncio.run_coroutine_threadsafe(coro, bot.loop)

        source = discord.FFmpegPCMAudio(file_name)
        voice_client.play(source, after=after_playing)
        
    except Exception as e:
        print(f"Erro ao processar o TTS: {e}")
        if os.path.exists(file_name):
            os.remove(file_name)
        await play_next(guild, voice_client)

@bot.event
async def on_ready():
    print(f'🤖 Bot TTS conectado com sucesso como {bot.user}')
    print(f'Canal alvo configurado: {CANAL_TEXTO_ID}')

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    await bot.process_commands(message)

    if message.channel.id != CANAL_TEXTO_ID:
        return
        
    if message.content.startswith(bot.command_prefix):
        return

    text = message.content.strip()

    if len(text) > 250:
        await message.add_reaction('❌')
        return
        
    text = re.sub(r'http[s]?://\S+', '', text)
    text = re.sub(r'<@!?&?\d+>', '', text)
    
    text = text.strip()
    if not text:
        return
        
    voice_client = discord.utils.get(bot.voice_clients, guild=message.guild)
    if not voice_client or not voice_client.is_connected():
        return
        
    state = get_state(message.guild.id)
    await state.queue.put((text, message.id))
    await message.add_reaction('✅')
    
    if not state.is_playing:
        await play_next(message.guild, voice_client)

@bot.command(name='entrar')
async def entrar(ctx):
    if not ctx.author.voice:
        await ctx.send("⚠️ Você precisa estar em um canal de voz para me chamar!")
        return
        
    channel = ctx.author.voice.channel
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    
    if voice_client and voice_client.is_connected():
        await voice_client.move_to(channel)
    else:
        await channel.connect()
        
    await ctx.send(f"🎙️ Conectado ao canal **{channel.name}**! Pode mandar texto no canal configurado.")

@bot.command(name='sair')
async def sair(ctx):
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    
    if voice_client and voice_client.is_connected():
        state = get_state(ctx.guild.id)
        
        while not state.queue.empty():
            state.queue.get_nowait()
            
        state.is_playing = False
        voice_client.stop()
        await voice_client.disconnect()
        await ctx.send("🔌 Desconectado e fila de áudio esvaziada!")
    else:
        await ctx.send("⚠️ Eu não estou em nenhum canal de voz no momento.")

@bot.command(name='pular')
async def pular(ctx):
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await ctx.send("⏭️ Áudio pulado!")
    else:
        await ctx.send("⚠️ Não há nenhum áudio tocando no momento.")
@bot.event
async def on_message(message):
    # Ignora as mensagens que o próprio bot enviar (para ele não falar sozinho)
        if message.author == bot.user:
                return

                    # Verifica se o bot está conectado em algum canal de voz
                        voice_client = message.guild.voice_client
                            
                                # Se o bot estiver na call e alguém digitar, ele vai falar!
                                    if voice_client and voice_client.is_connected():
                                            # Cria a frase: "Nome disse: mensagem"
                                                    texto_para_falar = f"{message.author.display_name} disse: {message.content}"
                                                            
                                                                    try:
                                                                                # Transforma o texto em áudio usando o Google (em português)
                                                                                            tts = gTTS(text=texto_para_falar, lang='pt', tld='com.br')
                                                                                                        tts.save("mensagem.mp3") # Salva um arquivo mp3 temporário

                                                                                                                    # Espera se o bot já estiver no meio de outra frase
                                                                                                                                while voice_client.is_playing():
                                                                                                                                                await asyncio.sleep(1)

                                                                                                                                                            # Toca o áudio na call!
                                                                                                                                                                        voice_client.play(discord.FFmpegPCMAudio("mensagem.mp3"))
                                                                                                                                                                                except Exception as e:
                                                                                                                                                                                            print(f"Erro ao tentar falar: {e}")

                                                                                                                                                                                                # MUITO IMPORTANTE: Essa linha garante que os seus comandos (como !entrar, !limpar) não parem de funcionar!
                                                                                                                                                                                                    await bot.process_commands(message)
# Comando para apagar mensagens em massa
@bot.command(name='limpar', help='Apaga mensagens do chat (Ex: !limpar 10)')
@commands.has_permissions(manage_messages=True) # Só admins/mods podem usar
async def limpar(ctx, quantidade: int):
    await ctx.channel.purge(limit=quantidade + 1) # +1 para apagar o próprio comando
        mensagem = await ctx.send(f"🧹 {quantidade} mensagens foram apagadas por {ctx.author.mention}!")
            await asyncio.sleep(5)
                await mensagem.delete() # Apaga o aviso depois de 5 segundos

                # Comando para expulsar
                @bot.command(name='kick', help='Expulsa um usuário (Ex: !kick @usuario motivo)')
                @commands.has_permissions(kick_members=True)
                async def kick(ctx, membro: discord.Member, *, motivo="Nenhum motivo informado."):
                    await membro.kick(reason=motivo)
                        await ctx.send(f"👢 {membro.mention} foi expulso do servidor. Motivo: {motivo}")

                        # Comando para banir
                        @bot.command(name='ban', help='Bane um usuário (Ex: !ban @usuario motivo)')
                        @commands.has_permissions(ban_members=True)
                        async def ban(ctx, membro: discord.Member, *, motivo="Nenhum motivo informado."):
                            await membro.ban(reason=motivo)
                                await ctx.send(f"🔨 {membro.mention} foi banido do servidor. Motivo: {motivo}")

                                # Se alguém sem permissão tentar usar, o bot avisa
                                @limpar.error
                                @kick.error
                                @ban.error
                                async def erro_permissao(ctx, error):
                                    if isinstance(error, commands.MissingPermissions):
                                            await ctx.send("❌ Ops! Você não tem permissão para usar este comando de moderação.")
                                            

@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == bot.user.id:
        return
        
    voice_client = member.guild.voice_client
    if not voice_client:
        return

    state = get_state(member.guild.id)
    human_members = [m for m in voice_client.channel.members if not m.bot]

    if len(human_members) == 0:
        if state.afk_task is None or state.afk_task.done():
            state.afk_task = bot.loop.create_task(afk_disconnect(member.guild, voice_client))
    else:
        if state.afk_task and not state.afk_task.done():
            state.afk_task.cancel()
            state.afk_task = None

async def afk_disconnect(guild, voice_client):
    try:
        await asyncio.sleep(180)
        
        if voice_client.is_connected():
            state = get_state(guild.id)
            while not state.queue.empty():
                state.queue.get_nowait()
            state.is_playing = False
            
            await voice_client.disconnect()
            print(f"💤 Bot desconectado de {guild.name} por inatividade (AFK).")
            
    except asyncio.CancelledError:
        pass

if __name__ == "__main__":
    if not TOKEN:
        print("ERRO: Token do bot não encontrado. Configure a variável TOKEN.")
    else:
        keep_alive()
        bot.run(TOKEN)
