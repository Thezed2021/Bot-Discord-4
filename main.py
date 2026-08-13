import discord
from discord.ext import commands
import os
import asyncio
import json
import time
import re
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

def init_guild_config(config, guild_id):
    if "servidores" not in config: config["servidores"] = {}
    if guild_id not in config["servidores"]: config["servidores"][guild_id] = {}
    return config

def get_prefix(bot, message):
    if not message.guild:
        return "!"
    config = carregar_config()
    return config.get("servidores", {}).get(str(message.guild.id), {}).get("prefixo", "!")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True 

bot = commands.Bot(command_prefix=get_prefix, intents=intents, help_command=None)

MAPA_VOZES = {
    2: "pt-BR-AntonioNeural",
    3: "pt-BR-FranciscaNeural",
    4: "pt-PT-DuarteNeural",
    5: "pt-PT-RaquelNeural"
}

# Filtros do FFmpeg corrigidos
FILTROS = {
    "fina": 'asetrate=44100*1.4,aresample=44100,atempo=1/1.4',
    "grossa": 'asetrate=44100*0.75,aresample=44100,atempo=1/0.75', # Ajustado para não falhar
    "grave": 'bass=g=15:f=110:w=0.6', # Equalizador de graves profundos
    "eco": 'aecho=0.8:0.9:1000:0.3',
    "alien": 'chorus=0.7:0.9:55:0.4:0.25:2',
    "estourado": 'acrusher=level_in=8:level_out=18:bits=8:mode=log:aa=1,volume=5',
    "radio": 'highpass=f=300,lowpass=f=3000',
    "fantasma": 'aecho=0.8:0.85:500|1000:0.2|0.1,asetrate=44100*0.9'
}

# --- FUNÇÃO PRINCIPAL DE REPRODUÇÃO (TTS) ---
async def play_tts(message, texto_original, filtro_global=None):
    voice_client = message.guild.voice_client
    if not voice_client or not voice_client.is_connected():
        return

    config = carregar_config()
    guild_id = str(message.guild.id)
    user_id = str(message.author.id)
    config_servidor = config.get("servidores", {}).get(guild_id, {})
    
    bloqueados = config_servidor.get("bloqueados", {})
    if user_id in bloqueados:
        vencimento = bloqueados[user_id]
        if vencimento == "perm" or vencimento > time.time():
            await message.add_reaction("🚫")
            return
        else:
            del config["servidores"][guild_id]["bloqueados"][user_id]
            salvar_config(config)

    dicionario = config_servidor.get("dicionario", {})
    for palavra, traducao in dicionario.items():
        texto_original = re.sub(rf'\b{re.escape(palavra)}\b', traducao, texto_original, flags=re.IGNORECASE)

    texto_original = re.sub(r'https?://[^\s]+', 'um link', texto_original)

    if config_servidor.get("filtro_palavrao", True):
        palavroes = config_servidor.get("palavroes", [])
        for p in palavroes:
            texto_original = re.sub(rf'\b{re.escape(p)}\b', 'BIP', texto_original, flags=re.IGNORECASE)

    partes = re.split(r'(<[a-zA-Z]+:\s*.*?>)', texto_original)
    fila = []
    
    for p in partes:
        if not p.strip(): continue
        m = re.match(r'<([a-zA-Z]+):\s*(.*?)>', p)
        if m:
            fila.append((m.group(2).strip(), m.group(1).lower())) 
        else:
            fila.append((p.strip(), filtro_global))

    while voice_client.is_playing():
        await asyncio.sleep(1)

    await message.add_reaction("✅")

    escolha_voz = config.get("usuarios", {}).get(user_id, 1)
    
    try:
        for i, (texto_parte, efeito_parte) in enumerate(fila):
            if not texto_parte: continue
            
            arquivo_audio = f"temp_{guild_id}_{i}_{int(time.time())}.mp3"
            
            if escolha_voz == 1:
                tts = gTTS(text=texto_parte, lang='pt', tld='com.br')
                tts.save(arquivo_audio)
            else:
                voz_edge = MAPA_VOZES.get(escolha_voz, "pt-BR-AntonioNeural")
                communicate = edge_tts.Communicate(texto_parte, voz_edge)
                await communicate.save(arquivo_audio)

            opcoes_ffmpeg = None
            if efeito_parte in FILTROS:
                opcoes_ffmpeg = f'-af "{FILTROS[efeito_parte]}"'
            elif efeito_parte: 
                opcoes_ffmpeg = f'-af "{efeito_parte}"'

            voice_client.play(discord.FFmpegPCMAudio(arquivo_audio, options=opcoes_ffmpeg))
            
            while voice_client.is_playing():
                await asyncio.sleep(0.5)
                
            try: os.remove(arquivo_audio)
            except: pass

    except Exception as e:
        await message.remove_reaction("✅", bot.user)
        await message.add_reaction("❌")
        print(f"Erro TTS: {e}")

