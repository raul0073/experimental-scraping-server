import matplotlib.pyplot as plt
from mplsoccer import PyPizza, FontManager, add_image
from typing import List, Dict, Optional
import io
import base64
import requests
from PIL import Image
import json

RADAR_CATEGORIES = {
    "Attacking": [
        "Performance_Gls", "Performance_Ast", "Expected_xG", "Expected_xAG", "Standard_Sh/90"
    ],
    "Creativity": [
        "KP", "Expected_xA", "SCA_SCA", "GCA_GCA"
    ],
    "Progression": [
        "Progression_PrgC", "Progression_PrgP", "Carries_1/3", "PPA"
    ],
    "Defending": [
        "Tkl+Int", "Clr", "Int", "Blocks_Blocks", "Challenges_Tkl%"
    ],
    "Possession": [
        "Total_Cmp%", "Touches_Touches", "Take-Ons_Succ%", "Receiving_PrgR", "Carries_PrgDist"
    ],
} 

STAT_KEY_MAPPING = {
    # Attacking
    "Performance_Gls": ("standard", "Performance - Gls"),
    "Performance_Ast": ("standard", "Performance - Ast"),
    "Expected_xG": ("standard", "Expected - xG"),
    "Expected_xAG": ("standard", "Expected - xAG"),
    "Standard_Sh/90": ("shooting", "Standard - Sh/90"),

    # Creativity
    "KP": ("passing", "KP"),
    "Expected_xA": ("passing", "Expected - xA"),
    "SCA_SCA": ("goal_shot_creation", "SCA - SCA"),
    "GCA_GCA": ("goal_shot_creation", "GCA - GCA"),

    # Progression
    "Progression_PrgC": ("possession", "Carries - PrgC"),
    "Carries_1/3": ("possession", "Carries - 1/3"),
    "PPA": ("passing", "PPA"),
    "Progression_PrgP": ("standard", "Progression - PrgP"),

    # Defending
    "Tkl+Int": ("defense", "Tkl+Int"),
    "Clr": ("defense", "Clr"),
    "Int": ("defense", "Int"),
    "Blocks_Blocks": ("defense", "Blocks - Blocks"),
    "Challenges_Tkl%": ("defense", "Challenges - Tkl%"),

    # Possession
    "Total_Cmp%": ("passing", "Total - Cmp%"),
    "Touches_Touches": ("possession", "Touches - Touches"),
    "Take-Ons_Succ%": ("possession", "Take-Ons - Succ%"),
    "Receiving_PrgR": ("possession", "Receiving - PrgR"),
     "Carries_PrgDist": ("possession", "Carries - PrgDist"),  # ADD THIS
}

CATEGORY_COLORS = {
    "Attacking": "#1A78CF",
    "Creativity": "#FF9300",
    "Progression": "#D70232",
    "Defending": "#27AE60",
    "Possession": "#F2C94C"
}


