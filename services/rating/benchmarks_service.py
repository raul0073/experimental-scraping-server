import logging
from collections import defaultdict
from typing import Dict, List

from models.team import TeamModel
from models.players import PlayerModel
from services.db.db_service import DBService


class PlayersBenchmarkService:
    VALID_POS_GROUPS = {"GK", "DF", "MF", "FW"}

    def __init__(self):
        self.raw_stats: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))

    def get_position_group(self, pos_str: str) -> str:
        pos = pos_str.split(",")[0].strip().upper()
        if pos in self.VALID_POS_GROUPS:
            return pos
        if pos.startswith("C") or pos.endswith("B"):
            return "DF"
        if pos.endswith("M"):
            return "MF"
        if pos in {"ST", "CF", "LW", "RW"}:
            return "FW"
        return "UNK"

    async def collect_stats(self):
        logging.info("Fetching all teams from DB...")
        teams: List[TeamModel] = DBService.get_all_teams()

        for team in teams:
            for player in team.players:
                if not player.position or not player.stats:
                    continue

                pos_group = self.get_position_group(player.position)
                if pos_group == "UNK":
                    continue

                for stat_type_records in player.stats.values():
                    if not isinstance(stat_type_records, list):
                        continue

                    for stat in stat_type_records:
                        if not self.is_valid_stat(stat):
                            continue

                        label = stat["label"].strip()
                        val = stat["val"]

                        if isinstance(val, str) or val is None:
                            continue

                        self.raw_stats[pos_group][label].append((val, player.name))

        total = sum(len(v) for d in self.raw_stats.values() for v in d.values())
        logging.info(f"Collected {total} valid stat entries for benchmarking.")

    def compute_benchmarks(self) -> Dict[str, Dict[str, dict]]:
        benchmarks: Dict[str, Dict[str, dict]] = {}

        for pos_group, stat_dict in self.raw_stats.items():
            benchmarks[pos_group] = {}
            for stat_key, entries in stat_dict.items():
                if not entries:
                    continue
                max_entry = max(entries, key=lambda x: x[0])
                max_val, player_name = max_entry
                benchmarks[pos_group][stat_key] = {
                    "max": round(max_val, 3),
                    "player": player_name
                }
        return benchmarks

    async def save_benchmarks(self):
        await self.collect_stats()
        benchmark_data = self.compute_benchmarks()

        logging.info("Benchmarks computed. Preview:\n")
        for pos, stats in benchmark_data.items():
            logging.info(f"🔹 {pos} ({len(stats)} keys)")
            for key, info in stats.items():
                logging.info(f"    {key}: {info['max']} (by {info['player']})")

        DBService.save_benchmarks(benchmark_data)
        logging.info("Benchmarks saved to DB.")

    @staticmethod
    def is_valid_stat(stat: dict) -> bool:
        excluded_labels = {
            "league", "season", "nation", "pos", "age", "born",
            "types_league", "types_season", "types_nation", "types_pos", "types_age", "types_born",
            "shot_creation_league", "shot_creation_season", "shot_creation_nation", "shot_creation_pos", "shot_creation_age", "shot_creation_born",
            "time_league", "time_season", "time_nation", "time_pos", "time_age", "time_born"
        }
        label = stat.get("label", "").strip().lower()
        return bool(label) and label not in excluded_labels