# --- EVENTOS DO BOT ---
@bot.event
async def on_ready():
    print(f'🤖 Bot conectado com sucesso como {bot.user}')

@bot.event
async def on_voice_state_update(member, before, after):
    # Se quem causou a atualização for um bot, ignoramos para não entrar em loop infinito
    if member.bot: 
        return
        
    config = carregar_config()
    guild_id = str(member.guild.id)
    config_servidor = config.get("servidores", {}).get(guild_id, {})
    voice_client = member.guild.voice_client

    # 1. ENTRAR SOZINHO (Modo Automático ligado e a pessoa entrou em um canal de voz)
    if before.channel is None and after.channel is not None:
        if config_servidor.get("auto_join", True):
            if not voice_client:
                await after.channel.connect()
                
                canal_envio = None
                canais_tts = config_servidor.get("canais_tts", [])
                if canais_tts: canal_envio = bot.get_channel(canais_tts[0])
                if not canal_envio: canal_envio = member.guild.system_channel
                if not canal_envio:
                    for channel in member.guild.text_channels:
                        if channel.permissions_for(member.guild.me).send_messages:
                            canal_envio = channel
                            break
                            
                if canal_envio:
                    prefixo = config_servidor.get("prefixo", "!")
                    await canal_envio.send(f"🤖 **Modo Automático Ativado!**\nEntrei na call automaticamente. Para desativar, use `{prefixo}modoautomatico off`.")

    # 2. SAIR SOZINHO (Alguém saiu da call e o bot ficou sozinho lá dentro)
    if before.channel is not None:
        # Se o bot está em um canal de voz
        if voice_client and voice_client.channel:
            # Conta quantas pessoas que NÃO SÃO BOTS estão no canal
            membros_humanos = sum(1 for m in voice_client.channel.members if not m.bot)
            
            # Se não sobrou nenhum humano, o bot sai
            if membros_humanos == 0:
                await asyncio.sleep(2) # Pequeno atraso para garantir que a API atualizou
                await voice_client.disconnect()

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    prefixo_atual = get_prefix(bot, message)
    if message.content.startswith(prefixo_atual):
        await bot.process_commands(message)
        return

    voice_client = message.guild.voice_client
    if voice_client and voice_client.is_connected():
        config = carregar_config()
        guild_id = str(message.guild.id)
        
        canais_permitidos = config.get("servidores", {}).get(guild_id, {}).get("canais_tts", [])
        if canais_permitidos and message.channel.id not in canais_permitidos:
            return

        texto_para_falar = f"{message.author.display_name} disse: {message.content}"
        await play_tts(message, texto_para_falar)

# --- COMANDOS: MODO AUTOMÁTICO ---
@bot.command(name='modoautomatico')
@commands.has_permissions(administrator=True)
async def modoautomatico(ctx, estado: str):
    estado = estado.lower()
    if estado not in ["on", "off"]:
        return await ctx.send("❌ Use `!modoautomatico on` ou `!modoautomatico off`.")
        
    config = carregar_config()
    guild_id = str(ctx.guild.id)
    config = init_guild_config(config, guild_id)
    
    config["servidores"][guild_id]["auto_join"] = (estado == "on")
    salvar_config(config)
    
    status = "ativado" if estado == "on" else "desativado"
    await ctx.send(f"✅ Modo automático **{status}**!")

# --- COMANDOS: DICIONÁRIO E GÍRIAS ---
@bot.command(name='ensinar')
@commands.has_permissions(administrator=True)
async def ensinar(ctx, palavra: str, *, traducao: str):
    config = carregar_config()
    guild_id = str(ctx.guild.id)
    config = init_guild_config(config, guild_id)
    if "dicionario" not in config["servidores"][guild_id]: config["servidores"][guild_id]["dicionario"] = {}
        
    config["servidores"][guild_id]["dicionario"][palavra.lower()] = traducao
    salvar_config(config)
    await ctx.send(f"✅ Aprendi! Quando alguém disser `{palavra}`, eu lerei `{traducao}`.")

@bot.command(name='esquecer')
@commands.has_permissions(administrator=True)
async def esquecer(ctx, palavra: str):
    config = carregar_config()
    guild_id = str(ctx.guild.id)
    dicionario = config.get("servidores", {}).get(guild_id, {}).get("dicionario", {})
    
    if palavra.lower() in dicionario:
        del config["servidores"][guild_id]["dicionario"][palavra.lower()]
        salvar_config(config)
        await ctx.send(f"✅ Esqueci a palavra `{palavra}`.")
    else:
        await ctx.send("❌ Essa palavra não estava no meu dicionário.")