class PlayerPlottingService:
    """Service to generate pizza charts for football players with full logging."""

    def __init__(self, all_players: List[Dict]):
        self.all_players = all_players
        self.font_normal = FontManager(
            'https://raw.githubusercontent.com/googlefonts/roboto/main/src/hinted/Roboto-Regular.ttf'
        )
        self.font_bold = FontManager(
            'https://raw.githubusercontent.com/googlefonts/roboto/main/src/hinted/Roboto-Bold.ttf'
        )
        self.font_italic = FontManager(
            'https://raw.githubusercontent.com/googlefonts/roboto/main/src/hinted/Roboto-Italic.ttf'
        )

    def _get_stat_value(self, player_stats: Dict, key: str) -> float:
        if key not in STAT_KEY_MAPPING:
            print(f"[DEBUG] Key '{key}' not mapped, returning 0")
            return 0.0
        group_name, stat_name = STAT_KEY_MAPPING[key]
        val = player_stats.get(group_name, {}).get(stat_name, None)
        if val is None:
            print(f"[WARN] Missing stat '{stat_name}' in group '{group_name}'")
            return 0.0
        try:
            return float(val)
        except Exception as e:
            print(f"[WARN] Cannot convert '{val}' to float for key '{key}': {e}")
            return 0.0

    def _get_best_in_league(self, stat_keys: List[str]) -> Dict[str, float]:
        best = {}
        for key in stat_keys:
            max_val = max(self._get_stat_value(p.get("stats", {}), key) for p in self.all_players)
            best[key] = max_val if max_val > 0 else 1.0
            print(f"[DEBUG] Best in league '{key}': {best[key]}")
        return best

    def _normalize_player_stats(self, player_stats: Dict, best_stats: Dict[str, float]) -> List[float]:
        normalized = []
        for k, best_val in best_stats.items():
            val = self._get_stat_value(player_stats, k)
            pct = round(val / best_val * 100, 2) if best_val > 0 else 0.0
            normalized.append(pct)
        return normalized

    def _load_player_image(self, url: Optional[str]) -> Optional[Image.Image]:
        if not url:
            print("[DEBUG] No player image URL provided")
            return None
        try:
            resp = requests.get(url)
            img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
            print("[DEBUG] Player image loaded successfully")
            return img
        except Exception as e:
            print(f"[WARN] Failed to load image from {url}: {e}")
            return None

    def plot_player_pizza(
        self,
        player: Dict,
        stat_keys: Optional[List[str]] = None,
        figsize: float = 8,
        dpi: int = 200  # improved quality
    ) -> str:

        if stat_keys is None:
            stat_keys = [k for cat in RADAR_CATEGORIES.values() for k in cat]

        print(f"[DEBUG] Generating pizza for player: {player.get('name')}")
        print("[DEBUG] Player stats:")
        print(json.dumps(player.get("stats", {}), indent=2))

        best_stats = self._get_best_in_league(stat_keys)
        values = self._normalize_player_stats(player.get("stats", {}), best_stats)

        print(f"[DEBUG] Stat keys: {stat_keys}")
        print(f"[DEBUG] Normalized values: {values}")

        # Build params and slice_colors dynamically
        params = [k.replace("_", "\n") for k in stat_keys]
        slice_colors = [CATEGORY_COLORS[next(cat for cat, keys in RADAR_CATEGORIES.items() if k in keys)]
                        for k in stat_keys]
        text_colors = ["#FFFFFF"] * len(params)

        # Load player image safely
        player_img = self._load_player_image(player.get("profile_img"))
    
        baker = PyPizza(
            params=params,
            background_color="#222222",
            straight_line_color="#000000",
            straight_line_lw=1,
            last_circle_color="#000000",
            last_circle_lw=1,
            other_circle_lw=0,
            inner_circle_size=20
        )

        fig, ax = baker.make_pizza(
            values,
            figsize=(figsize, figsize + 0.5),
            color_blank_space="same",
            slice_colors=slice_colors,
            value_colors=text_colors,
            value_bck_colors=slice_colors,
            blank_alpha=0.4,
            kwargs_slices=dict(edgecolor="#000000", zorder=2, linewidth=1),
            kwargs_params=dict(color="#F2F2F2", fontsize=11, fontproperties=self.font_normal.prop, va="center"),
            kwargs_values=dict(
                color="#F2F2F2", fontsize=11,
                fontproperties=self.font_normal.prop, zorder=3,
                bbox=dict(edgecolor="#000000", facecolor="cornflowerblue",
                        boxstyle="round,pad=0.2", lw=1)
            )
        )

        # Add player info text
        fig.text(
            0.515, 0.975,
            f"{player.get('name')} - {player.get('__meta__', {}).get('team', '')}",
            size=16, ha="center", fontproperties=self.font_bold.prop, color="#F2F2F2"
        )
        fig.text(
            0.515, 0.955,
            "Percentile Rank vs Top League Players",
            size=13, ha="center", fontproperties=self.font_bold.prop, color="#F2F2F2"
        )
        fig.text(
            0.99, 0.02,
            "data: fbref\ninspired by mplsoccer / slothfulwave612",
            size=9, fontproperties=self.font_italic.prop, color="#F2F2F2", ha="right"
        )

        # Add player image dead center if available
        if player_img:
            add_image(player_img, fig, left=0.5-0.065, bottom=0.5-0.065, width=0.13, height=0.13)  # dead center

            # Add category labels with colors
    # Add stacked category labels (vertical list) on the right
        y_start = 0.9
        y_step = 0.02
        x_pos = 0.92
        for i, (cat, color) in enumerate(CATEGORY_COLORS.items()):
            fig.text(
                x=x_pos,
                y=y_start - i * y_step,
                s=cat,
                fontsize=12,
                fontproperties=self.font_bold.prop,
                color=color,
                ha="left",
                va="center"
            )


        # Export as high-quality base64
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight", facecolor="#222222", dpi=dpi)
        plt.close(fig)
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode("utf-8")
        print(f"[DEBUG] Pizza chart generated, size={len(img_base64)} bytes")
        return img_base64

