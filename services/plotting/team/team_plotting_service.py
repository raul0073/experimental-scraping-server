from fastapi import HTTPException
import matplotlib
matplotlib.use("Agg")
from models.mental.mental_categories import TEAM_MENTAL_MAPPING
from services.fbref.loader import FBRefLoaderService

import matplotlib.pyplot as plt
from io import BytesIO
import base64
import numpy as np
from typing import Dict, List, Union

class TeamPlottingService:

    @staticmethod
    def safe_get(data: Union[dict, list], key: str, default=None):
        """Safely get value from dict or list."""
        if isinstance(data, dict):
            return data.get(key, default)
        elif isinstance(data, list):
            # If list of dicts, search for dict with 'team' == key
            for item in data:
                if isinstance(item, dict) and item.get("team") == key:
                    return item
        return default

    @staticmethod
    def plot_team_scatter(league: str, season: int, team: str, stat_type: str, keys: List[str]) -> str:
        import matplotlib.pyplot as plt
        from io import BytesIO
        import base64

        # Load raw team stats for this stat type (list of dicts)
        teams_stats_raw = FBRefLoaderService.load_teams_stats(league, season).get(stat_type, [])
        team_stats = FBRefLoaderService.filter_stat_type_by_team(all_team_stats=teams_stats_raw, team=team)

        # Compute league-best for each key directly from all teams
        league_best = {}
        for k in keys:
            max_val = 0
            for t in teams_stats_raw:
                val = t.get("metrics", {}).get(k, {}).get("value", 0)
                if val is not None and val > max_val:
                    max_val = val
            league_best[k] = max_val

        print(f"--- DEBUG: plot_team_scatter ---")
        print(f"League: {league}, Season: {season}, Team: {team}, Stat Type: {stat_type}")


        # Scatter plot
        team_values = [team_stats.get(k, {}).get("value", 0) for k in keys]
        league_values = [league_best.get(k, 0) for k in keys]

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.scatter(keys, team_values, color="blue", label=f"{team}", s=120)
        ax.scatter(keys, league_values, color="green", label="League Best", marker="X", s=120)
        ax.set_ylabel("Value")
        ax.set_title(f"{team} vs League Best ({stat_type})")
        ax.legend()
        ax.grid(True, linestyle="--", alpha=0.4)
        plt.xticks(rotation=45, ha="right")

        buf = BytesIO()
        fig.tight_layout()
        fig.savefig(buf, format="png", dpi=90, bbox_inches="tight")
        buf.seek(0)
        plt.close(fig)
        return base64.b64encode(buf.read()).decode("utf-8")

    @staticmethod
    def plot_team_radar(league: str, season: int, team: str, stat_type: str, keys: List[str]) -> str:
        """
        Radar chart comparing team stats vs league best (normalized 0-1 per key).
        """
        team_stats = TeamPlottingService.safe_get(
            FBRefLoaderService.load_teams_stats(league, season).get(stat_type, {}), team, {}
        )
        league_stats = FBRefLoaderService.load_league_stats(league, season).get(stat_type, {})

        if not team_stats or not league_stats:
            raise ValueError(f"No stats found for {team} or league for {stat_type}")

        team_values = np.array([team_stats.get(k, 0) for k in keys])
        league_max_values = np.array([max(league_stats.get(k, 1), 1) for k in keys])

        normalized_team = team_values / league_max_values
        normalized_league = np.ones_like(normalized_team)

        # Close the radar
        normalized_team = np.concatenate((normalized_team, [normalized_team[0]]))
        normalized_league = np.concatenate((normalized_league, [normalized_league[0]]))
        angles = np.linspace(0, 2 * np.pi, len(keys), endpoint=False).tolist()
        angles += angles[:1]

        fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
        ax.plot(angles, normalized_league, color="green", linewidth=2, linestyle="dashed", label="League Best")
        ax.fill(angles, normalized_league, color="green", alpha=0.1)
        ax.plot(angles, normalized_team, color="blue", linewidth=2, label=team)
        ax.fill(angles, normalized_team, color="blue", alpha=0.25)

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(keys, fontsize=8)
        ax.set_yticklabels([])
        ax.set_title(f"{team} Radar vs League Best ({stat_type})", fontsize=12)
        ax.legend(loc="upper right", bbox_to_anchor=(1.2, 1.1))

        buf = BytesIO()
        fig.tight_layout()
        fig.savefig(buf, format="png", dpi=90, bbox_inches="tight")
        buf.seek(0)
        plt.close(fig)
        return base64.b64encode(buf.read()).decode("utf-8")

    def normalize_rank(rank: int, total_teams: int) -> int:
        """Normalize rank to 0-100 scale where 100 is best (rank 1)."""
        if not rank or total_teams <= 1:
            return 0
        return round((total_teams - rank) / (total_teams - 1) * 100)

    @staticmethod
    async def get_team_default_chart(league: str, season: int, team: str):
        # Load all team stats
        all_team_stats = FBRefLoaderService.load_teams_stats(league, season)
        if not all_team_stats:
            raise HTTPException(status_code=404, detail="League/team stats not found")

        # Count teams for normalization
        sample_stat_type = next(iter(all_team_stats))
        total_teams = len(all_team_stats.get(sample_stat_type, []))

        data = {}

        for category, metrics in TEAM_MENTAL_MAPPING.items():
            category_data = {}

            for m in metrics:
                stat_type = m["stat_type"]
                key = m["key"]

                stat_list = all_team_stats.get(stat_type, [])
                if not stat_list:
                    continue

                # Team entry
                team_entry = next((s for s in stat_list if s.get("team", "").lower() == team.lower()), {})
                team_metrics = team_entry.get("metrics", {})

                team_value = team_metrics.get(key, {}).get("value", 0)
                team_rank = team_metrics.get(key, {}).get("rank", None)
                team_normalized = TeamPlottingService.normalize_rank(team_rank, total_teams) if team_rank else 0

                # League best
                league_best_entry = max(
                    stat_list,
                    key=lambda t: t.get("metrics", {}).get(key, {}).get("value", float("-inf")),
                    default={}
                )
                league_best_team = league_best_entry.get("team", "")
                league_best_value = league_best_entry.get("metrics", {}).get(key, {}).get("value", 0)
                league_best_rank = league_best_entry.get("metrics", {}).get(key, {}).get("rank", 1)
                league_normalized = TeamPlottingService.normalize_rank(league_best_rank, total_teams)

                category_data[key] = {
                    "team_value": team_value,
                    "team_rank": team_rank,
                    "team_normalized": team_normalized,
                    "league_best_value": league_best_value,
                    "league_best_team": league_best_team,
                    "league_normalized": league_normalized
                }

            data[category] = category_data

        return {
            "league": league,
            "season": season,
            "team": team,
            "chart_type": "default",
            "data": data,
            "metrics": TEAM_MENTAL_MAPPING
        }