@bot.command(name='dicionario')
async def dicionario_lista(ctx):
    config = carregar_config()
    dicionario = config.get("servidores", {}).get(str(ctx.guild.id), {}).get("dicionario", {})
    if not dicionario:
        return await ctx.send("📜 Meu dicionário está vazio.")
        
    texto = "\n".join([f"**{p}** ➡️ {t}" for p, t in dicionario.items()])
    await ctx.send(f"📖 **Meu Dicionário de Gírias:**\n{texto}")

# --- COMANDOS: FILTRO FAMILY FRIENDLY ---
@bot.command(name='ativarpalavrao')
@commands.has_permissions(administrator=True)
async def ativarpalavrao(ctx):
    config = carregar_config()
    guild_id = str(ctx.guild.id)
    config = init_guild_config(config, guild_id)
    config["servidores"][guild_id]["filtro_palavrao"] = True
    salvar_config(config)
    await ctx.send("✅ O filtro de palavrões foi **ativado**! (Serão substituídos por BIP).")

@bot.command(name='desativarpalavrao')
@commands.has_permissions(administrator=True)
async def desativarpalavrao(ctx):
    config = carregar_config()
    guild_id = str(ctx.guild.id)
    config = init_guild_config(config, guild_id)
    config["servidores"][guild_id]["filtro_palavrao"] = False
    salvar_config(config)
    await ctx.send("❌ O filtro de palavrões foi **desativado**!")

@bot.command(name='addpalavrao')
@commands.has_permissions(administrator=True)
async def addpalavrao(ctx, palavra: str):
    config = carregar_config()
    guild_id = str(ctx.guild.id)
    config = init_guild_config(config, guild_id)
    if "palavroes" not in config["servidores"][guild_id]: config["servidores"][guild_id]["palavroes"] = []
    
    if palavra.lower() not in config["servidores"][guild_id]["palavroes"]:
        config["servidores"][guild_id]["palavroes"].append(palavra.lower())
        salvar_config(config)
        await ctx.send(f"✅ Palavra `{palavra}` adicionada à lista negra.")
    else:
        await ctx.send("⚠️ Essa palavra já está na lista negra.")

@bot.command(name='rempalavrao')
@commands.has_permissions(administrator=True)
async def rempalavrao(ctx, palavra: str):
    config = carregar_config()
    guild_id = str(ctx.guild.id)
    palavroes = config.get("servidores", {}).get(guild_id, {}).get("palavroes", [])
    
    if palavra.lower() in palavroes:
        config["servidores"][guild_id]["palavroes"].remove(palavra.lower())
        salvar_config(config)
        await ctx.send(f"✅ Palavra `{palavra}` removida da lista negra.")
    else:
        await ctx.send("❌ Essa palavra não estava na lista negra.")

# --- OUTROS COMANDOS (EFEITOS, PREFIXO, VOZ E MENUS) ---
@bot.command(name='efeito')
async def efeito(ctx, nome_efeito: str, *, texto: str):
    nome_efeito = nome_efeito.lower()
    if nome_efeito not in FILTROS:
        efeitos_disp = ", ".join(FILTROS.keys())
        return await ctx.send(f"❌ Efeito inválido! Escolha: `{efeitos_disp}`")
    
    texto_para_falar = f"{ctx.author.display_name} disse: {texto}"
    await play_tts(ctx.message, texto_para_falar, filtro_global=FILTROS[nome_efeito])

@bot.command(name='vozvelo')
async def vozvelo(ctx, velocidade: float, *, texto: str):
    if velocidade < 0.5 or velocidade > 2.0:
        return await ctx.send("❌ A velocidade deve estar entre `0.5` (lento) e `2.0` (rápido).")
    
    filtro = f"atempo={velocidade}"
    texto_para_falar = f"{ctx.author.display_name} disse: {texto}"
    await play_tts(ctx.message, texto_para_falar, filtro_global=filtro)

@bot.command(name='mudarprefixo')
@commands.has_permissions(administrator=True)
async def mudarprefixo(ctx, novo_prefixo: str):
    config = carregar_config()
    guild_id = str(ctx.guild.id)
    config = init_guild_config(config, guild_id)
    config["servidores"][guild_id]["prefixo"] = novo_prefixo
    salvar_config(config)
    await ctx.send(f"✅ Prefixo alterado para: `{novo_prefixo}`")

@bot.command(name='setcanal')
@commands.has_permissions(administrator=True)
async def setcanal(ctx):
    config = carregar_config()
    guild_id = str(ctx.guild.id)
    config = init_guild_config(config, guild_id)
    if "canais_tts" not in config["servidores"][guild_id]: config["servidores"][guild_id]["canais_tts"] = []
        
    if ctx.channel.id not in config["servidores"][guild_id]["canais_tts"]:
        config["servidores"][guild_id]["canais_tts"].append(ctx.channel.id)
        salvar_config(config)
        await ctx.send(f"✅ Canal {ctx.channel.mention} adicionado à lista!")
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
        await ctx.send(f"✅ Canal {ctx.channel.mention} removido da lista!")

