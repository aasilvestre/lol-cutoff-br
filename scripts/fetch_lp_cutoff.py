"""
Busca as ligas Challenger, Grandmaster e Master das filas Solo/Duo
(RANKED_SOLO_5x5) e Flex (RANKED_FLEX_SR) no servidor BR1, e registra a
"linha de corte" de cada liga em um histórico local
(docs/data/history.json), separado por fila.

A Riot às vezes demora a sincronizar a lista pública de uma liga com o
tier real do jogador (ex: um jogador que já caiu pra Mestre ainda
aparece, por um tempo, na lista de entries do Desafiante). Pra não
depender de qual endpoint devolveu cada jogador, juntamos os três
retornos (Desafiante + Grão-Mestre + Mestre) numa lista só, ordenamos
por LP e definimos os cortes por POSIÇÃO no ranking geral:

- Top 200 (posições 1–200)  → grupo do Desafiante
- Próximos 500 (201–700)    → grupo do Grão-Mestre

Assim, um jogador mal classificado pela Riot (com LP baixo demais pra
estar de verdade onde o endpoint dele diz) simplesmente cai pra posição
correta na lista combinada, sem precisar de nenhum filtro manual.

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

# Tamanho-alvo de cada grupo no ranking geral combinado.
CHALLENGER_SIZE = 200
GRANDMASTER_SIZE = 500

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


def lps_from(league_json: dict) -> list:
    entries = league_json.get("entries", [])
    return [e["leaguePoints"] for e in entries]


def ranked_group_stats(all_lps_desc: list, start: int, target_size: int) -> dict:
    """Pega o grupo de tamanho `target_size` a partir da posição `start`
    (0-indexado) numa lista já ordenada do maior LP pro menor."""
    end = min(start + target_size, len(all_lps_desc))
    group = all_lps_desc[start:end]

    if not group:
        return {
            "cutoff_lp": None,
            "top_lp": None,
            "player_count": 0,
            "target_size": target_size,
        }

    return {
        "cutoff_lp": group[-1],   # menor LP do grupo = linha de corte
        "top_lp": group[0],
        "player_count": len(group),
        "target_size": target_size,
    }


def fetch_queue_summary(queue: str, api_key: str) -> dict:
    challenger_json = fetch(f"challengerleagues/by-queue/{queue}", api_key)
    grandmaster_json = fetch(f"grandmasterleagues/by-queue/{queue}", api_key)
    master_json = fetch(f"masterleagues/by-queue/{queue}", api_key)

    challenger_lps = lps_from(challenger_json)
    grandmaster_lps = lps_from(grandmaster_json)
    master_lps = lps_from(master_json)

    # Junta tudo numa lista única, ordenada do maior LP pro menor.
    all_lps_desc = sorted(challenger_lps + grandmaster_lps + master_lps, reverse=True)

    challenger_stats = ranked_group_stats(all_lps_desc, start=0, target_size=CHALLENGER_SIZE)
    grandmaster_stats = ranked_group_stats(
        all_lps_desc, start=challenger_stats["player_count"], target_size=GRANDMASTER_SIZE
    )

    # Mestre não tem um "corte" útil (é sempre perto de 0/1 LP), então só
    # guardamos os dados brutos vindos direto do endpoint dele.
    master_stats = {
        "cutoff_lp": min(master_lps) if master_lps else None,
        "top_lp": max(master_lps) if master_lps else None,
        "player_count": len(master_lps),
    }

    return {
        "challenger": challenger_stats,
        "grandmaster": grandmaster_stats,
        "master": master_stats,
        "total_apex_players": len(all_lps_desc),
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
