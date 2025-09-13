import matplotlib
matplotlib.use("Agg")
from fastapi import HTTPException
from services.fbref.loader import FBRefLoaderService
from models.mental.mental_categories import TEAM_MENTAL_MAPPING
from mplsoccer import VerticalPitch
import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
from scipy.ndimage import gaussian_filter
import numpy as np
import io
import base64
from typing import List, Dict, Optional, Union

# ----------------------
# Zone mapping by role (simplified)
# ----------------------
ROLE_ZONE_MAPPING = {
    "GK": {"x_range": [0, 10], "y_range": [0, 100]},
    "CB": {"x_range": [10, 40], "y_range": [20, 80]},
    "LCB": {"x_range": [10, 40], "y_range": [20, 50]},  # split CB horizontally
    "RCB": {"x_range": [10, 40], "y_range": [50, 80]},
    "LB": {"x_range": [10, 40], "y_range": [0, 30]},
    "LWB": {"x_range": [10, 40], "y_range": [0, 20]},  # optional defensive wing
    "RB": {"x_range": [10, 40], "y_range": [70, 100]},
    "RWB": {"x_range": [10, 40], "y_range": [80, 100]},
    "DM": {"x_range": [30, 50], "y_range": [20, 80]},
    "CM": {"x_range": [40, 60], "y_range": [20, 80]},
    "AM": {"x_range": [60, 80], "y_range": [30, 70]},
    "LW": {"x_range": [60, 90], "y_range": [0, 40]},
    "RW": {"x_range": [60, 90], "y_range": [60, 100]},
    "CF": {"x_range": [70, 120], "y_range": [30, 120]},
}

