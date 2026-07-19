# Linha de Corte — Challenger / Grão-Mestre / Mestre (Solo/Duo e Flex BR)

Dashboard que acompanha, dia a dia, a menor quantidade de LP necessária
para estar em Challenger, Grão-Mestre e Mestre nas filas Solo/Duo e Flex
5x5 do servidor BR1, usando a Riot Games API.

- **Coleta**: GitHub Actions roda um cron todo dia às 23h50 (horário de
  Brasília) — 5 min depois do reset diário das ligas (23h45) — busca os
  dados na Riot API e commita em `docs/data/`.
- **Dashboard**: página estática em `docs/`, publicada via GitHub Pages,
  que lê `docs/data/history.json` e desenha os gráficos com Chart.js.

## Como colocar no ar

### 1. Criar o repositório
Suba esta pasta para um repositório novo no GitHub (pode ser público ou
privado — só lembre que se for privado, o GitHub Pages precisa de plano
que suporte isso, ou deixe público).

```bash
cd lol-lp-cutoff-br
git init
git add .
git commit -m "chore: setup inicial"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/lol-lp-cutoff-br.git
git push -u origin main
```

### 2. Cadastrar sua API key como Secret
No repositório: **Settings → Secrets and variables → Actions → New
repository secret**

- Nome: `RIOT_API_KEY`
- Valor: sua chave do [developer.riotgames.com](https://developer.riotgames.com)

> ⚠️ **Atenção**: a API key "pessoal" padrão da Riot expira a cada 24h.
> Se a sua for desse tipo, o cron vai parar de funcionar depois de 1 dia.
> Para uso contínuo, solicite uma **Personal API Key** de longa duração
> (aba "Apps" no developer portal, produto "Personal API Key" — é
> aprovação manual da Riot, mas gratuita) e atualize o Secret quando
> renovar.

### 3. Ativar o GitHub Pages
**Settings → Pages → Source**: escolha a branch `main` e a pasta `/docs`.
Depois de salvar, o GitHub te dá a URL pública (algo como
`https://SEU_USUARIO.github.io/lol-lp-cutoff-br/`).

### 4. Rodar o primeiro fetch manualmente
Não precisa esperar o cron: vá em **Actions → Fetch LoL LP Cutoff (BR
Flex) → Run workflow**. Isso já popula `docs/data/history.json` e o
GitHub Pages atualiza sozinho.

Depois disso, o job roda automaticamente todo dia às 23h50 (BRT).

## Sobre o horário do cron
GitHub Actions usa UTC. Brasília é UTC-3 o ano todo (sem horário de
verão desde 2019), então 23h45 BRT = 02h45 UTC. O workflow está
agendado para `50 2 * * *` (02h50 UTC / 23h50 BRT) — 5 minutos de
margem porque os crons do GitHub Actions podem atrasar alguns minutos
em horários de pico.

## Estrutura

```
.
├── .github/workflows/fetch-data.yml   # cron + commit automático
├── scripts/fetch_lp_cutoff.py         # chama a Riot API e grava o histórico
├── docs/
│   ├── index.html                     # dashboard
│   ├── style.css
│   ├── app.js                         # lê history.json e desenha os gráficos
│   └── data/
│       ├── history.json               # série histórica (usada no gráfico)
│       └── latest.json                # snapshot mais recente
└── requirements.txt
```

## O que é "linha de corte" aqui
Para cada liga (Challenger, Grão-Mestre, Mestre) e cada fila (Solo/Duo e
Flex), o script pega todos os jogadores retornados pela Riot API para
aquela liga/fila no BR e guarda o **menor LP entre eles** — que é, na
prática, o LP mínimo que alguém precisa ter naquele momento para estar
naquela liga.
