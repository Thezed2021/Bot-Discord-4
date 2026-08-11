import discord
from discord.ext import commands
import os
import asyncio
import json
import time
from gtts import gTTS
import edge_tts
from keep_alive import keep_alive

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

# Gerencia o prefixo dinâmico de cada servidor
def get_prefix(bot, message):
    if not message.guild:
        return "!"
    config = carregar_config()
    guild_id = str(message.guild.id)
    return config.get("servidores", {}).get(guild_id, {}).get("prefixo", "!")

# Configuração das permissões
intents = discord.Intents.default()
intents.message_content = True
intents.members = True 

bot = commands.Bot(command_prefix=get_prefix, intents=intents, help_command=None)

# Mapeamento das vozes da Microsoft
MAPA_VOZES = {
    2: "pt-BR-AntonioNeural",
    3: "pt-BR-FranciscaNeural",
    4: "pt-PT-DuarteNeural",
    5: "pt-PT-RaquelNeural"
}

# Filtros do FFmpeg para os efeitos especiais
FILTROS = {
    "fina": 'asetrate=44100*1.4,aresample=44100,atempo=1/1.4',
    "grossa": 'asetrate=44100*0.6,aresample=44100,atempo=1/0.6',
    "eco": 'aecho=0.8:0.9:1000:0.3',
    "alien": 'chorus=0.7:0.9:55:0.4:0.25:2',
    "estourado": 'acrusher=level_in=8:level_out=18:bits=8:mode=log:aa=1,volume=5',
    "radio": 'highpass=f=300,lowpass=f=3000',
    "fantasma": 'aecho=0.8:0.85:500|1000:0.2|0.1,asetrate=44100*0.9'
}

# --- FUNÇÃO PRINCIPAL DE REPRODUÇÃO (TTS) ---
async def play_tts(message, texto_falado, filtro_customizado=None):
    voice_client = message.guild.voice_client
    if not voice_client or not voice_client.is_connected():
        return

    config = carregar_config()
    guild_id = str(message.guild.id)
    user_id = str(message.author.id)
    
    # 1. Verifica se o usuário está bloqueado
    bloqueados = config.get("servidores", {}).get(guild_id, {}).get("bloqueados", {})
    if user_id in bloqueados:
        vencimento = bloqueados[user_id]
        if vencimento == "perm" or vencimento > time.time():
            await message.add_reaction("🚫")
            return
        else:
            # Tempo expirou, remove o bloqueio
            del config["servidores"][guild_id]["bloqueados"][user_id]
            salvar_config(config)

    # 2. Fila de espera
    while voice_client.is_playing():
        await asyncio.sleep(1)

    await message.add_reaction("✅")

    # 3. Geração do Áudio
    escolha_voz = config.get("usuarios", {}).get(user_id, 1)
    arquivo_audio = f"mensagem_{guild_id}.mp3"
    
    try:
        if escolha_voz == 1:
            tts = gTTS(text=texto_falado, lang='pt', tld='com.br')
            tts.save(arquivo_audio)
        else:
            voz_edge = MAPA_VOZES.get(escolha_voz, "pt-BR-AntonioNeural")
            communicate = edge_tts.Communicate(texto_falado, voz_edge)
            await communicate.save(arquivo_audio)

        # 4. Aplica o filtro de efeito (se houver)
        opcoes_ffmpeg = None
        if filtro_customizado:
            opcoes_ffmpeg = f'-af "{filtro_customizado}"'

        voice_client.play(discord.FFmpegPCMAudio(arquivo_audio, options=opcoes_ffmpeg))
    except Exception as e:
        await message.remove_reaction("✅", bot.user)
        await message.add_reaction("❌")
        print(f"Erro TTS: {e}")

# EVENTO: Quando o bot ligar
@bot.event
async def on_ready():
    print(f'🤖 Bot conectado com sucesso como {bot.user}')

# EVENTO: Processar mensagens normais
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    prefixo_atual = get_prefix(bot, message)
    
    # Ignora mensagens que começam com o prefixo (comandos não viram áudio)
    if message.content.startswith(prefixo_atual):
        await bot.process_commands(message)
        return

    voice_client = message.guild.voice_client
    if voice_client and voice_client.is_connected():
        config = carregar_config()
        guild_id = str(message.guild.id)
        
        # Verifica canais permitidos
        canais_permitidos = config.get("servidores", {}).get(guild_id, {}).get("canais_tts", [])
        if canais_permitidos and message.channel.id not in canais_permitidos:
            return

        texto_para_falar = f"{message.author.display_name} disse: {message.content}"
        await play_tts(message, texto_para_falar)

# --- COMANDOS DE EFEITOS E VELOCIDADE (USO ÚNICO) ---

