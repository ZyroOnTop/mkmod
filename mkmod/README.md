# MK Mobile Mod — 7.4.0 (1449740)

Mod menu para Mortal Kombat Mobile via GitHub Actions.  
Zero instalação local. Tudo roda na nuvem.

## Como usar

### 1. Pegar a URL do XAPK

- Vai em **apkmirror.com** e busca **Mortal Kombat 7.4.0**
- Clica em **Download APK** → na página de download, clica com botão direito no link final → **Copiar endereço do link**
- Ou usa **apkpure.com** → mesma coisa

### 2. Rodar o workflow

- Vai na aba **Actions** do seu repo no GitHub
- Clica em **MK Mod Build — 7.4.0**
- Clica em **Run workflow**
- Cola a URL do XAPK no campo
- Clica em **Run workflow** (verde)

### 3. Baixar o APK

- Aguarda ~15-25 minutos
- Quando terminar, clica no run → rola até **Artifacts**
- Baixa **MK-Mobile-7.4.0-MODDED**

### 4. Instalar no celular

- Habilita **Fontes desconhecidas** nas configurações
- Desinstala o MK original (ou mantém — mas precisará aceitar reinstalação)
- Instala o APK baixado
- Na primeira abertura: **Configurações → Apps → MK Mobile → Permissões → Exibir sobre outros apps → Permitir**

## Features do mod

| Feature | O que faz |
|---|---|
| God Mode | Seu HP não cai |
| One Hit Kill | Mata qualquer inimigo com um hit |
| Dumb Bot | Bot para de atacar e bloquear |
| No Cooldown | Specials sempre disponíveis |
| Damage Multi | Multiplica seu dano (slider 1x–50x) |
| Defense Multi | Multiplica sua defesa (slider 1x–50x) |

## Offsets zerados?

Se o **offsets-report** artifact mostrar `0x0` em tudo:

1. Baixa o **libgame-so-1449740** artifact
2. Abre no Ghidra (ghidra-sre.org, grátis)
3. Import → AARCH64 LE 64-bit → auto-analyze
4. Busca `TakeDamage`, `GetHealth`, `GetCooldown` na Symbol Table
5. Edita `app/src/main/cpp/hack.h` com os offsets encontrados
6. Faz push → roda o workflow de novo

## Atualizar para versões futuras

1. Pega o XAPK da nova versão
2. Roda o workflow com a nova URL
3. Se os offsets derem 0x0, deriva no Ghidra
4. Atualiza `hack.h` e faz push
