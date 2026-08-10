import discord
from discord.ext import commands
import os
import asyncio
from gtts import gTTS
import edge_tts
from keep_alive import keep_alive

# Configuração das permissões (Intents)
intents = discord.Intents.default()
intents.message_content = True
intents.members = True 

# Criando o bot (desativamos o help padrão para usar o nosso !menu)
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# Dicionário para salvar a voz escolhida (padrão é 1)
vozes_config = {}

# Mapeamento das vozes da Microsoft
MAPA_VOZES = {
    2: "pt-BR-AntonioNeural",
    3: "pt-BR-FranciscaNeural",
    4: "pt-PT-DuarteNeural",
    5: "pt-PT-RaquelNeural"
}

# EVENTO: Quando o bot ligar
@bot.event
async def on_ready():
    print(f'🤖 Bot conectado com sucesso como {bot.user}')

# EVENTO: Quando alguém mandar mensagem e o bot estiver na call
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    voice_client = message.guild.voice_client
    
    if voice_client and voice_client.is_connected():
        texto_para_falar = f"{message.author.display_name} disse: {message.content}"
        
        # Pega a voz escolhida do servidor (se não tiver, usa a 1 do Google)
        escolha_voz = vozes_config.get(message.guild.id, 1)
        
        # Espera a frase anterior terminar antes de criar a próxima
        while voice_client.is_playing():
            await asyncio.sleep(1)

        try:
            arquivo_audio = f"mensagem_{message.guild.id}.mp3"
            
            if escolha_voz == 1:
                # Usa o Google Tradutor
                tts = gTTS(text=texto_para_falar, lang='pt', tld='com.br')
                tts.save(arquivo_audio)
            else:
                # Usa a IA da Microsoft (Edge-TTS)
                voz_edge = MAPA_VOZES.get(escolha_voz, "pt-BR-AntonioNeural")
                communicate = edge_tts.Communicate(texto_para_falar, voz_edge)
                await communicate.save(arquivo_audio)

            # Toca o áudio
            voice_client.play(discord.FFmpegPCMAudio(arquivo_audio))
        except Exception as e:
            print(f"Erro ao tentar falar: {e}")

    # Processa os comandos normais (!menu, !entrar, etc)
    await bot.process_commands(message)

# COMANDO: Menu de Comandos e Vozes
@bot.command(name='menu')
async def menu(ctx):
    # Cria uma caixa de mensagem bonita (Embed)
    embed = discord.Embed(title="🤖 Painel de Controle do Bot", color=discord.Color.blue())
    
    # Adiciona a lista de comandos
    embed.add_field(name="🎙️ Comandos de Voz", value="`!entrar` - O bot entra na call\n`!sair` - O bot sai da call\n`!voz <numero>` - Muda o dublador do bot", inline=False)
    embed.add_field(name="🛡️ Moderação", value="`!limpar <quantidade>` - Apaga mensagens\n`!kick @usuario` - Expulsa membro\n`!ban @usuario` - Bane membro", inline=False)
    
    # Adiciona a lista de vozes
    lista_vozes = (
        "**1** - Google Tradutor (Feminina - Padrão)\n"
        "**2** - Antônio (Masculina - Realista BR)\n"
        "**3** - Francisca (Feminina - Realista BR)\n"
        "**4** - Duarte (Masculina - Realista de Portugal)\n"
        "**5** - Raquel (Feminina - Realista de Portugal)"
    )
    embed.add_field(name="🗣️ Opções de Voz", value=lista_vozes, inline=False)
    
    embed.set_footer(text="Exemplo de uso: Digite !voz 2 para usar a voz do Antônio.")
    await ctx.send(embed=embed)

# COMANDO: Mudar a voz
@bot.command(name='voz')
async def mudar_voz(ctx, escolha: int):
    if escolha in [1, 2, 3, 4, 5]:
        vozes_config[ctx.guild.id] = escolha
        await ctx.send(f"✅ Voz alterada com sucesso para a opção **{escolha}**!")
    else:
        await ctx.send("❌ Opção inválida! Digite `!menu` para ver as opções disponíveis.")

# COMANDO: Entrar na call
@bot.command(name='entrar')
async def entrar(ctx):
    if ctx.author.voice:
        canal_voz = ctx.author.voice.channel
        await canal_voz.connect()
        await ctx.send("🔊 Cheguei na call! Tudo que digitarem aqui eu vou ler em voz alta.")
    else:
        await ctx.send("❌ Você precisa entrar em um canal de voz primeiro!")

# COMANDO: Sair da call
@bot.command(name='sair')
async def sair(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("🔇 Saí da call. Até a próxima!")
    else:
        await ctx.send("❌ Eu não estou em nenhuma call.")

# COMANDO: Limpar Chat
@bot.command(name='limpar')
@commands.has_permissions(manage_messages=True)
async def limpar(ctx, quantidade: int):
    await ctx.channel.purge(limit=quantidade + 1)
    mensagem = await ctx.send(f"🧹 {quantidade} mensagens foram apagadas por {ctx.author.mention}!")
    await asyncio.sleep(5)
    await mensagem.delete()

# COMANDO: Expulsar
@bot.command(name='kick')
@commands.has_permissions(kick_members=True)
async def kick(ctx, membro: discord.Member, *, motivo="Nenhum motivo informado."):
    await membro.kick(reason=motivo)
    await ctx.send(f"👢 {membro.mention} foi expulso. Motivo: {motivo}")

# COMANDO: Banir
@bot.command(name='ban')
@commands.has_permissions(ban_members=True)
async def ban(ctx, membro: discord.Member, *, motivo="Nenhum motivo informado."):
    await membro.ban(reason=motivo)
    await ctx.send(f"🔨 {membro.mention} foi banido. Motivo: {motivo}")

# MENSAGEM DE ERRO: Moderação sem permissão
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