@bot.command(name='efeito')
async def efeito(ctx, nome_efeito: str, *, texto: str):
    nome_efeito = nome_efeito.lower()
    if nome_efeito not in FILTROS:
        efeitos_disp = ", ".join(FILTROS.keys())
        return await ctx.send(f"❌ Efeito inválido! Escolha um destes: `{efeitos_disp}`")
    
    texto_para_falar = f"{ctx.author.display_name} disse: {texto}"
    await play_tts(ctx.message, texto_para_falar, filtro_customizado=FILTROS[nome_efeito])

@bot.command(name='vozvelo')
async def vozvelo(ctx, velocidade: float, *, texto: str):
    if velocidade < 0.5 or velocidade > 2.0:
        return await ctx.send("❌ A velocidade deve ser um número entre `0.5` (lento) e `2.0` (rápido).")
    
    filtro = f"atempo={velocidade}"
    texto_para_falar = f"{ctx.author.display_name} disse: {texto}"
    await play_tts(ctx.message, texto_para_falar, filtro_customizado=filtro)

# --- COMANDOS DE CONFIGURAÇÃO DO SERVIDOR E USUÁRIO ---

@bot.command(name='mudarprefixo')
@commands.has_permissions(administrator=True)
async def mudarprefixo(ctx, novo_prefixo: str):
    config = carregar_config()
    guild_id = str(ctx.guild.id)
    if "servidores" not in config: config["servidores"] = {}
    if guild_id not in config["servidores"]: config["servidores"][guild_id] = {}
    
    config["servidores"][guild_id]["prefixo"] = novo_prefixo
    salvar_config(config)
    await ctx.send(f"✅ Prefixo deste servidor alterado para: `{novo_prefixo}`")

@bot.command(name='setcanal')
@commands.has_permissions(administrator=True)
async def setcanal(ctx):
    config = carregar_config()
    guild_id = str(ctx.guild.id)
    
    if "servidores" not in config: config["servidores"] = {}
    if guild_id not in config["servidores"]: config["servidores"][guild_id] = {}
    if "canais_tts" not in config["servidores"][guild_id]: config["servidores"][guild_id]["canais_tts"] = []
        
    if ctx.channel.id not in config["servidores"][guild_id]["canais_tts"]:
        config["servidores"][guild_id]["canais_tts"].append(ctx.channel.id)
        salvar_config(config)
        await ctx.send(f"✅ Canal {ctx.channel.mention} adicionado à lista de leitura!")
    else:
        await ctx.send("⚠️ Este canal já está na lista.")

@bot.command(name='removercanal')
@commands.has_permissions(administrator=True)
async def removercanal(ctx):
    config = carregar_config()
    guild_id = str(ctx.guild.id)
    
    canais = config.get("servidores", {}).get(guild_id, {}).get("canais_tts", [])
    if ctx.channel.id in canais:
        canais.remove(ctx.channel.id)
        config["servidores"][guild_id]["canais_tts"] = canais
        salvar_config(config)
        await ctx.send(f"✅ Canal {ctx.channel.mention} removido da lista de leitura!")
    else:
        await ctx.send("❌ Este canal não estava na lista.")

@bot.command(name='listacanais')
async def listacanais(ctx):
    config = carregar_config()
    canais = config.get("servidores", {}).get(str(ctx.guild.id), {}).get("canais_tts", [])
    
    if not canais:
        await ctx.send("📜 Nenhum canal restrito. Estou lendo de todos os canais de texto!")
    else:
        lista = "\n".join([f"<#{canal_id}>" for canal_id in canais])
        await ctx.send(f"📜 **Canais permitidos para TTS:**\n{lista}")

@bot.command(name='voz')
async def mudar_voz(ctx, escolha: int):
    if escolha in [1, 2, 3, 4, 5]:
        config = carregar_config()
        if "usuarios" not in config: config["usuarios"] = {}
        config["usuarios"][str(ctx.author.id)] = escolha
        salvar_config(config)
        await ctx.send(f"✅ Voz alterada com sucesso para a opção **{escolha}**!")
    else:
        await ctx.send("❌ Opção inválida! Veja as opções no `!menu`.")

# --- COMANDOS DE MODERAÇÃO DE TTS ---

@bot.command(name='blocktts')
@commands.has_permissions(administrator=True)
async def blocktts(ctx, membro: discord.Member):
    config = carregar_config()
    guild_id = str(ctx.guild.id)
    
    if "servidores" not in config: config["servidores"] = {}
    if guild_id not in config["servidores"]: config["servidores"][guild_id] = {}
    if "bloqueados" not in config["servidores"][guild_id]: config["servidores"][guild_id]["bloqueados"] = {}
        
    config["servidores"][guild_id]["bloqueados"][str(membro.id)] = "perm"
    salvar_config(config)
    await ctx.send(f"🚫 {membro.mention} foi **bloqueado permanentemente** de usar o bot de voz.")

