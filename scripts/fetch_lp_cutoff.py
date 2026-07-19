"""
Busca as ligas Challenger, Grandmaster e Master das filas Solo/Duo
(RANKED_SOLO_5x5) e Flex (RANKED_FLEX_SR) no servidor BR1, e registra a
"linha de corte" de cada liga em um histórico local
(docs/data/history.json), separado por fila.

A Riot às vezes demora a sincronizar a lista pública de uma liga com o
tier real do jogador (ex: um jogador que já caiu pra Mestre ainda
aparece, por um tempo, na lista de entries do Desafiante). Isso cria
"resíduos" no fim de cada lista, com LP bem abaixo do que deveria.

Em vez de chutar uma posição de rank fixa (frágil — muda com a
população, a fila e o tempo), usamos uma regra que sempre deveria valer
mesmo com atraso de sincronização: nenhum jogador do Mestre pode ter
mais LP do que o corte real do Grão-Mestre (senão já teria sido
promovido), e nenhum jogador do Grão-Mestre pode ter mais LP do que o
corte real do Desafiante. Ou seja: o maior LP de uma liga vira o "piso"
pra filtrar resíduos na liga de cima. Isso se ajusta sozinho à
população real de cada fila, sem números fixos.

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


def sorted_lps(league_json: dict) -> list:
    entries = league_json.get("entries", [])
    return sorted((e["leaguePoints"] for e in entries), reverse=True)


def tier_stats(lps: list, floor_lp) -> dict:
    """
    lps: lista de LP da liga, já ordenada do maior pro menor.
    floor_lp: maior LP observado na liga imediatamente abaixo (ou None,
              pra liga mais baixa — Mestre — que não tem piso de referência).
    """
    if not lps:
        return {
            "cutoff_lp": None,
            "raw_min_lp": None,
            "top_lp": None,
            "player_count": 0,
            "clean_player_count": 0,
            "floor_lp": floor_lp,
        }

    clean = [lp for lp in lps if floor_lp is None or lp > floor_lp]

    if clean:
        cutoff_lp = clean[-1]  # menor LP entre os que passaram no filtro
    elif floor_lp is not None:
        # Nenhuma entry ficou acima do piso — melhor estimativa disponível
        cutoff_lp = floor_lp + 1
    else:
        cutoff_lp = lps[-1]

    return {
        "cutoff_lp": cutoff_lp,              # linha de corte "oficial" (filtrada)
        "raw_min_lp": lps[-1],               # menor LP bruto, sem filtro (referência/debug)
        "top_lp": lps[0],
        "player_count": len(lps),
        "clean_player_count": len(clean),
        "floor_lp": floor_lp,
    }


def fetch_queue_summary(queue: str, api_key: str) -> dict:
    challenger_json = fetch(f"challengerleagues/by-queue/{queue}", api_key)
    grandmaster_json = fetch(f"grandmasterleagues/by-queue/{queue}", api_key)
    master_json = fetch(f"masterleagues/by-queue/{queue}", api_key)

    challenger_lps = sorted_lps(challenger_json)
    grandmaster_lps = sorted_lps(grandmaster_json)
    master_lps = sorted_lps(master_json)

    # Mestre não tem liga de referência abaixo (fora do escopo aqui), então
    # usamos o valor bruto normalmente (não é exibido no dashboard mesmo).
    master_stats = tier_stats(master_lps, floor_lp=None)

    # Grão-Mestre é filtrado usando o maior LP do Mestre como piso.
    grandmaster_stats = tier_stats(grandmaster_lps, floor_lp=master_stats["top_lp"])

    # Desafiante é filtrado usando o maior LP bruto do Grão-Mestre como piso
    # (o teto de uma liga não muda ao filtrarmos a cauda dela, então tanto
    # faz usar o bruto ou o limpo aqui).
    challenger_stats = tier_stats(challenger_lps, floor_lp=grandmaster_stats["top_lp"])

    return {
        "challenger": challenger_stats,
        "grandmaster": grandmaster_stats,
        "master": master_stats,
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
