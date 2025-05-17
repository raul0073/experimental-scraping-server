import logging
import os
import re
from dotenv import load_dotenv
from typing import Any, List, Dict
from fastapi import HTTPException, logger
from openai import BaseModel, OpenAI
from models.players import PlayerModel
import logging
import json
from collections import defaultdict

load_dotenv()

api_key = os.getenv("OPENAI_KEY")

client = OpenAI(api_key=api_key)


class AIService:

    @staticmethod
    def generate_player_stat_summary(
        player_name: str, stat_type: str, stats: List[Dict[str, str]]
    ) -> str:
        try:
            stat_lines = "\n".join(
                f"- {item['label']}: {item['val']} (Rank: {item['rank']})"
                for item in stats
            )
            prompt = (
                f"You are a professional football/soccer data analyst.\n\n"
                f"Your job is to write a short, high-quality performance summary for {player_name}'s "
                f"{stat_type} stats during the 2024/25 League season, based on the following thinking process:\n\n"
                f"1. **Player Context First**:\n"
                f"   - Identify the player's full name, position, age (if available), and playing style.\n"
                f"   - Mention any notable context such as recent transfers, rumours, contract status, or tactical changes that impacted his role this season.\n\n"
                f"2. **Role-Aware Statistical Review**:\n"
                f"   - Evaluate the stats in a way that matches the player's position and natural role. Do not generalise or judge based on irrelevant stats.\n"
                f"   - Use the following position-based stat guidelines:\n"
                f"     - **Goalkeepers (GK)**: Evaluate save percentage, total saves, clean sheets, crosses claimed, aerial duels won, distribution accuracy (e.g., long ball success), and 1v1 performance.\n"
                f"     - **Defenders**: Focus on tackles, interceptions, blocks, clearances, aerial duels, and if applicable, passing contribution to build-up play.\n"
                f"     - **Midfielders**: Focus on passing accuracy, key passes, progressive carries, defensive work rate (tackles/interceptions), and transition play.\n"
                f"     - **Forwards**: Evaluate goals, assists, shots on target, xG, shot conversion rate, dribbles, and link-up play.\n\n"
                f"3. **Compare with Previous Seasons (Optional)**:\n"
                f"   - If notable, mention how this season compares to last season in terms of form, fitness, minutes played, or key metrics.\n\n"
                f"4. **Conclude with Professional Insight**:\n"
                f"   - Highlight clear strengths, areas to improve, and overall impact. Avoid vague praise. Be data-driven.\n"
                f"   - Keep the tone professional, British English, and grounded — no exaggerated language.\n\n"
                f"Data provided:\n{stat_lines}\n\n"
                f"Output must be under 100 words."
            )

            # v1.75.0
            response = client.chat.completions.create(
                model="gpt-4.1-nano",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a football/soccer data analyst.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=200,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"OpenAI summary generation failed: {str(e)}"
            )

    @staticmethod
    def complete_player_details(players: List[PlayerModel]) -> List[PlayerModel]:
        try:
            prompt = AIService.build_prompt(players)

            response = client.chat.completions.create(
                model="gpt-4.1-nano",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert football data analyst for the 2024–25 season."
                            "Given a player profile, your job is to assign the **most accurate tactical role** (e.g., LB, LWB, RCB, LCD, RB, RWB, CDM, CM, LCM, RCM, RM,LM, CAM, RW, LW, CF, ST)"
                            "You must return **exactly one** tactical role that best fits how this player is deployed in the current 2024–25 season."
                            "In addition to the role, return: full player name, most accurate tactical role, current squad number at club (simulated lookup if unknown) and dominant foot"
                            "your output on *club-level data only* and ignore national team deployments."
                            "Be strict: **no guesses**, no 'hybrid', 'either', or dual-position answers."
                            "Respond with a valid JSON list of objects with keys: name, role, shirt_number, and dominant foot."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
            )

            raw_output = response.choices[0].message.content.strip()
            logging.info(f"AI raw output: {raw_output}")

            # Strip markdown code block if exists
            if raw_output.startswith("```"):
                raw_output = re.sub(
                    r"^```(?:json)?|```$", "", raw_output, flags=re.MULTILINE
                ).strip()

            # Try parsing as JSON
            try:
                inferred_data = json.loads(raw_output)
            except json.JSONDecodeError as e:
                logging.error(f"JSON decoding failed: {e}")
                return players

            # Process players
            name_map = {p.name: p for p in players}
            for obj in inferred_data:
                name = obj.get("name")
                if name in name_map:
                    player = name_map[name]
                    player.role = obj.get("role", "")
                    player.foot = obj.get("foot", "")
                    player.shirt_number = obj.get("shirt_number", None)
                    logging.debug(
                        f"Matched: {name} — role: {player.role}, number: {player.shirt_number}"
                    )
                else:
                    logging.warning(f"No match for name: {name}")

            return players

        except Exception as e:
            logging.error(f"AI enrichment failed: {e}")
            return players

    @staticmethod
    def optimize_zone_scalers(
        zone_config: dict,
        all_team_stats: List[Dict[str, Any]],
        all_team_stats_against: List[Dict[str, Any]],
        all_players: List[PlayerModel],
    ) -> Dict[str, Dict[str, float]]:
        try:

            flat_stats = AIService.flatten_stats(all_team_stats)
            flat_stats_against = AIService.flatten_stats(all_team_stats_against)

            serializable_zone_config = {}
            for zid, zcfg in zone_config.items():
                if isinstance(zcfg, BaseModel):
                    serializable_zone_config[zid] = zcfg.model_dump()
                elif hasattr(zcfg, "model_dump"):
                    serializable_zone_config[zid] = zcfg.model_dump()
                else:
                    serializable_zone_config[zid] = zcfg

            prompt = AIService.build_zone_scaler_prompt(
                zone_config=serializable_zone_config,
                stats=flat_stats,
                stats_against=flat_stats_against,
            )
            logging.info("Zone scaler optimization prompt:\n%s", prompt)

            response = client.chat.completions.create(
                model="gpt-4.1-nano",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a football tactics and data optimization expert.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
                max_tokens=1800,
            )

            raw = response.choices[0].message.content.strip()
            logging.info("Raw optimize_zone_scalers response:\n%s", raw)
            # strip ``` fences if present
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()

            # First parse
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as e:
                logging.error(f"JSON decode failed on first pass: {e}\nRaw: {raw}")
                return {}

                    # validate type
            if not isinstance(parsed, dict):
                raise ValueError(f"optimize_zone_scalers returned non-dict: {type(parsed)}")

            # ensure weights are floats and in [0,1]
            for zid, weights in parsed.items():
                if not isinstance(weights, dict):
                    raise ValueError(f"Zone {zid} has invalid scaler block: {weights}")
                for k, v in weights.items():
                    parsed[zid][k] = float(v)

            return parsed

        except Exception as e:
            logging.error(f"Scaler optimization failed: {e}")
            return {}

    @staticmethod
    def build_prompt(players: List[PlayerModel]) -> str:
        lines = [f"- {p.name} ({p.position})" for p in players]

        return "\n".join(
            [
                "Here is a list of football players and their general positions:",
                *lines,
                "",
                "Please return a JSON array in this format:",
                "[{'name': 'John Smith', 'role': 'RCM', 'shirt_number': 8, 'foot':'left'}, ...]",
            ]
        )

    def flatten_stats(stat_rows: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Flattens a list of stat dictionaries into a single aggregated dict.

        Each entry in stat_rows is expected to be a dict where keys are stat names
        and values are numeric (int or float). Non-numeric and reserved keys are ignored.

        Example:
            [
                {"Blocks": 10, "Tackles": 5},
                {"Blocks": 7, "Passes": 100}
            ]
            -> {"Blocks": 17.0, "Tackles": 5.0, "Passes": 100.0}

        Args:
            stat_rows: List of stat dictionaries.

        Returns:
            Aggregated stat dictionary mapping each stat name to its total value.
        """
        totals = defaultdict(float)
        for row in stat_rows:
            # Convert Pydantic models or objects to plain dict
            if isinstance(row, BaseModel):
                data = row.model_dump()
            elif hasattr(row, "model_dump"):
                data = row.model_dump()
            elif hasattr(row, "dict"):
                data = row.dict()
            elif isinstance(row, dict):
                data = row
            else:
                continue

            for key, val in data.items():
                # skip reserved or nested properties
                if key in ("team", "against", "_id"):
                    continue
                try:
                    num = float(val)
                except (TypeError, ValueError):
                    continue
                totals[key] += num
        return dict(totals)



    def build_zone_scaler_prompt(
        zone_config: Dict[str, Any],
        stats: Dict[str, float],
        stats_against: Dict[str, float]
    ) -> str:
        """
        Builds a JSON prompt for GPT-4 to refine spatial zone_configs.
        Requirements:
        • Keep existing labels and positions unchanged.
        • Populate exactly four flat lists per zone:
            – pros.team    (our team's strengths metrics)
            – pros.against (metrics where limiting opponent is positive)
            – cons.team    (our team's weaknesses/errors)
            – cons.against (opponent's key strengths to minimize)
        • Use only keys from team_stats or team_stats_against.
        • Add metrics with high impact; remove those absent in stats.
        • Weights for metrics will be handled separately.
        • Output must be valid JSON mapping zone IDs to updated configs.
        """
        # ADDED: prepare a clean base structure preserving labels & positions
        base_config: Dict[str, Any] = {}
        for zid, cfg in zone_config.items():
            # ensure dict of primitives
            data = cfg.model_dump() if hasattr(cfg, "model_dump") else dict(cfg)
            base_config[zid] = {
                "label": data.get("label"),
                "positions": data.get("positions"),
                # initialize empty flat lists
                "pros": {"team": [], "against": []},
                "cons": {"team": [], "against": []}
            }

        system_msg = (
            "You are an expert football analytics AI. Optimize each zone configuration using season stats,"
            " capturing MENTAL (decision-making) and TECHNICAL (execution) performance."
        )

        # ADDED: example demonstrating exact output structure
        example = {
            "zoneX": {
                "label": "Example Zone",
                "positions": {"CM": 0.5},
                "pros": {"team": ["goals"], "against": ["miscontrols"]},
                "cons": {"team": ["passes_offside"], "against": ["goals"]}
            }
        }

        instructions = [
            "Use 'current_config' exactly as base; do not change labels or positions.",  # ADDED clarity
            "Populate four flat metric lists per zone: pros.team, pros.against, cons.team, cons.against.",
            "Include only metrics found in 'team_stats' or 'team_stats_against'.",
            "Add metrics with high variance or impact; remove metrics not in provided stats.",
            "Weights are not part of this prompt; return only the updated zone_config structure.",
            "Example output format:",
            json.dumps(example, indent=2)
        ]

        prompt = {
            "system": system_msg,
            "instructions": instructions,
            "current_config": base_config,
            "team_stats": stats,
            "team_stats_against": stats_against,
            "output_format": (
                "Return ONLY the zone_config JSON object mapping zone IDs to updated entries with four flat lists under",
                " pros.team, pros.against, cons.team, and cons.against. Do not include any additional keys."
            )
        }

        return json.dumps(prompt)

