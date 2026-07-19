"""
Busca as ligas Challenger, Grandmaster e Master das filas Solo/Duo
(RANKED_SOLO_5x5) e Flex (RANKED_FLEX_SR) no servidor BR1, e registra a
"linha de corte" de cada liga em um histórico local
(docs/data/history.json), separado por fila.

A Riot às vezes demora a sincronizar a lista pública de uma liga com o
tier real do jogador (ex: um jogador que já caiu pra Mestre ainda
aparece, por um tempo, na lista de entries do Desafiante). Pra não
deixar esses "fantasmas" distorcerem o corte, em vez de pegar o menor
LP entre TODOS os jogadores retornados, ordenamos por LP e pegamos o
valor na posição de rank alvo (configurável abaixo) — que reflete o
tamanho "real" observado da liga, ignorando a cauda desatualizada.

Pensado para rodar logo após 23:45 (horário de Brasília), que é quando a
Riot recalcula as ligas Challenger/GM/Master no dia.
"""

import os
import json
from datetime import datetime, timezone, timedelta

import requests

PLATFORM = "br1"
QUEUES = ["RANKED_SOLO_5x5", "RANKED_FLEX_SR"]
BASE_URL = f"https://{PLATFORM}.api.riotgames.com/lol/league/v4"

# Posição de rank (1-indexado, contando do topo) usada como "corte oficial"
# de cada liga, pra ignorar entries desatualizados no fim da lista.
# Esses números vieram de observação manual no client do jogo e podem
# precisar de ajuste com o tempo, conforme a população ranqueada muda.
TARGET_RANK = {
    "challenger": 200,
    "grandmaster": 700,
}

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "data")
HISTORY_PATH = os.path.join(DATA_DIR, "history.json")
LATEST_PATH = os.path.join(DATA_DIR, "latest.json")

BRT = timezone(timedelta(hours=-3))


def get_api_key() -> str:
    key = os.environ.get("RIOT_API_KEY")
    if not key:
        raise RuntimeError("Variável de ambiente RIOT_API_KEY não definida.")
    return key


def fetch(endpoint: str, api_key: str) -> dict:
    url = f"{BASE_URL}/{endpoint}"
    resp = requests.get(url, headers={"X-Riot-Token": api_key}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def summarize(league_json: dict, league_name: str) -> dict:
    entries = league_json.get("entries", [])
    if not entries:
        return {
            "cutoff_lp": None,
            "raw_min_lp": None,
            "top_lp": None,
            "player_count": 0,
            "rank_used": None,
        }

    lps = sorted((e["leaguePoints"] for e in entries), reverse=True)
    target_rank = TARGET_RANK.get(league_name)

    if target_rank and len(lps) >= target_rank:
        cutoff_lp = lps[target_rank - 1]  # rank N = índice N-1 (lista já ordenada desc)
        rank_used = target_rank
    else:
        # Não tem jogadores suficientes pra alcançar o rank alvo (pode
        # acontecer na fila Flex, que tem população bem menor) — cai
        # de volta pro menor LP disponível.
        cutoff_lp = lps[-1]
        rank_used = len(lps)

    return {
        "cutoff_lp": cutoff_lp,          # linha de corte "oficial" (por posição de rank)
        "raw_min_lp": lps[-1],           # menor LP bruto entre todos os entries (referência/debug)
        "top_lp": lps[0],
        "player_count": len(lps),
        "rank_used": rank_used,
    }


def fetch_queue_summary(queue: str, api_key: str) -> dict:
    challenger = fetch(f"challengerleagues/by-queue/{queue}", api_key)
    grandmaster = fetch(f"grandmasterleagues/by-queue/{queue}", api_key)
    master = fetch(f"masterleagues/by-queue/{queue}", api_key)
    return {
        "challenger": summarize(challenger, "challenger"),
        "grandmaster": summarize(grandmaster, "grandmaster"),
        "master": summarize(master, "master"),
    }


def load_history() -> list:
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def main():
    api_key = get_api_key()
    os.makedirs(DATA_DIR, exist_ok=True)

    queues_data = {queue: fetch_queue_summary(queue, api_key) for queue in QUEUES}

    now_utc = datetime.now(timezone.utc)
    now_brt = now_utc.astimezone(BRT)

    snapshot = {
        "timestamp_utc": now_utc.isoformat(),
        "timestamp_brt": now_brt.isoformat(),
        "date_brt": now_brt.strftime("%Y-%m-%d"),
        "queues": {
            "solo": queues_data["RANKED_SOLO_5x5"],
            "flex": queues_data["RANKED_FLEX_SR"],
        },
    }

    history = load_history()

    # Evita duplicar se o job rodar 2x no mesmo dia (mantém o último do dia)
    history = [h for h in history if h.get("date_brt") != snapshot["date_brt"]]
    history.append(snapshot)
    history.sort(key=lambda h: h["timestamp_utc"])

    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    with open(LATEST_PATH, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    print("Snapshot salvo com sucesso:")
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
