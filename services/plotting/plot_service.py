import logging
from typing import List
import matplotlib
import numpy as np
from models.plotting.plot import ChartMetric
matplotlib.use('Agg')  # <<<< REQUIRED ON TOP!



class PlottingService:
    @staticmethod
    def generate_radar_chart(
        keys: List[str],
        values: List[float],
        player_name: str,
        save_path: str = "radar_polygon.png",
        color: str = "#5B9BD5",
    ) -> str:
        import matplotlib.pyplot as plt
        from io import BytesIO
        import base64
        num_vars = len(keys)
        if num_vars < 3 or len(values) != num_vars:
            raise ValueError("Need at least 3 metrics with matching values")

        # Close the loop
        values += [values[0]]
        angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
        angles += [angles[0]]

        fig, ax = plt.subplots(figsize=(6, 6))
        fig.patch.set_facecolor("#111")
        ax.set_facecolor("#1c1919")
        ax.axis("off")  # no frame

        # Draw grid
        for r in np.linspace(0.2, 1.0, 5):
            xs = [r * np.cos(a) for a in angles]
            ys = [r * np.sin(a) for a in angles]
            ax.plot(xs, ys, color="#444", linewidth=0.8, linestyle="dotted")

        # Draw radial lines
        for angle in angles[:-1]:
            ax.plot([0, np.cos(angle)], [0, np.sin(angle)], color="#444", linewidth=0.5)

        # Plot filled area
        r_values = [v / max(values[:-1]) for v in values]  # normalize 0–1
        x = [r * np.cos(a) for r, a in zip(r_values, angles)]
        y = [r * np.sin(a) for r, a in zip(r_values, angles)]
        ax.plot(x, y, color=color, linewidth=2)
        ax.fill(x, y, color=color, alpha=0.4)

        # Add labels
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
        img_bytes = buf.read()
        plt.close(fig)
        return base64.b64encode(img_bytes).decode("utf-8")


    @staticmethod
    def generate_pizza_chart_mplsoccer(
        player_name: str,
        metrics: list[ChartMetric]
    ) -> str:
        from mplsoccer import PyPizza, FontManager
        from matplotlib.colors import to_rgba
        from matplotlib.patches import Patch
        from collections import defaultdict
        import matplotlib.pyplot as plt
        from io import BytesIO
        import base64
        font_bold2 = FontManager('https://raw.githubusercontent.com/google/fonts/main/apache/robotoslab/'
                        'RobotoSlab[wght].ttf')
        # Extract data
        keys = [m.key.replace("_", " ") for m in metrics]
        values = [m.value for m in metrics]
        categories = [m.category for m in metrics]

        if len(keys) < 3 or len(values) != len(keys):
            raise ValueError("Need at least 3 metrics with matching values.")
        # 1. Calculate total value per category
        category_totals = defaultdict(float)
        for m in metrics:
            category_totals[m.category] += m.value

        # 2. Sort categories by total value
        sorted_cats = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
        ranked_cats = [cat for cat, _ in sorted_cats]

        # 3. Assign colors to categories
        COLOR_HIGH = "#22C55E"  # emerald
        COLOR_MID = "#3B82F6"   # blue
        COLOR_LOW = "#EF4444"   # red

        def fade(hex_color: str, alpha: float = 0.80):
            return to_rgba(hex_color, alpha=alpha)

        cat_color_map = {}
        if len(ranked_cats) > 0: cat_color_map[ranked_cats[0]] = COLOR_HIGH
        if len(ranked_cats) > 1: cat_color_map[ranked_cats[1]] = COLOR_MID
        if len(ranked_cats) > 2: cat_color_map[ranked_cats[2]] = COLOR_LOW

        # 4. Match each metric to its category color
        value_colors = [cat_color_map.get(m.category, "#999999") for m in metrics]
        slice_colors = [fade(cat_color_map.get(m.category, "#999999")) for m in metrics]

        # 5. Build pizza chart
        baker = PyPizza(
            params=keys,
            background_color="#0f0f0f",
            straight_line_color="#444444",
            straight_line_lw=1,
            last_circle_lw=1,
            other_circle_lw=1,
            other_circle_ls="-.",
            inner_circle_size=20
        )

        fig, ax = baker.make_pizza(
            values,
            figsize=(8, 8.5),
            slice_colors=slice_colors,
            value_colors=value_colors,
            color_blank_space="same",
            value_bck_colors=["#222222"] * len(keys),
            param_location=105,
            kwargs_slices=dict(edgecolor="#0f0f0f", linewidth=0.8, zorder=1),
            kwargs_params=dict(color="white", fontsize=12),
            kwargs_values=dict(
                color="white",
                fontsize=18,
                bbox=dict(
                    edgecolor="none", facecolor="#111111", boxstyle="round,pad=0.2"
                ),
            ),
        )

        legend_handles = [
        Patch(color=color, label=cat.title())
        for cat, color in cat_color_map.items()
    ]

        # title
        fig.text(
         0.5, 0.935, player_name,
        ha="center",
        fontproperties=font_bold2.prop,
        color="white",
        size=16
    )
        legend_labels = list(cat_color_map.items())  # [('general', '#3B82F6'), ...]

        x_start = 0.25
        x_gap = 0.20
        y_text = 0.900

        for i, (cat, color) in enumerate(legend_labels):
            x = x_start + i * x_gap

            fig.text(
                x, y_text,
                cat.title().replace("_", " "),
                ha="left",
                fontproperties=font_bold2.prop,
                color=color,     # 🎯 each label is colored directly
                size=14
            )

        fig.subplots_adjust(top=0.85)
        # 7. Render image
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("utf-8")