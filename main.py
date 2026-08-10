import discord
from discord.ext import commands
import os
import asyncio
import json
from gtts import gTTS
import edge_tts
from keep_alive import keep_alive

# Configuração das permissões
intents = discord.Intents.default()
intents.message_content = True
intents.members = True 

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# Mapeamento das vozes da Microsoft
MAPA_VOZES = {
    2: "pt-BR-AntonioNeural",
    3: "pt-BR-FranciscaNeural",
    4: "pt-PT-DuarteNeural",
    5: "pt-PT-RaquelNeural"
}

# --- SISTEMA DE CONFIGURAÇÃO (BANCO DE DADOS LOCAL) ---
ARQUIVO_CONFIG = "config.json"

def carregar_config():
    try:
        with open(ARQUIVO_CONFIG, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"servidores": {}, "usuarios": {}}

def salvar_config(dados):
    with open(ARQUIVO_CONFIG, "w") as f:
        json.dump(dados, f, indent=4)

# EVENTO: Quando o bot ligar
@bot.event
async def on_ready():
    print(f'🤖 Bot conectado com sucesso como {bot.user}')

# EVENTO: Processar mensagens e falar na call
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Sempre processa os comandos (!menu, !entrar, etc)
    await bot.process_commands(message)

    voice_client = message.guild.voice_client
    
    if voice_client and voice_client.is_connected():
        # Ignora comandos para não ler em voz alta
        if message.content.startswith("!"):
            return

        config = carregar_config()
        
        # Garante a estrutura correta do arquivo
        if "servidores" not in config:
            config = {"servidores": {}, "usuarios": {}}
            
        guild_id = str(message.guild.id)
        config_servidor = config["servidores"].get(guild_id, {})
        
        # Verifica se tem canal travado
        canal_permitido = config_servidor.get("canal_tts")
        if canal_permitido and message.channel.id != canal_permitido:
            return

        texto_para_falar = f"{message.author.display_name} disse: {message.content}"
        
        # Pega a voz escolhida do USUÁRIO (padrão é 1 se ele nunca escolheu)
        escolha_voz = config["usuarios"].get(str(message.author.id), 1) 
        
        while voice_client.is_playing():
            await asyncio.sleep(1)

        try:
            arquivo_audio = f"mensagem_{message.guild.id}.mp3"
            
            if escolha_voz == 1:
                tts = gTTS(text=texto_para_falar, lang='pt', tld='com.br')
                tts.save(arquivo_audio)
            else:
                voz_edge = MAPA_VOZES.get(escolha_voz, "pt-BR-AntonioNeural")
                communicate = edge_tts.Communicate(texto_para_falar, voz_edge)
                await communicate.save(arquivo_audio)

            voice_client.play(discord.FFmpegPCMAudio(arquivo_audio))
        except Exception as e:
            print(f"Erro ao tentar falar: {e}")

# --- COMANDOS DE CONFIGURAÇÃO ---

@bot.command(name='tutorial')
async def tutorial(ctx):
    embed = discord.Embed(title="📚 Tutorial Rápido de Configuração", color=discord.Color.green())
    embed.description = "Configurar o bot é super fácil! Tudo é feito por comandos aqui mesmo no chat."
    
    passos = (
        "**1. Fixar um Canal de Leitura (Admins):**\n"
        "Vá no canal de texto que você quer que o bot leia (ex: #chat-voz) e digite `!setcanal`.\n"
        "*(Se não configurar, ele lerá as mensagens de todos os canais!)*\n\n"
        
        "**2. Escolher a sua Voz (Qualquer pessoa):**\n"
        "Digite `!menu` para ver as vozes e use `!voz <numero>` (Ex: `!voz 2`).\n"
        "*(A voz que você escolher fica salva só para você!)*\n\n"
        
        "**3. Começar a usar:**\n"
        "Entre numa call e digite `!entrar`. Depois é só digitar no canal e ouvir a mágica!"
    )
    embed.add_field(name="Siga estes passos:", value=passos, inline=False)
    await ctx.send(embed=embed)