@bot.command(name='listacanais')
async def listacanais(ctx):
    config = carregar_config()
    canais = config.get("servidores", {}).get(str(ctx.guild.id), {}).get("canais_tts", [])
    if not canais:
        await ctx.send("📜 Lendo mensagens de **todos** os canais de texto!")
    else:
        lista = "\n".join([f"<#{c}>" for c in canais])
        await ctx.send(f"📜 **Canais permitidos para TTS:**\n{lista}")

@bot.command(name='voz')
async def mudar_voz(ctx, escolha: int):
    if escolha in [1, 2, 3, 4, 5]:
        config = carregar_config()
        if "usuarios" not in config: config["usuarios"] = {}
        config["usuarios"][str(ctx.author.id)] = escolha
        salvar_config(config)
        await ctx.send(f"✅ Voz alterada para a opção **{escolha}**!")

@bot.command(name='blocktts')
@commands.has_permissions(administrator=True)
async def blocktts(ctx, membro: discord.Member):
    config = carregar_config()
    guild_id = str(ctx.guild.id)
    config = init_guild_config(config, guild_id)
    if "bloqueados" not in config["servidores"][guild_id]: config["servidores"][guild_id]["bloqueados"] = {}
    config["servidores"][guild_id]["bloqueados"][str(membro.id)] = "perm"
    salvar_config(config)
    await ctx.send(f"🚫 {membro.mention} foi **bloqueado permanentemente** de usar o TTS.")

@bot.command(name='unblocktts')
@commands.has_permissions(administrator=True)
async def unblocktts(ctx, membro: discord.Member):
    config = carregar_config()
    guild_id = str(ctx.guild.id)
    bloqueados = config.get("servidores", {}).get(guild_id, {}).get("bloqueados", {})
    if str(membro.id) in bloqueados:
        del config["servidores"][guild_id]["bloqueados"][str(membro.id)]
        salvar_config(config)
        await ctx.send(f"✅ {membro.mention} foi **desbloqueado**.")

@bot.command(name='entrar')
async def entrar(ctx):
    if ctx.author.voice:
        await ctx.author.voice.channel.connect()
        await ctx.send("🔊 Cheguei na call!")

@bot.command(name='sair')
async def sair(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("🔇 Saí da call.")

@bot.command(name='log')
async def log(ctx):
    prefixo = get_prefix(bot, ctx.message)
    embed = discord.Embed(title="🚀 Changelog - Update de Luxo", color=discord.Color.gold())
    embed.add_field(name="🆕 Novidades", value=(
        "• **Auto-Desconectar:** O bot agora sai sozinho se a call ficar vazia.\n"
        "• **Novo Efeito 'Grave':** Novo filtro de equalizador para voz grossa e profunda.\n"
        "• **Fix Efeito 'Grossa':** Matemática ajustada para não bugar o áudio.\n"
        "• **Efeitos Parciais:** Digite `<eco: texto>` para aplicar efeitos no meio da frase!\n"
        "• **Modo Automático:** O bot entra na call sozinho se ela estiver vazia.\n"
        "• **Filtro Family Friendly:** Troca palavrões por BIP! Configure a sua lista.\n"
        "• **Dicionário (Aliases):** Ensine gírias para o bot pronunciar corretamente.\n"
        "• **Anti-Links:** Links longos são resumidos em áudio."
    ), inline=False)
    await ctx.send(embed=embed)

@bot.command(name='menu')
async def menu(ctx):
    p = get_prefix(bot, ctx.message)
    embed = discord.Embed(title="🤖 Painel de Controle Avançado", color=discord.Color.blue())
    
    embed.add_field(name="⚙️ Sistemas e Canais", value=f"`{p}modoautomatico on/off`\n`{p}setcanal` | `{p}removercanal` | `{p}listacanais`\n`{p}mudarprefixo <novo>`", inline=False)
    
    embed.add_field(name="🎙️ Voz e Efeitos", value=f"`{p}voz <num>` - Muda voz\n**Ex parcial:** Olá `<eco: mundo>`\n**Ex Global:** `{p}efeito alien Olá`\nEfeitos: `fina, grossa, grave, eco, alien, estourado, radio, fantasma`", inline=False)
    
    embed.add_field(name="📖 Dicionário e Palavrões", value=f"`{p}ensinar <palavra> <tradução>`\n`{p}esquecer <palavra>` | `{p}dicionario`\n`{p}ativarpalavrao` | `{p}addpalavrao <palavra>`", inline=False)
    
    await ctx.send(embed=embed)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Você não tem permissão para usar este comando.")

keep_alive()
TOKEN = os.environ.get("TOKEN")
bot.run(TOKEN)