@bot.command(name='blocktts_tempo')
@commands.has_permissions(administrator=True)
async def blocktts_tempo(ctx, membro: discord.Member, minutos: int):
    config = carregar_config()
    guild_id = str(ctx.guild.id)
    
    if "servidores" not in config: config["servidores"] = {}
    if guild_id not in config["servidores"]: config["servidores"][guild_id] = {}
    if "bloqueados" not in config["servidores"][guild_id]: config["servidores"][guild_id]["bloqueados"] = {}
        
    tempo_vencimento = time.time() + (minutos * 60)
    config["servidores"][guild_id]["bloqueados"][str(membro.id)] = tempo_vencimento
    salvar_config(config)
    await ctx.send(f"⏱️ {membro.mention} foi bloqueado de usar o TTS por **{minutos} minutos**.")

@bot.command(name='unblocktts')
@commands.has_permissions(administrator=True)
async def unblocktts(ctx, membro: discord.Member):
    config = carregar_config()
    guild_id = str(ctx.guild.id)
    
    bloqueados = config.get("servidores", {}).get(guild_id, {}).get("bloqueados", {})
    if str(membro.id) in bloqueados:
        del config["servidores"][guild_id]["bloqueados"][str(membro.id)]
        salvar_config(config)
        await ctx.send(f"✅ {membro.mention} foi **desbloqueado** e pode usar o TTS novamente.")
    else:
        await ctx.send("⚠️ Este usuário não estava bloqueado.")

# --- COMANDOS BÁSICOS E MENUS ---

@bot.command(name='log')
async def log(ctx):
    prefixo = get_prefix(bot, ctx.message)
    embed = discord.Embed(title="🚀 Changelog - Última Atualização", color=discord.Color.gold())
    embed.add_field(name="🆕 Novidades", value=(
        "• **Emojis de Status:** O bot reage com ✅ (sucesso), ❌ (erro) e 🚫 (bloqueado).\n"
        "• **Sem spam de comandos:** Comandos não são mais lidos em voz alta.\n"
        "• **Efeitos de Voz:** Use o comando de efeitos para modificar o áudio.\n"
        "• **Velocidade:** Altere a velocidade da fala.\n"
        "• **Múltiplos Canais:** Adicione e remova vários canais de leitura.\n"
        "• **Prefixo Próprio:** Cada servidor pode ter seu próprio prefixo."
    ), inline=False)
    embed.set_footer(text=f"Digite {prefixo}menu para ver todos os comandos ativos.")
    await ctx.send(embed=embed)

@bot.command(name='menu')
async def menu(ctx):
    prefixo = get_prefix(bot, ctx.message)
    embed = discord.Embed(title="🤖 Painel de Controle Completo", color=discord.Color.blue())
    
    embed.add_field(name="⚙️ Canais e Sistema", value=f"`{prefixo}setcanal` - Adiciona canal de leitura\n`{prefixo}removercanal` - Remove canal\n`{prefixo}listacanais` - Lista canais atuais\n`{prefixo}mudarprefixo <novo>` - Muda o prefixo do bot\n`{prefixo}log` - Veja a última atualização", inline=False)
    
    embed.add_field(name="🎙️ Comandos de Voz", value=f"`{prefixo}entrar` e `{prefixo}sair` - Controle de call\n`{prefixo}voz <num>` - Escolher sua voz\n`{prefixo}efeito <tipo> <msg>` - Ex: {prefixo}efeito alien Olá\n`{prefixo}vozvelo <0.5 a 2.0> <msg>` - Ex: {prefixo}vozvelo 1.5 Olá", inline=False)
    
    embed.add_field(name="🛡️ Moderação TTS", value=f"`{prefixo}blocktts @user` - Bloqueia permanente\n`{prefixo}blocktts_tempo @user <min>` - Bloqueia por tempo\n`{prefixo}unblocktts @user` - Desbloqueia usuário", inline=False)
    
    lista_efeitos = ", ".join(FILTROS.keys())
    embed.add_field(name="🎭 Efeitos Disponíveis", value=f"`{lista_efeitos}`", inline=False)
    
    lista_vozes = (
        "**1** - Google (Padrão)\n**2** - Antônio (BR)\n"
        "**3** - Francisca (BR)\n**4** - Duarte (PT)\n**5** - Raquel (PT)"
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

# --- MODERAÇÃO GERAL (CHAT) ---
@bot.command(name='limpar')
@commands.has_permissions(manage_messages=True)
async def limpar(ctx, quantidade: int):
    await ctx.channel.purge(limit=quantidade + 1)
    msg = await ctx.send(f"🧹 {quantidade} mensagens apagadas por {ctx.author.mention}!")
    await asyncio.sleep(5)
    await msg.delete()

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

# Error Handler Unificado
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Ops! Você não tem permissão de Administrador/Moderador para usar este comando.")

keep_alive()
TOKEN = os.environ.get("TOKEN")
bot.run(TOKEN)
