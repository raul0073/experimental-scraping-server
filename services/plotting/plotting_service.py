import matplotlib
matplotlib.use("Agg")
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from io import BytesIO
import base64
from PIL import Image
import matplotlib.pyplot as plt
from PIL import Image
from mplsoccer import VerticalPitch, FontManager
import matplotlib.patheffects as path_effects
# mplsoccer import - same as your environment
from mplsoccer import VerticalPitch
# -------------------------
# Font for pitch text
# -------------------------
roboto_bold = FontManager(
    'https://raw.githubusercontent.com/google/fonts/main/apache/robotoslab/RobotoSlab%5Bwght%5D.ttf'
)
path_eff = [
    path_effects.Stroke(linewidth=3, foreground='black'),
    path_effects.Normal()
]

# -------------------------
# Dataclasses 
# -------------------------
@dataclass
class Coordinate:
    x: float
    y: float


@dataclass
class PositionLine4:
    GK: Coordinate
    RB: Coordinate
    RCB: Coordinate
    LCB: Coordinate
    LB: Coordinate
    RDM: Coordinate
    LDM: Coordinate
    RW: Coordinate
    CAM: Coordinate
    LW: Coordinate
    ST: Coordinate


@dataclass
class PositionLine5:
    GK: Coordinate
    RB: Coordinate
    RCB: Coordinate
    CB: Coordinate
    LCB: Coordinate
    LB: Coordinate
    RDM: Coordinate
    LDM: Coordinate
    CDM: Coordinate
    RM: Coordinate
    RCM: Coordinate
    CM: Coordinate
    LCM: Coordinate
    LM: Coordinate
    RW: Coordinate
    CAM: Coordinate
    LAM: Coordinate
    LW: Coordinate
    RCF: Coordinate
    ST: Coordinate
    LCF: Coordinate


@dataclass
class Formation:
    position_line4: PositionLine4
    position_line5: PositionLine5

    # (unused for coordinate lookup in this implementation)
    def get_positions_ids(self, formation_name: str) -> List[int]:
        if formation_name == '4231':
            return [1, 2, 3, 5, 6, 9, 11, 17, 19, 21, 23]
        raise ValueError(f"Formation {formation_name} not defined")


# -------------------------
# Plotter
# -------------------------
class BestXIPlotter:
    def plot_best_xi(best_11: List[dict], formation: str = "4231") -> str:
        # Dummy formation lines
        line4 = PositionLine4(
            GK=Coordinate(50, 5),
            RB=Coordinate(90, 35),
            RCB=Coordinate(70, 25),
            LCB=Coordinate(30, 25),
            LB=Coordinate(10, 35),
            RDM=Coordinate(65, 45),
            LDM=Coordinate(35, 45),
            RW=Coordinate(80, 65),
            CAM=Coordinate(50, 65),
            LW=Coordinate(20, 65),
            ST=Coordinate(50, 85),
        )
        line5 = PositionLine5(
            GK=Coordinate(50, 5),
            RB=Coordinate(90, 35),
            RCB=Coordinate(70, 25),
            CB=Coordinate(50, 25),
            LCB=Coordinate(30, 25),
            LB=Coordinate(10, 35),
            RDM=Coordinate(65, 45),
            LDM=Coordinate(35, 45),
            CDM=Coordinate(50, 45),
            RM=Coordinate(80, 45),
            RCM=Coordinate(65, 45),
            CM=Coordinate(50, 50),
            LCM=Coordinate(35, 45),
            LM=Coordinate(20, 45),
            RW=Coordinate(80, 65),
            CAM=Coordinate(50, 65),
            LAM=Coordinate(20, 65),
            LW=Coordinate(20, 65),
            RCF=Coordinate(70, 85),
            ST=Coordinate(50, 85),
            LCF=Coordinate(30, 85),
        )
        formation_obj = Formation(position_line4=line4, position_line5=line5)
        positions_ids = formation_obj.get_positions_ids(formation)

        player_names = [
            f"{p['name']}\n({p['role']}, M={round(p['mental']['m'],2)})"
            for p in best_11
        ]
        assigned_positions = {}
        for p in best_11:
            
            slot = BestXIPlotter.assign_side(player=p)
            assigned_positions[slot] = p
        pitch = VerticalPitch(pitch_type="statsbomb", pitch_color="grass", line_color="white")
        fig, ax = pitch.draw(figsize=(6, 8))

        # Scatter circles
        pitch.formation(
            formation,
            kind="scatter",
            positions=positions_ids,
            ax=ax,
            s=1200,
            c="red",
            edgecolors="black",
            zorder=2
        )

        # Text under circle
        pitch.formation(
            formation,
            kind="text",
            positions=positions_ids,
            text=player_names,
            ax=ax,
            va="top",
            ha="center",
            fontsize=11,
            fontproperties=roboto_bold.prop,
            color="white",
            path_effects=None
        )

        # Export base64 PNG
        buf = BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", dpi=80)
        buf.seek(0)
        img = Image.open(buf)
        buf_compressed = BytesIO()
        img.save(buf_compressed, format="PNG", optimize=True)
        buf_compressed.seek(0)
        plt.close(fig)

        return base64.b64encode(buf_compressed.read()).decode("utf-8")


    @staticmethod
    def assign_side(player: dict) -> str:
        role = player.get("role", "")
        pos_text = (player.get("position_text") or "").lower()
        foot = (player.get("foot") or "").lower()

        # ... (assign_side method as provided in the previous response)
        if role == "GK":
            return "GK"

        if role == "FB":
            if "left" in pos_text or foot == "left":
                return "LB"
            if "right" in pos_text or foot == "right":
                return "RB"
            return "FB"

        if role == "CB":
            if "left" in pos_text or foot == "left":
                return "LCB"
            if "right" in pos_text or foot == "right":
                return "RCB"
            return "CB"

        if role == "DM":
            return "DM"
        if role == "CM":
            if "left" in pos_text or foot == "left":
                return "LCM"
            if "right" in pos_text or foot == "right":
                return "RCM"
            return "CM"

        if role == "W":
            if "left" in pos_text or foot == "left":
                return "LW"
            if "right" in pos_text or foot == "right":
                return "RW"
            return "W"

        if role == "AM":
            if "left" in pos_text or foot == "left":
                return "LAM"
            if "right" in pos_text or foot == "right":
                return "RAM"
            return "CAM"

        if role == "CF":
            if "left" in pos_text or foot == "left":
                return "LCF"
            if "right" in pos_text or foot == "right":
                return "RCF"
            return "ST"

        return role