"""
Busca as ligas Challenger, Grandmaster e Master das filas Solo/Duo
(RANKED_SOLO_5x5) e Flex (RANKED_FLEX_SR) no servidor BR1, e registra a
"linha de corte" (menor LP dentro de cada liga) em um histórico local
(docs/data/history.json), separado por fila.

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


def summarize(league_json: dict) -> dict:
    entries = league_json.get("entries", [])
    if not entries:
        return {"cutoff_lp": None, "player_count": 0, "top_lp": None}
    lps = [e["leaguePoints"] for e in entries]
    return {
        "cutoff_lp": min(lps),      # menor LP = linha de corte da liga
        "top_lp": max(lps),         # LP do 1º colocado (bônus, útil pro dashboard)
        "player_count": len(entries),
    }


def fetch_queue_summary(queue: str, api_key: str) -> dict:
    challenger = fetch(f"challengerleagues/by-queue/{queue}", api_key)
    grandmaster = fetch(f"grandmasterleagues/by-queue/{queue}", api_key)
    master = fetch(f"masterleagues/by-queue/{queue}", api_key)
    return {
        "challenger": summarize(challenger),
        "grandmaster": summarize(grandmaster),
        "master": summarize(master),
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
