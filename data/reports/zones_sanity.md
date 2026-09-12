# Zones sanity report — season 2526

## ENG-Premier League

- teams rated: 20; unjoined vs fixtures: none
- Spearman(attack zones, goals scored): **0.92**
- Spearman(defense zones, xGA prevented): **0.95** (consistency check)
- Spearman(defense zones, goals prevented): **0.55** (ceiling = corr(xGA,GA) = 0.53)
- top-5 attack zones: Manchester City, Arsenal, Manchester Utd, Chelsea, Liverpool
- top-5 actual scorers: Manchester City, Arsenal, Manchester Utd, Liverpool, Bournemouth
- top-5 defense zones: Arsenal, Manchester City, Manchester Utd, Liverpool, Brighton
- top-5 actual defenses (fewest conceded): Arsenal, Manchester City, Brighton, Sunderland, Aston Villa
- dead zones (<=2 distinct ratings): none

## ESP-La Liga

- teams rated: 20; unjoined vs fixtures: none
- Spearman(attack zones, goals scored): **0.74**
- Spearman(defense zones, xGA prevented): **0.98** (consistency check)
- Spearman(defense zones, goals prevented): **0.67** (ceiling = corr(xGA,GA) = 0.63)
- top-5 attack zones: Barcelona, Real Madrid, Villarreal, Atlético Madrid, Real Betis
- top-5 actual scorers: Barcelona, Real Madrid, Villarreal, Atlético Madrid, Real Sociedad
- top-5 defense zones: Real Madrid, Getafe, Athletic Club, Osasuna, Barcelona
- top-5 actual defenses (fewest conceded): Real Madrid, Barcelona, Getafe, Rayo Vallecano, Atlético Madrid
- dead zones (<=2 distinct ratings): none

## ITA-Serie A

- teams rated: 20; unjoined vs fixtures: none
- Spearman(attack zones, goals scored): **0.93**
- Spearman(defense zones, xGA prevented): **0.98** (consistency check)
- Spearman(defense zones, goals prevented): **0.83** (ceiling = corr(xGA,GA) = 0.80)
- top-5 attack zones: Inter, Juventus, Atalanta, Como, Milan
- top-5 actual scorers: Inter, Como, Juventus, Roma, Napoli
- top-5 defense zones: Juventus, Inter, Como, Napoli, Roma
- top-5 actual defenses (fewest conceded): Como, Roma, Juventus, Milan, Inter
- dead zones (<=2 distinct ratings): none

## GER-Bundesliga

- teams rated: 18; unjoined vs fixtures: none
- Spearman(attack zones, goals scored): **0.87**
- Spearman(defense zones, xGA prevented): **0.92** (consistency check)
- Spearman(defense zones, goals prevented): **0.65** (ceiling = corr(xGA,GA) = 0.77)
- top-5 attack zones: Bayern Munich, RB Leipzig, Leverkusen, Stuttgart, Dortmund
- top-5 actual scorers: Bayern Munich, Stuttgart, Dortmund, Leverkusen, RB Leipzig
- top-5 defense zones: Dortmund, Bayern Munich, Freiburg, Frankfurt, RB Leipzig
- top-5 actual defenses (fewest conceded): Dortmund, Bayern Munich, RB Leipzig, Leverkusen, Stuttgart
- dead zones (<=2 distinct ratings): none

## FRA-Ligue 1

- teams rated: 18; unjoined vs fixtures: none
- Spearman(attack zones, goals scored): **0.96**
- Spearman(defense zones, xGA prevented): **0.98** (consistency check)
- Spearman(defense zones, goals prevented): **0.74** (ceiling = corr(xGA,GA) = 0.79)
- top-5 attack zones: Lens, PSG, Marseille, Monaco, Lyon
- top-5 actual scorers: PSG, Lens, Marseille, Monaco, Rennes
- top-5 defense zones: PSG, Lille, Lens, Toulouse, Strasbourg
- top-5 actual defenses (fewest conceded): PSG, Lens, Lille, Lyon, Le Havre
- dead zones (<=2 distinct ratings): none

## Verdict

GATE PASSED: all leagues correlate with reality, no dead zones, clean name joins.