class TeamPlottingService:
    def __init__(self, league: str, season: int, team: Optional[str]):
        self.league = league
        self.season = season
        self.team = team
        self.all_team_stats = FBRefLoaderService.load_teams_stats(league, season)
        self.all_players = FBRefLoaderService.load_team_players(league, season, team)

        if not self.all_team_stats:
            raise HTTPException(status_code=404, detail="League stats not found")

    # ----------------------
    # Safe get
    # ----------------------
    @staticmethod
    def safe_get(data: Union[dict, list], key: str, default=None):
        if isinstance(data, dict):
            return data.get(key, default)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("team") == key:
                    return item
        return default

    # ----------------------
    # Normalize rank 0-100
    # ----------------------
    @staticmethod
    def normalize_rank(rank: int, total_teams: int) -> int:
        if not rank or total_teams <= 1:
            return 0
        return round((total_teams - rank) / (total_teams - 1) * 100)

    # ----------------------
    # Radar chart
    # ----------------------
    @staticmethod
    def plot_team_radar(league: str, season: int, team: str, stat_type: str, keys: List[str]) -> str:
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

        buf = io.BytesIO()
        fig.tight_layout()
        fig.savefig(buf, format="png", dpi=90, bbox_inches="tight")
        buf.seek(0)
        plt.close(fig)
        return base64.b64encode(buf.read()).decode("utf-8")

    # ----------------------
    # Scatter chart
    # ----------------------
    @staticmethod
    def plot_team_scatter(league: str, season: int, team: str, stat_type: str, keys: List[str]) -> str:
        teams_stats_raw = FBRefLoaderService.load_teams_stats(league, season).get(stat_type, [])
        team_stats = FBRefLoaderService.filter_stat_type_by_team(all_team_stats=teams_stats_raw, team=team)
        league_best = {k: max((t.get("metrics", {}).get(k, {}).get("value", 0) for t in teams_stats_raw), default=0) for k in keys}

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

        buf = io.BytesIO()
        fig.tight_layout()
        fig.savefig(buf, format="png", dpi=90, bbox_inches="tight")
        buf.seek(0)
        plt.close(fig)
        return base64.b64encode(buf.read()).decode("utf-8")

    # ----------------------
    # Default mental chart
    # ----------------------
    async def get_team_default_chart(self) -> dict:
        if not self.all_team_stats:
            raise HTTPException(status_code=404, detail="League/team stats not found")

        total_teams = len(next(iter(self.all_team_stats.values()), []))
        data = {}
        for category, metrics in TEAM_MENTAL_MAPPING.items():
            category_data = {}
            for m in metrics:
                stat_type, key = m["stat_type"], m["key"]
                stat_list = self.all_team_stats.get(stat_type, [])
                if not stat_list:
                    continue
                team_entry = next((s for s in stat_list if s.get("team", "").lower() == self.team.lower()), {})
                team_metrics = team_entry.get("metrics", {})

                team_value = team_metrics.get(key, {}).get("value", 0)
                team_rank = team_metrics.get(key, {}).get("rank")
                team_normalized = self.normalize_rank(team_rank, total_teams) if team_rank else 0

                league_best_entry = max(stat_list, key=lambda t: t.get("metrics", {}).get(key, {}).get("value", float("-inf")), default={})
                league_best_value = league_best_entry.get("metrics", {}).get(key, {}).get("value", 0)
                league_best_rank = league_best_entry.get("metrics", {}).get("rank", 1)
                league_best_team = league_best_entry.get("team", "")
                league_normalized = self.normalize_rank(league_best_rank, total_teams)

                category_data[key] = {
                    "team_value": team_value,
                    "team_rank": team_rank,
                    "team_normalized": team_normalized,
                    "league_best_value": league_best_value,
                    "league_best_team": league_best_team,
                    "league_normalized": league_normalized,
                }
            data[category] = category_data

        return {
            "league": self.league,
            "season": self.season,
            "team": self.team,
            "chart_type": "default",
            "data": data,
            "metrics": TEAM_MENTAL_MAPPING,
        }

    # ----------------------
    # Compute zone weights
    # ----------------------
    def _compute_zone_weights(self, attack: bool = True) -> np.ndarray:
        zone_weights = np.zeros(len(ZONES))
        if not self.all_players:
            return zone_weights

        for player in self.all_players:
            role = player.get("role")
            if role not in ROLE_ZONE_MAPPING:
                continue
            zones = ROLE_ZONE_MAPPING[role]
            stats = player.get("stats", {})

            if attack:
                contrib = stats.get("shooting", {}).get("Standard - Gls", 0) + stats.get("goal_shot_creation", {}).get("SCA - SCA", 0)
            else:
                contrib = stats.get("defense", {}).get("Tackles - Att 3rd", 0) + stats.get("defense", {}).get("Tackles - TklW", 0) + stats.get("defense", {}).get("Challenges - Tkl%", 0)

            if contrib <= 0:
                continue
            for z in zones:
                zone_weights[z] += contrib
        return zone_weights

    async def get_team_heatmaps(self) -> Dict[str, str]:
        """
        Returns attacking and defending heatmaps as base64 PNG images.
        Players with Playing Time - MP < 5 are ignored.
        """
        if not self.all_players:
            raise HTTPException(status_code=404, detail=f"No players found for {self.team}")

        # --- Debug info ---

        # --- Collect contributions ---
        x_attack, y_attack, w_attack = [], [], []
        x_defense, y_defense, w_defense = [], [], []

        for player in self.all_players:
            role = player.get("role")
            zone_cfg = ROLE_ZONE_MAPPING.get(role)
            if not zone_cfg:
                print(f"[DEBUG] Skipping {player.get('name')} - no zone for role {role}")
                continue

            stats = player.get("stats", {})

            # Skip players with very low playing time
            mp = stats.get("playing_time", {}).get("Playing Time - MP", 0)
            if mp < 5:
                print(f"[DEBUG] Skipping {player.get('name')} - only {mp} matches played")
                continue

            # --- Attacking score ---
            attack_score = (
                stats.get("shooting", {}).get("Standard - Gls", 0) * 3 +
                stats.get("shooting", {}).get("Expected - xG", 0) * 2 +
                stats.get("goal_shot_creation", {}).get("SCA - SCA", 0) * 1 +
                stats.get("goal_shot_creation", {}).get("GCA - GCA", 0) * 2
            )
            if attack_score > 0:
                n_points = 10  # fixed number of points per player
                x_a = np.random.uniform(zone_cfg["x_range"][0], zone_cfg["x_range"][1], n_points)
                y_a = np.random.uniform(zone_cfg["y_range"][0], zone_cfg["y_range"][1], n_points)
                x_attack.extend(x_a)
                y_attack.extend(y_a)
                # distribute attack score evenly across points
                w_attack.extend([attack_score / n_points] * n_points)

            # --- Defensive score ---
            defense_score = (
                stats.get("defense", {}).get("Tkl", 0) * 2 +
                stats.get("defense", {}).get("Int", 0) * 2 +
                stats.get("defense", {}).get("Blk", 0) * 1
            )
            if defense_score > 0:
                n_points = 10
                x_d = np.random.uniform(zone_cfg["x_range"][0], zone_cfg["x_range"][1], n_points)
                y_d = np.random.uniform(zone_cfg["y_range"][0], zone_cfg["y_range"][1], n_points)
                x_defense.extend(x_d)
                y_defense.extend(y_d)
                w_defense.extend([defense_score / n_points] * n_points)


        # --- Heatmap function ---
        def create_heatmap(x, y, weights, cmap="Reds") -> str:
            fig, ax = plt.subplots(figsize=(6, 10))
            pitch = VerticalPitch(pitch_type="statsbomb", line_zorder=1, pitch_color="#f4edf0")
            pitch.draw(ax=ax)
            fig.set_facecolor("#2c2c2c")

            bin_stat = pitch.bin_statistic(x, y, statistic="sum", bins=(6, 3), values=weights, normalize=True)
            pcm = pitch.heatmap(bin_stat, ax=ax, cmap=cmap, edgecolor="#f9f9f9")
            # Label percentages
            path_eff = [path_effects.withStroke(linewidth=1, foreground="#000000")]
            pitch.label_heatmap(bin_stat, color="#bbbbbb", fontsize=12, ax=ax,
                                ha="center", va="center", str_format="{:.0%}", path_effects=path_eff)
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
            buf.seek(0)
            plt.close(fig)
            return base64.b64encode(buf.read()).decode("utf-8")

        attack_heatmap = create_heatmap(x_attack, y_attack, w_attack, cmap="Reds")
        defense_heatmap = create_heatmap(x_defense, y_defense, w_defense, cmap="Blues")

        return {
            "attacking": attack_heatmap,
            "defending": defense_heatmap
        }