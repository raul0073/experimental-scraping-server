import logging
import os
import re
from dotenv import load_dotenv
from typing import List, Dict
from fastapi import HTTPException
from openai import OpenAI
from models.players import PlayerModel
import logging
import json
load_dotenv()

api_key = os.getenv("OPENAI_KEY")

client = OpenAI(api_key=api_key)
class AIService:

    @staticmethod
    def generate_player_stat_summary(player_name: str, stat_type: str, stats: List[Dict[str, str]]) -> str:
        try:
            stat_lines = "\n".join(
                f"- {item['label']}: {item['val']} (Rank: {item['rank']})" for item in stats
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
                    {"role": "system", "content": "You are a football/soccer data analyst."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=200,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"OpenAI summary generation failed: {str(e)}")

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
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.4,
            )

            raw_output = response.choices[0].message.content.strip()
            logging.debug(f"AI raw output: {raw_output}")

            # ✅ Strip markdown code block if exists
            if raw_output.startswith("```"):
                raw_output = re.sub(r"^```(?:json)?|```$", "", raw_output, flags=re.MULTILINE).strip()

            # ✅ Try parsing as JSON
            try:
                inferred_data = json.loads(raw_output)
            except json.JSONDecodeError as e:
                logging.error(f"JSON decoding failed: {e}")
                return players

            # ✅ Process players
            name_map = {p.name: p for p in players}
            for obj in inferred_data:
                name = obj.get("name")
                if name in name_map:
                    player = name_map[name]
                    player.role = obj.get("role", "")
                    player.foot = obj.get("foot", "")
                    player.shirt_number = obj.get("shirt_number", None)
                    logging.debug(f"✅ Matched: {name} — role: {player.role}, number: {player.shirt_number}")
                else:
                    logging.warning(f"⚠️  No match for name: {name}")

            return players

        except Exception as e:
            logging.error(f"AI enrichment failed: {e}")
            return players
        
        
    @staticmethod
    def build_prompt(players: List[PlayerModel]) -> str:
        lines = [f"- {p.name} ({p.position})" for p in players]

        return "\n".join([
            "Here is a list of football players and their general positions:",
            *lines,
            "",
            "Please return a JSON array in this format:",
            "[{'name': 'John Smith', 'role': 'RCM', 'shirt_number': 8, 'foot':'left'}, ...]"
        ])