@bot.command(name='setcanal')
@commands.has_permissions(administrator=True)
async def setcanal(ctx):
    config = carregar_config()
    if "servidores" not in config:
        config = {"servidores": {}, "usuarios": {}}
        
    guild_id = str(ctx.guild.id)
    if guild_id not in config["servidores"]:
        config["servidores"][guild_id] = {}
        
    config["servidores"][guild_id]["canal_tts"] = ctx.channel.id
    salvar_config(config)
    
    await ctx.send(f"✅ **Canal configurado!** A partir de agora, eu só vou ler em voz alta as mensagens enviadas aqui no canal {ctx.channel.mention}.")

@bot.command(name='voz')
async def mudar_voz(ctx, escolha: int):
    if escolha in [1, 2, 3, 4, 5]:
        config = carregar_config()
        if "usuarios" not in config:
            config["usuarios"] = {}
            
        # Salva a voz escolhida usando o ID da pessoa que mandou a mensagem
        config["usuarios"][str(ctx.author.id)] = escolha
        salvar_config(config)
        
        await ctx.send(f"✅ Perfeito! Agora eu usarei a voz **{escolha}** quando **VOCÊ** ({ctx.author.mention}) digitar algo.")
    else:
        await ctx.send("❌ Opção inválida! Digite `!menu` para ver as opções disponíveis.")

# --- OUTROS COMANDOS ---

@bot.command(name='menu')
async def menu(ctx):
    embed = discord.Embed(title="🤖 Painel de Controle do Bot", color=discord.Color.blue())
    
    embed.add_field(name="⚙️ Configuração", value="`!tutorial` - Como configurar\n`!setcanal` - Trava a leitura neste canal (Admins)", inline=False)
    embed.add_field(name="🎙️ Comandos de Voz", value="`!entrar` - O bot entra na call\n`!sair` - O bot sai da call\n`!voz <numero>` - Muda a sua voz pessoal", inline=False)
    embed.add_field(name="🛡️ Moderação", value="`!limpar <qtd>` - Apaga mensagens\n`!kick @usuario` - Expulsa\n`!ban @usuario` - Bane", inline=False)
    
    lista_vozes = (
        "**1** - Google Tradutor (Feminina - Padrão)\n"
        "**2** - Antônio (Masculina - Realista BR)\n"
        "**3** - Francisca (Feminina - Realista BR)\n"
        "**4** - Duarte (Masculina - Realista PT)\n"
        "**5** - Raquel (Feminina - Realista PT)"
    )
    embed.add_field(name="🗣️ Opções de Voz", value=lista_vozes, inline=False)
    await ctx.send(embed=embed)

@bot.command(name='entrar')
async def entrar(ctx):
    if ctx.author.voice:
        canal_voz = ctx.author.voice.channel
        await canal_voz.connect()
        await ctx.send("🔊 Cheguei na call! Tudo que digitarem eu vou ler em voz alta.")
    else:
        await ctx.send("❌ Você precisa entrar em um canal de voz primeiro!")

@bot.command(name='sair')
async def sair(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("🔇 Saí da call. Até a próxima!")
    else:
        await ctx.send("❌ Eu não estou em nenhuma call.")

@bot.command(name='limpar')
@commands.has_permissions(manage_messages=True)
async def limpar(ctx, quantidade: int):
    await ctx.channel.purge(limit=quantidade + 1)
    mensagem = await ctx.send(f"🧹 {quantidade} mensagens apagadas por {ctx.author.mention}!")
    await asyncio.sleep(5)
    await mensagem.delete()

@bot.command(name='kick')
@commands.has_permissions(kick_members=True)
async def kick(ctx, membro: discord.Member, *, motivo="Nenhum motivo informado."):
    await membro.kick(reason=motivo)
    await ctx.send(f"👢 {membro.mention} foi expulso. Motivo: {motivo}")

@bot.command(name='ban')
@commands.has_permissions(ban_members=True)
async def ban(ctx, membro: discord.Member, *, motivo="Nenhum motivo informado."):
    await membro.ban(reason=motivo)
    await ctx.send(f"🔨 {membro.mention} foi banido. Motivo: {motivo}")

@limpar.error
@kick.error
@ban.error
@setcanal.error
async def erro_permissao(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Ops! Você não tem permissão para usar este comando.")

keep_alive()
TOKEN = os.environ.get("TOKEN")
bot.run(TOKEN)
