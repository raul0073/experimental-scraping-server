import logging
from typing import List
import matplotlib
import numpy as np
from models.players import PlayerModel
from models.plotting.plot import ChartMetric
from services.db.db_service import DBService
matplotlib.use('Agg')  # <<<< REQUIRED ON TOP!



class PlottingService:
    @staticmethod
    def generate_radar_chart(
        player: PlayerModel,
        metrics: List[ChartMetric],
        save_path: str = "radar_polygon.png",
        color: str = "#5B9BD5",
    ) -> str:
        import matplotlib.pyplot as plt
        from io import BytesIO
        import base64

        normalized = PlottingService.normalize_metrics_for_player(player, metrics)
        keys = [m.key for m in normalized]
        values = [m.value for m in normalized]

        num_vars = len(keys)
        if num_vars < 3 or len(values) != num_vars:
            raise ValueError("Need at least 3 normalized metrics with matching values")

        values += [values[0]]
        angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
        angles += [angles[0]]

        fig, ax = plt.subplots(figsize=(6, 6))
        fig.patch.set_facecolor("#111")
        ax.set_facecolor("#1c1919")
        ax.axis("off")

        for r in np.linspace(0.2, 1.0, 5):
            xs = [r * np.cos(a) for a in angles]
            ys = [r * np.sin(a) for a in angles]
            ax.plot(xs, ys, color="#444", linewidth=0.8, linestyle="dotted")

        for angle in angles[:-1]:
            ax.plot([0, np.cos(angle)], [0, np.sin(angle)], color="#444", linewidth=0.5)

        r_values = [v / 100 for v in values]
        x = [r * np.cos(a) for r, a in zip(r_values, angles)]
        y = [r * np.sin(a) for r, a in zip(r_values, angles)]
        ax.plot(x, y, color=color, linewidth=2)
        ax.fill(x, y, color=color, alpha=0.4)

        label_pad = 1.15
        for angle, label in zip(angles[:-1], keys):
            ax.text(
                label_pad * np.cos(angle),
                label_pad * np.sin(angle),
                label,
                ha="center",
                va="center",
                fontsize=11,
                color="white",
            )

        buf = BytesIO()
        fig.savefig(
            buf,
            format="png",
            dpi=180,
            bbox_inches="tight",
            facecolor=fig.get_facecolor(),
        )
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("utf-8")

    @staticmethod
    def generate_pizza_chart_mplsoccer(
        player_name: str,
        player_position: str,
        metrics: list[ChartMetric]
    ) -> str:
        from mplsoccer import PyPizza, FontManager
        from matplotlib.colors import to_rgba
        from matplotlib.patches import Patch
        from collections import defaultdict
        import matplotlib.pyplot as plt
        from io import BytesIO
        import base64

        font_bold2 = FontManager('https://raw.githubusercontent.com/google/fonts/main/apache/robotoslab/RobotoSlab[wght].ttf')
        normalized = PlottingService.normalize_metrics_for_player(player_position, metrics)

        keys = [PlottingService.wrap_label(m.key.replace("_", " ").replace("-", " ")) for m in normalized]
        values = [m.value for m in normalized]
        categories = [m.category for m in normalized]

        if len(keys) < 3 or len(values) != len(keys):
            raise ValueError("Need at least 3 normalized metrics with matching values")

        category_totals = defaultdict(float)
        for m in normalized:
            category_totals[m.category] += m.value

        sorted_cats = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
        ranked_cats = [cat for cat, _ in sorted_cats]

        COLOR_HIGH = "#1a78cf"
        COLOR_MID = "#ff9300"
        COLOR_LOW = "#d70232"

        def fade(hex_color: str, alpha: float = 0.80):
            return to_rgba(hex_color, alpha=alpha)

        cat_color_map = {}
        if len(ranked_cats) > 0: cat_color_map[ranked_cats[0]] = COLOR_HIGH
        if len(ranked_cats) > 1: cat_color_map[ranked_cats[1]] = COLOR_MID
        if len(ranked_cats) > 2: cat_color_map[ranked_cats[2]] = COLOR_LOW

        value_colors = [cat_color_map.get(m.category, "#999999") for m in normalized]
        slice_colors = [fade(cat_color_map.get(m.category, "#999999")) for m in normalized]

        baker = PyPizza(
            params=keys,
            background_color="#0f0f0f",
            straight_line_color="#444444",
            straight_line_lw=1,
            last_circle_lw=1,
            other_circle_lw=1,
            other_circle_ls="-.",
            inner_circle_size=1
        )

        fig, ax = baker.make_pizza(
            values,
            figsize=(8, 8.5),
            slice_colors=slice_colors,
            value_colors=value_colors,
            color_blank_space="same",
            
            value_bck_colors=["#222222"] * len(keys),
            param_location=110,
            kwargs_slices=dict(edgecolor="#0f0f0f", linewidth=0.8, zorder=1),
            kwargs_params=dict(color="white", fontsize=9),
            kwargs_values=dict(
                color="white",
                fontsize=12,
                bbox=dict(edgecolor="none", facecolor=slice_colors, boxstyle="round,pad=0.2"),
            ),
        )

        fig.text(
            0.5, 0.935, player_name,
            ha="center",
            fontproperties=font_bold2.prop,
            color="white",
            size=18
        )

        legend_labels = list(cat_color_map.items())
        x_text = 0.02  # Aligned to left
        y_start = 0.120
        y_gap = 0.035  # Vertical spacing

        for i, (cat, color) in enumerate(legend_labels):
            y = y_start - i * y_gap
            fig.text(
                x_text, y,
                cat.title().replace("_", " "),
                ha="left",
                fontproperties=font_bold2.prop,
                color=color,
                size=14
            )

        fig.subplots_adjust(top=0.85)
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("utf-8")

    
    
    @staticmethod
    def normalize_metrics_for_player(player_position: str, metrics: List[ChartMetric]) -> List[ChartMetric]:
            position_group = player_position.split(",")[0].strip().upper()

            full_benchmark_data = DBService.get_benchmarks()
            raw_benchmarks = full_benchmark_data.get(position_group)

            if not raw_benchmarks:
                logging.warning(f"⚠️ No benchmark data for position group: {position_group}")
                return []

            # Normalize all benchmark keys (once!)
            normalized_benchmarks = {
                k.strip().lower(): v for k, v in raw_benchmarks.items()
            }

            normalized_metrics = []

            for m in metrics:
                key_options = [
                    m.raw_key.strip().lower(),
                    m.key.strip().lower()
                ]

                benchmark = None
                tried_keys = []

                for key in key_options:
                    tried_keys.append(key)
                    benchmark = normalized_benchmarks.get(key)
                    if benchmark:
                        break

                if not benchmark or not benchmark.get("max"):
                    logging.warning(
                        f"⚠️ No benchmark found for '{m.key}' (tried: {tried_keys}) in {position_group}"
                    )
                    continue

                try:
                    max_val = benchmark["max"]
                    norm_val = round((m.value / max_val) * 100, 1) if max_val > 0 else 0.0

                    normalized_metrics.append(ChartMetric(
                        key=m.key,
                        raw_key=m.raw_key,
                        value=norm_val,
                        category=m.category
                    ))

                except Exception as e:
                    logging.error(
                        f"❌ Error normalizing '{m.raw_key}' for {position_group}: {e}"
                    )

            if not normalized_metrics:
                logging.warning(f"⚠️ No metrics normalized for {position_group} — all keys may have mismatched labels")

            return normalized_metrics
        
    @staticmethod
    def wrap_label(label: str) -> str:
        words = label.split()
        if len(words) <= 2:
            return label
        return " ".join(words[:2]) + "\n" + " ".join(words[2:])