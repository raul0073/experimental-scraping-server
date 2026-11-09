# Versus the market

generated 2026-11-09T10:43:24+00:00 · source football-data.co.uk · margin removal: **normalise**

Margin method on 11,309 joined historical rows: normalise 0.9655, Shin 0.9654. Shin changes market log loss by +0.0001 nats, inside the ±0.002 band where the simpler method is preferred

Odds column used, live rows: pinnacle_closing 0, pinnacle 0, average_closing 499, average 0  
Odds column used, historical rows: pinnacle_closing 10,608, pinnacle 4, average_closing 697, average 0  
Odds column used, all rows: pinnacle_closing 10,608, pinnacle 4, average_closing 1,196, average 0  

## Live record

Graded rows 501, joined 499 (99.6%).

Unjoined:

| league | kickoff | home | away | retro |
|---|---|---|---|---|
| ESP-La Liga | 2026-09-16 | Levante | Athletic Club | False |
| ESP-La Liga | 2026-10-10 | Rayo Vallecano | Athletic Club | False |

| split | n | model LL | market LL | gap | uniform LL | base-rate LL | Brier m / mkt | acc m / mkt |
|---|---|---|---|---|---|---|---|---|
| live | 353 | 0.9715 | 0.9298 | 0.0417 | 1.0986 | 1.0513 | 0.5755 / 0.5478 | 55.2% / 57.5% |
| reconstructed | 146 | 0.9909 | 0.9783 | 0.0126 | 1.0986 | 1.0763 | 0.5897 / 0.5817 | 55.5% / 54.1% |
| all | 499 | 0.9772 | 0.9440 | 0.0332 | 1.0986 | 1.0597 | 0.5796 / 0.5577 | 55.3% / 56.5% |

### By league (all joined graded rows)

| league | n | model LL | market LL | gap |
|---|---|---|---|---|
| ENG-Premier League | 100 | 1.0055 | 1.0108 | -0.0053 |
| ESP-La Liga | 118 | 0.9677 | 0.9037 | 0.0640 |
| ITA-Serie A | 110 | 0.9380 | 0.9041 | 0.0339 |
| GER-Bundesliga | 81 | 0.9916 | 0.9696 | 0.0220 |
| FRA-Ligue 1 | 90 | 0.9931 | 0.9482 | 0.0449 |

### Disagreement

| max |model − market| | n | model LL | market LL | better |
|---|---|---|---|---|
| <0.05 | 153 | 0.9423 | 0.9349 | market |
| 0.05–0.10 | 169 | 1.0556 | 1.0495 | market |
| 0.10–0.15 | 110 | 0.9295 | 0.8727 | market |
| ≥0.15 | 67 | 0.9377 | 0.8156 | market |

Rows above 0.08 (graded only):

| league | kickoff | home | away | retro | model H/D/A | market H/D/A | max diff | result | better |
|---|---|---|---|---|---|---|---|---|---|
| ENG-Premier League | 2026-09-12 | Chelsea | Hull City | False | 0.469/0.243/0.287 | 0.780/0.141/0.079 | 0.310 | draw | model |
| FRA-Ligue 1 | 2026-08-30 | Rennes | Le Mans | True | 0.398/0.308/0.295 | 0.699/0.181/0.121 | 0.301 | home | market |
| ESP-La Liga | 2026-11-07 | Valencia | Real Madrid | False | 0.264/0.253/0.484 | 0.087/0.145/0.767 | 0.284 | away | market |
| ENG-Premier League | 2026-08-22 | Hull City | Manchester Utd | True | 0.304/0.262/0.433 | 0.111/0.185/0.704 | 0.271 | home | model |
| ESP-La Liga | 2026-09-16 | Atlético Madrid | Osasuna | False | 0.460/0.287/0.253 | 0.728/0.175/0.097 | 0.268 | home | market |
| ENG-Premier League | 2026-09-19 | Nottingham | Coventry City | False | 0.316/0.335/0.349 | 0.579/0.240/0.181 | 0.263 | away | model |
| FRA-Ligue 1 | 2026-09-05 | Nice | Le Mans | True | 0.319/0.329/0.352 | 0.571/0.237/0.192 | 0.252 | draw | model |
| ESP-La Liga | 2026-11-01 | Racing Sant | Real Madrid | False | 0.209/0.246/0.544 | 0.089/0.122/0.789 | 0.244 | away | market |
| GER-Bundesliga | 2026-09-12 | Dortmund | Paderborn 07 | False | 0.511/0.261/0.227 | 0.752/0.149/0.099 | 0.241 | home | market |
| ESP-La Liga | 2026-08-30 | Real Madrid | Málaga | True | 0.637/0.226/0.136 | 0.868/0.088/0.043 | 0.231 | home | market |
| ESP-La Liga | 2026-09-04 | Real Betis | Real Madrid | True | 0.290/0.287/0.424 | 0.160/0.188/0.652 | 0.229 | home | model |
| ITA-Serie A | 2026-08-29 | Fiorentina | Frosinone | True | 0.318/0.349/0.333 | 0.545/0.241/0.214 | 0.227 | away | model |
| ENG-Premier League | 2026-09-04 | Ipswich Town | Liverpool | True | 0.332/0.308/0.360 | 0.195/0.219/0.586 | 0.226 | away | market |
| ENG-Premier League | 2026-09-05 | Manchester City | Coventry City | True | 0.576/0.251/0.173 | 0.795/0.132/0.073 | 0.219 | home | market |
| FRA-Ligue 1 | 2026-11-07 | Auxerre | Paris FC | False | 0.315/0.313/0.372 | 0.180/0.230/0.591 | 0.219 | away | market |
| FRA-Ligue 1 | 2026-09-18 | Monaco | Lens | False | 0.307/0.259/0.434 | 0.521/0.240/0.239 | 0.214 | home | market |
| ENG-Premier League | 2026-09-19 | Everton | Ipswich Town | False | 0.330/0.316/0.354 | 0.542/0.245/0.213 | 0.212 | home | market |
| ESP-La Liga | 2026-09-16 | Dep. A Coruña | Sevilla | False | 0.560/0.256/0.184 | 0.348/0.306/0.346 | 0.211 | away | market |
| FRA-Ligue 1 | 2026-09-20 | Marseille | PSG | False | 0.272/0.269/0.460 | 0.144/0.185/0.671 | 0.211 | away | market |
| GER-Bundesliga | 2026-08-29 | Mainz 05 | Paderborn 07 | True | 0.413/0.256/0.330 | 0.624/0.210/0.167 | 0.210 | draw | model |
| FRA-Ligue 1 | 2026-08-22 | Troyes | Paris FC | True | 0.491/0.245/0.264 | 0.286/0.268/0.447 | 0.205 | draw | market |
| ESP-La Liga | 2026-09-11 | Sevilla | Valencia | False | 0.333/0.305/0.362 | 0.536/0.267/0.197 | 0.203 | home | market |
| GER-Bundesliga | 2026-09-05 | Gladbach | Elversberg | True | 0.296/0.310/0.393 | 0.497/0.239/0.263 | 0.201 | away | model |
| ESP-La Liga | 2026-10-31 | Levante | Atlético Madrid | False | 0.291/0.261/0.448 | 0.155/0.198/0.647 | 0.199 | away | market |
| ESP-La Liga | 2026-09-13 | Celta Vigo | Málaga | False | 0.364/0.336/0.300 | 0.561/0.258/0.180 | 0.198 | draw | model |
| ENG-Premier League | 2026-09-05 | Hull City | Aston Villa | True | 0.432/0.267/0.300 | 0.240/0.262/0.498 | 0.198 | draw | model |
| FRA-Ligue 1 | 2026-09-13 | Brest | PSG | False | 0.185/0.238/0.578 | 0.088/0.138/0.774 | 0.197 | away | market |
| GER-Bundesliga | 2026-09-18 | Bayern Munich | Union Berlin | False | 0.728/0.179/0.093 | 0.924/0.053/0.024 | 0.195 | home | market |
| ENG-Premier League | 2026-09-19 | Newcastle | Hull City | False | 0.398/0.262/0.341 | 0.593/0.220/0.187 | 0.195 | home | market |
| FRA-Ligue 1 | 2026-11-08 | Angers | Nice | False | 0.347/0.333/0.320 | 0.240/0.252/0.509 | 0.189 | away | market |
| ESP-La Liga | 2026-10-10 | Alavés | Atlético Madrid | False | 0.363/0.303/0.334 | 0.215/0.262/0.523 | 0.189 | away | market |
| ENG-Premier League | 2026-11-08 | Crystal Palace | Liverpool | False | 0.292/0.278/0.430 | 0.173/0.208/0.619 | 0.188 | away | market |
| FRA-Ligue 1 | 2026-09-19 | Angers | Troyes | False | 0.275/0.319/0.406 | 0.462/0.271/0.267 | 0.187 | home | market |
| ENG-Premier League | 2026-08-30 | Manchester Utd | Ipswich Town | True | 0.516/0.266/0.219 | 0.703/0.175/0.123 | 0.187 | home | market |
| GER-Bundesliga | 2026-09-04 | Stuttgart | Köln | True | 0.470/0.283/0.247 | 0.656/0.185/0.159 | 0.186 | home | market |
| ESP-La Liga | 2026-09-13 | Levante | Barcelona | False | 0.190/0.194/0.617 | 0.079/0.119/0.802 | 0.186 | away | market |
| ESP-La Liga | 2026-09-06 | Valencia | Barcelona | True | 0.216/0.207/0.577 | 0.090/0.148/0.762 | 0.185 | away | market |
| ESP-La Liga | 2026-10-24 | Atlético Madrid | Dep. A Coruña | False | 0.574/0.241/0.185 | 0.758/0.152/0.089 | 0.185 | home | market |
| FRA-Ligue 1 | 2026-10-09 | Lens | Lyon | False | 0.552/0.229/0.219 | 0.373/0.259/0.367 | 0.179 | home | model |
| ENG-Premier League | 2026-09-19 | Tottenham | Aston Villa | False | 0.323/0.335/0.342 | 0.501/0.251/0.248 | 0.178 | away | model |
| GER-Bundesliga | 2026-09-05 | Schalke 04 | Bayern Munich | True | 0.165/0.218/0.616 | 0.082/0.128/0.791 | 0.174 | draw | model |
| GER-Bundesliga | 2026-08-28 | Bayern Munich | Stuttgart | True | 0.603/0.215/0.182 | 0.777/0.128/0.095 | 0.174 | home | market |
| GER-Bundesliga | 2026-11-08 | Köln | Leverkusen | False | 0.285/0.308/0.407 | 0.198/0.222/0.580 | 0.173 | away | market |
| ENG-Premier League | 2026-10-25 | Hull City | Brentford | False | 0.270/0.329/0.401 | 0.193/0.233/0.573 | 0.172 | draw | model |
| ITA-Serie A | 2026-09-19 | Venezia | Lazio | False | 0.419/0.271/0.310 | 0.253/0.266/0.481 | 0.171 | away | market |
| GER-Bundesliga | 2026-09-20 | Schalke 04 | Elversberg | False | 0.334/0.335/0.331 | 0.505/0.240/0.255 | 0.171 | draw | model |
| GER-Bundesliga | 2026-09-13 | Elversberg | Bayern Munich | False | 0.168/0.194/0.638 | 0.080/0.113/0.806 | 0.168 | away | market |
| GER-Bundesliga | 2026-10-10 | Augsburg | Bayern Munich | False | 0.149/0.193/0.658 | 0.071/0.104/0.826 | 0.168 | draw | model |
| GER-Bundesliga | 2026-09-05 | Paderborn 07 | Freiburg | True | 0.388/0.289/0.323 | 0.263/0.247/0.490 | 0.167 | away | market |
| ENG-Premier League | 2026-09-13 | Coventry City | Brighton | False | 0.350/0.320/0.330 | 0.255/0.250/0.495 | 0.165 | away | market |
| FRA-Ligue 1 | 2026-09-11 | Rennes | Marseille | False | 0.317/0.299/0.384 | 0.477/0.244/0.278 | 0.161 | home | market |
| ITA-Serie A | 2026-08-28 | Milan | Venezia | True | 0.478/0.286/0.236 | 0.639/0.213/0.149 | 0.161 | home | market |
| ENG-Premier League | 2026-08-22 | Ipswich Town | Sunderland | True | 0.493/0.273/0.234 | 0.333/0.293/0.374 | 0.160 | home | model |
| ESP-La Liga | 2026-10-12 | Levante | Sevilla | False | 0.482/0.266/0.252 | 0.323/0.290/0.387 | 0.159 | draw | market |
| ESP-La Liga | 2026-10-17 | Real Betis | Barcelona | False | 0.248/0.239/0.512 | 0.156/0.173/0.671 | 0.159 | away | market |
| FRA-Ligue 1 | 2026-11-08 | Le Mans | Monaco | False | 0.292/0.284/0.425 | 0.179/0.238/0.584 | 0.159 | draw | model |
| ESP-La Liga | 2026-08-22 | Espanyol | Real Madrid | True | 0.212/0.268/0.520 | 0.128/0.193/0.678 | 0.158 | away | market |
| FRA-Ligue 1 | 2026-10-30 | Le Havre | PSG | False | 0.186/0.232/0.581 | 0.107/0.154/0.739 | 0.157 | away | market |
| ESP-La Liga | 2026-11-07 | Osasuna | Athletic Club | False | 0.380/0.303/0.317 | 0.244/0.282/0.474 | 0.157 | draw | model |
| ESP-La Liga | 2026-10-25 | Real Sociedad | Levante | False | 0.465/0.271/0.264 | 0.622/0.199/0.180 | 0.156 | home | market |
| ESP-La Liga | 2026-10-10 | Real Madrid | Villarreal | False | 0.559/0.236/0.205 | 0.713/0.162/0.124 | 0.155 | home | market |
| GER-Bundesliga | 2026-11-07 | Mainz 05 | Bayern Munich | False | 0.206/0.197/0.597 | 0.108/0.143/0.749 | 0.152 | away | market |
| GER-Bundesliga | 2026-09-05 | Leverkusen | Union Berlin | True | 0.548/0.262/0.191 | 0.700/0.173/0.127 | 0.152 | home | market |
| ESP-La Liga | 2026-10-17 | Espanyol | Atlético Madrid | False | 0.306/0.276/0.417 | 0.192/0.239/0.569 | 0.152 | away | market |
| ENG-Premier League | 2026-10-31 | Tottenham | Crystal Palace | False | 0.427/0.276/0.297 | 0.579/0.229/0.192 | 0.152 | home | market |
| GER-Bundesliga | 2026-09-06 | Frankfurt | Augsburg | True | 0.363/0.327/0.310 | 0.515/0.230/0.255 | 0.152 | away | model |
| FRA-Ligue 1 | 2026-08-28 | Lille | PSG | True | 0.294/0.312/0.394 | 0.211/0.245/0.544 | 0.150 | draw | model |
| ESP-La Liga | 2026-09-19 | Athletic Club | Alavés | False | 0.440/0.283/0.277 | 0.590/0.248/0.162 | 0.149 | draw | model |
| FRA-Ligue 1 | 2026-09-06 | Angers | Rennes | True | 0.279/0.317/0.404 | 0.213/0.235/0.552 | 0.148 | away | market |
| ESP-La Liga | 2026-09-19 | Celta Vigo | Racing Sant | False | 0.377/0.311/0.312 | 0.525/0.250/0.224 | 0.148 | home | market |
| FRA-Ligue 1 | 2026-10-10 | Monaco | Toulouse | False | 0.436/0.267/0.298 | 0.582/0.226/0.192 | 0.146 | draw | model |
| ENG-Premier League | 2026-10-10 | Chelsea | Bournemouth | False | 0.376/0.310/0.313 | 0.523/0.239/0.238 | 0.146 | home | market |
| ESP-La Liga | 2026-11-08 | Elche | Real Betis | False | 0.310/0.306/0.384 | 0.238/0.232/0.530 | 0.146 | away | market |
| ENG-Premier League | 2026-10-19 | Tottenham | Coventry City | False | 0.470/0.296/0.234 | 0.616/0.211/0.173 | 0.146 | home | market |
| ENG-Premier League | 2026-08-21 | Arsenal | Coventry City | True | 0.645/0.222/0.133 | 0.791/0.141/0.068 | 0.146 | home | market |
| ESP-La Liga | 2026-08-17 | Dep. A Coruña | Elche | True | 0.577/0.228/0.195 | 0.432/0.300/0.268 | 0.145 | draw | market |
| FRA-Ligue 1 | 2026-08-22 | Le Mans | Brest | True | 0.519/0.244/0.236 | 0.376/0.283/0.341 | 0.143 | draw | market |
| FRA-Ligue 1 | 2026-10-10 | Lorient | Paris FC | False | 0.361/0.327/0.312 | 0.256/0.291/0.453 | 0.141 | home | model |
| ESP-La Liga | 2026-09-17 | Málaga | Villarreal | False | 0.347/0.337/0.316 | 0.278/0.266/0.457 | 0.141 | away | market |
| ESP-La Liga | 2026-09-05 | Villarreal | Dep. A Coruña | True | 0.516/0.265/0.219 | 0.656/0.202/0.141 | 0.140 | away | model |
| ESP-La Liga | 2026-09-15 | Elche | Real Madrid | False | 0.159/0.190/0.651 | 0.078/0.130/0.791 | 0.140 | away | market |
| ENG-Premier League | 2026-08-29 | Coventry City | Hull City | True | 0.411/0.268/0.321 | 0.551/0.248/0.201 | 0.140 | away | model |
| GER-Bundesliga | 2026-09-19 | Werder Bremen | Augsburg | False | 0.283/0.321/0.397 | 0.422/0.251/0.327 | 0.139 | home | market |
| GER-Bundesliga | 2026-09-12 | Freiburg | Gladbach | False | 0.421/0.311/0.267 | 0.561/0.225/0.214 | 0.139 | home | market |
| GER-Bundesliga | 2026-11-08 | Freiburg | Union Berlin | False | 0.512/0.240/0.248 | 0.651/0.207/0.142 | 0.139 | home | market |
| GER-Bundesliga | 2026-10-31 | Werder Bremen | Hoffenheim | False | 0.264/0.298/0.438 | 0.402/0.245/0.353 | 0.138 | home | market |
| ESP-La Liga | 2026-08-16 | Racing Sant | Villarreal | True | 0.392/0.254/0.354 | 0.256/0.251/0.493 | 0.138 | draw | model |
| FRA-Ligue 1 | 2026-10-17 | Strasbourg | PSG | False | 0.234/0.252/0.514 | 0.161/0.187/0.652 | 0.138 | away | market |
| ENG-Premier League | 2026-08-23 | Newcastle | Liverpool | True | 0.320/0.325/0.355 | 0.259/0.248/0.493 | 0.138 | draw | model |
| ESP-La Liga | 2026-09-16 | Barcelona | Racing Sant | False | 0.761/0.139/0.100 | 0.898/0.067/0.035 | 0.137 | home | market |
| ITA-Serie A | 2026-08-22 | Inter | Monza | True | 0.687/0.189/0.124 | 0.824/0.121/0.055 | 0.136 | home | market |
| ESP-La Liga | 2026-09-12 | Real Madrid | Rayo Vallecano | False | 0.695/0.186/0.120 | 0.830/0.110/0.060 | 0.135 | home | market |
| ESP-La Liga | 2026-08-31 | Barcelona | Rayo Vallecano | True | 0.727/0.172/0.101 | 0.862/0.091/0.048 | 0.135 | home | market |
| ITA-Serie A | 2026-10-11 | Lazio | Monza | False | 0.426/0.250/0.324 | 0.560/0.246/0.194 | 0.135 | home | market |
| FRA-Ligue 1 | 2026-10-10 | PSG | Le Mans | False | 0.681/0.223/0.096 | 0.815/0.116/0.069 | 0.134 | home | market |
| ENG-Premier League | 2026-10-17 | Fulham | Hull City | False | 0.445/0.291/0.264 | 0.579/0.234/0.187 | 0.134 | home | market |
| FRA-Ligue 1 | 2026-10-18 | Lorient | Monaco | False | 0.343/0.320/0.336 | 0.259/0.273/0.468 | 0.132 | home | model |
| FRA-Ligue 1 | 2026-10-25 | Monaco | Lille | False | 0.366/0.304/0.329 | 0.497/0.265/0.237 | 0.131 | draw | model |
| ITA-Serie A | 2026-11-08 | Monza | Atalanta | False | 0.327/0.306/0.366 | 0.257/0.247/0.497 | 0.131 | away | market |
| ESP-La Liga | 2026-10-11 | Real Betis | Osasuna | False | 0.518/0.262/0.220 | 0.648/0.203/0.148 | 0.130 | home | market |
| ENG-Premier League | 2026-11-07 | Nottingham | Manchester City | False | 0.273/0.275/0.452 | 0.188/0.230/0.582 | 0.130 | home | model |
| ITA-Serie A | 2026-09-06 | Parma | Monza | True | 0.241/0.292/0.467 | 0.334/0.329/0.337 | 0.130 | draw | market |
| FRA-Ligue 1 | 2026-10-11 | Rennes | Auxerre | False | 0.535/0.241/0.224 | 0.665/0.193/0.142 | 0.129 | home | market |
| ITA-Serie A | 2026-10-11 | Sassuolo | Milan | False | 0.311/0.319/0.370 | 0.245/0.256/0.499 | 0.129 | draw | model |
| ESP-La Liga | 2026-09-13 | Real Sociedad | Atlético Madrid | False | 0.368/0.309/0.323 | 0.283/0.265/0.452 | 0.129 | away | market |
| ENG-Premier League | 2026-10-31 | Hull City | Ipswich Town | False | 0.420/0.311/0.270 | 0.325/0.277/0.398 | 0.129 | draw | model |
| GER-Bundesliga | 2026-08-29 | Elversberg | Leverkusen | True | 0.281/0.251/0.468 | 0.188/0.216/0.596 | 0.128 | home | model |
| FRA-Ligue 1 | 2026-09-13 | Le Mans | Lens | False | 0.264/0.279/0.457 | 0.196/0.219/0.585 | 0.128 | draw | model |
| FRA-Ligue 1 | 2026-09-12 | Strasbourg | Monaco | False | 0.422/0.277/0.301 | 0.313/0.258/0.429 | 0.128 | draw | model |
| FRA-Ligue 1 | 2026-09-04 | Lyon | Auxerre | True | 0.549/0.266/0.185 | 0.677/0.187/0.136 | 0.127 | home | market |
| GER-Bundesliga | 2026-09-20 | Leverkusen | RB Leipzig | False | 0.385/0.299/0.316 | 0.512/0.216/0.272 | 0.127 | home | market |
| GER-Bundesliga | 2026-09-11 | Union Berlin | Schalke 04 | False | 0.281/0.370/0.350 | 0.407/0.277/0.316 | 0.127 | away | model |
| GER-Bundesliga | 2026-10-17 | Bayern Munich | RB Leipzig | False | 0.639/0.162/0.199 | 0.766/0.130/0.104 | 0.127 | home | market |
| ESP-La Liga | 2026-08-26 | Real Madrid | Real Sociedad | True | 0.674/0.201/0.125 | 0.799/0.128/0.073 | 0.125 | home | market |
| ESP-La Liga | 2026-10-31 | Barcelona | Alavés | False | 0.738/0.161/0.101 | 0.863/0.087/0.050 | 0.125 | home | market |
| ENG-Premier League | 2026-11-07 | Arsenal | Hull City | False | 0.703/0.206/0.091 | 0.829/0.118/0.053 | 0.125 | home | market |
| ITA-Serie A | 2026-10-27 | Sassuolo | Lazio | False | 0.337/0.308/0.355 | 0.260/0.260/0.480 | 0.125 | away | market |
| ENG-Premier League | 2026-09-20 | Leeds United | Crystal Palace | False | 0.444/0.286/0.269 | 0.569/0.239/0.192 | 0.125 | draw | model |
| ENG-Premier League | 2026-10-25 | Liverpool | Brighton | False | 0.356/0.306/0.338 | 0.480/0.247/0.273 | 0.125 | home | market |
| ITA-Serie A | 2026-08-29 | Monza | Udinese | True | 0.450/0.289/0.261 | 0.326/0.308/0.366 | 0.124 | away | market |
| ENG-Premier League | 2026-09-05 | Fulham | Crystal Palace | True | 0.314/0.336/0.350 | 0.438/0.279/0.283 | 0.124 | away | model |
| ITA-Serie A | 2026-09-13 | Lecce | Monza | False | 0.244/0.282/0.474 | 0.334/0.316/0.350 | 0.124 | home | market |
| FRA-Ligue 1 | 2026-10-24 | Lens | Paris FC | False | 0.532/0.265/0.203 | 0.408/0.266/0.326 | 0.124 | home | model |
| ENG-Premier League | 2026-08-23 | Manchester City | Bournemouth | True | 0.531/0.263/0.205 | 0.655/0.197/0.148 | 0.123 | home | market |
| ENG-Premier League | 2026-08-29 | Tottenham | Newcastle | True | 0.314/0.325/0.361 | 0.437/0.256/0.307 | 0.123 | away | model |
| ENG-Premier League | 2026-10-18 | Nottingham | Arsenal | False | 0.224/0.267/0.508 | 0.143/0.226/0.631 | 0.123 | away | market |
| ESP-La Liga | 2026-08-28 | Alavés | Villarreal | True | 0.389/0.317/0.294 | 0.310/0.273/0.416 | 0.122 | home | model |
| ESP-La Liga | 2026-08-27 | Celta Vigo | Osasuna | True | 0.387/0.328/0.285 | 0.510/0.287/0.204 | 0.122 | away | model |
| ENG-Premier League | 2026-09-05 | Newcastle | Bournemouth | True | 0.325/0.333/0.342 | 0.446/0.260/0.294 | 0.121 | draw | model |
| ENG-Premier League | 2026-09-20 | Bournemouth | Liverpool | False | 0.373/0.308/0.319 | 0.303/0.258/0.439 | 0.120 | away | market |
| FRA-Ligue 1 | 2026-09-19 | Paris FC | Strasbourg | False | 0.407/0.302/0.291 | 0.526/0.243/0.231 | 0.119 | home | market |
| FRA-Ligue 1 | 2026-09-19 | Le Mans | Lorient | False | 0.446/0.296/0.259 | 0.328/0.295/0.377 | 0.119 | home | model |
| ESP-La Liga | 2026-08-27 | Barcelona | Athletic Club | True | 0.654/0.205/0.141 | 0.771/0.142/0.087 | 0.118 | home | market |
| FRA-Ligue 1 | 2026-09-12 | Auxerre | Nice | False | 0.427/0.303/0.270 | 0.330/0.283/0.387 | 0.117 | home | model |
| ENG-Premier League | 2026-11-06 | Everton | Coventry City | False | 0.452/0.301/0.247 | 0.569/0.236/0.196 | 0.117 | home | market |
| ESP-La Liga | 2026-08-23 | Getafe | Racing Sant | True | 0.299/0.339/0.362 | 0.416/0.308/0.276 | 0.117 | home | market |
| ESP-La Liga | 2026-10-18 | Real Madrid | Sevilla | False | 0.652/0.220/0.128 | 0.768/0.142/0.090 | 0.116 | home | market |
| FRA-Ligue 1 | 2026-09-13 | Lille | Troyes | False | 0.522/0.261/0.217 | 0.637/0.206/0.157 | 0.115 | home | market |
| ITA-Serie A | 2026-10-29 | Frosinone | Lecce | False | 0.433/0.267/0.300 | 0.549/0.226/0.225 | 0.115 | home | market |
| FRA-Ligue 1 | 2026-08-29 | Lorient | Troyes | True | 0.373/0.366/0.262 | 0.488/0.283/0.230 | 0.115 | away | model |
| GER-Bundesliga | 2026-10-10 | Paderborn 07 | Stuttgart | False | 0.214/0.319/0.467 | 0.207/0.212/0.582 | 0.115 | away | market |
| ITA-Serie A | 2026-09-11 | Venezia | Fiorentina | False | 0.432/0.296/0.271 | 0.335/0.279/0.386 | 0.115 | away | market |
| ENG-Premier League | 2026-08-30 | Chelsea | Brighton | True | 0.399/0.308/0.293 | 0.513/0.245/0.241 | 0.114 | home | market |
| ITA-Serie A | 2026-08-23 | Frosinone | Juventus | True | 0.208/0.248/0.544 | 0.141/0.201/0.658 | 0.114 | away | market |
| ESP-La Liga | 2026-09-12 | Osasuna | Espanyol | False | 0.540/0.260/0.200 | 0.427/0.295/0.279 | 0.114 | away | market |
| GER-Bundesliga | 2026-10-17 | Schalke 04 | Mainz 05 | False | 0.223/0.287/0.489 | 0.337/0.268/0.395 | 0.114 | away | model |
| ITA-Serie A | 2026-10-19 | Monza | Cagliari | False | 0.484/0.284/0.232 | 0.371/0.299/0.330 | 0.113 | home | model |
| GER-Bundesliga | 2026-09-12 | Mainz 05 | Frankfurt | False | 0.425/0.303/0.272 | 0.538/0.232/0.230 | 0.113 | away | model |
| GER-Bundesliga | 2026-09-19 | Stuttgart | Dortmund | False | 0.292/0.300/0.409 | 0.404/0.243/0.353 | 0.113 | away | model |
| ITA-Serie A | 2026-09-18 | Monza | Sassuolo | False | 0.447/0.284/0.269 | 0.337/0.281/0.382 | 0.113 | home | model |
| ESP-La Liga | 2026-08-15 | Sevilla | Rayo Vallecano | True | 0.278/0.313/0.409 | 0.380/0.324/0.296 | 0.112 | home | market |
| FRA-Ligue 1 | 2026-09-03 | Toulouse | Lille | True | 0.309/0.334/0.357 | 0.254/0.277/0.469 | 0.112 | away | market |
| ITA-Serie A | 2026-09-06 | Juventus | Milan | True | 0.542/0.270/0.188 | 0.430/0.305/0.265 | 0.112 | draw | market |
| ITA-Serie A | 2026-11-07 | Cagliari | Frosinone | False | 0.375/0.288/0.337 | 0.306/0.247/0.447 | 0.110 | home | model |
| ESP-La Liga | 2026-10-26 | Sevilla | Osasuna | False | 0.381/0.303/0.316 | 0.490/0.281/0.229 | 0.110 | home | market |
| ESP-La Liga | 2026-08-15 | Alavés | Getafe | True | 0.516/0.289/0.195 | 0.407/0.342/0.252 | 0.109 | home | model |
| ITA-Serie A | 2026-11-01 | Frosinone | Torino | False | 0.346/0.299/0.355 | 0.455/0.240/0.305 | 0.109 | home | market |
| GER-Bundesliga | 2026-09-05 | Hoffenheim | Dortmund | True | 0.280/0.297/0.423 | 0.388/0.248/0.364 | 0.108 | away | model |
| ITA-Serie A | 2026-09-20 | Milan | Lecce | False | 0.662/0.215/0.122 | 0.771/0.154/0.075 | 0.108 | home | market |
| ESP-La Liga | 2026-08-19 | Atlético Madrid | Málaga | True | 0.538/0.232/0.230 | 0.646/0.209/0.144 | 0.108 | home | market |
| ENG-Premier League | 2026-10-24 | Aston Villa | Manchester City | False | 0.274/0.254/0.473 | 0.210/0.209/0.581 | 0.108 | home | model |
| FRA-Ligue 1 | 2026-10-11 | Nice | Strasbourg | False | 0.342/0.322/0.337 | 0.449/0.256/0.296 | 0.107 | home | market |
| FRA-Ligue 1 | 2026-10-25 | PSG | Lyon | False | 0.607/0.228/0.165 | 0.714/0.168/0.118 | 0.107 | home | market |
| ESP-La Liga | 2026-08-31 | Osasuna | Getafe | True | 0.545/0.284/0.172 | 0.438/0.331/0.231 | 0.106 | home | model |
| GER-Bundesliga | 2026-10-16 | Frankfurt | Köln | False | 0.434/0.264/0.303 | 0.540/0.220/0.240 | 0.106 | home | market |
| FRA-Ligue 1 | 2026-10-17 | Troyes | Lens | False | 0.156/0.209/0.634 | 0.225/0.246/0.529 | 0.105 | away | model |
| FRA-Ligue 1 | 2026-11-08 | Lens | Marseille | False | 0.534/0.242/0.223 | 0.429/0.259/0.312 | 0.105 | away | market |
| GER-Bundesliga | 2026-10-17 | Hamburger SV | Stuttgart | False | 0.251/0.296/0.453 | 0.221/0.220/0.558 | 0.105 | home | model |
| GER-Bundesliga | 2026-09-06 | Hamburger SV | Mainz 05 | True | 0.228/0.295/0.477 | 0.333/0.272/0.395 | 0.105 | away | model |
| FRA-Ligue 1 | 2026-09-06 | Troyes | Strasbourg | True | 0.389/0.331/0.279 | 0.341/0.275/0.384 | 0.105 | away | market |
| FRA-Ligue 1 | 2026-10-18 | Lyon | Nice | False | 0.580/0.248/0.172 | 0.476/0.255/0.269 | 0.104 | home | model |
| GER-Bundesliga | 2026-11-01 | Frankfurt | Hamburger SV | False | 0.529/0.245/0.226 | 0.632/0.196/0.171 | 0.103 | home | market |
| ENG-Premier League | 2026-08-22 | Nottingham | Leeds United | True | 0.282/0.325/0.393 | 0.385/0.295/0.321 | 0.103 | away | model |
| ESP-La Liga | 2026-09-15 | Rayo Vallecano | Espanyol | False | 0.525/0.269/0.206 | 0.423/0.291/0.286 | 0.103 | home | model |
| ENG-Premier League | 2026-10-12 | Coventry City | Newcastle | False | 0.314/0.309/0.377 | 0.267/0.254/0.479 | 0.102 | home | model |
| ITA-Serie A | 2026-08-30 | Napoli | Como | True | 0.309/0.333/0.358 | 0.412/0.308/0.280 | 0.102 | away | model |
| FRA-Ligue 1 | 2026-09-12 | Le Havre | Angers | False | 0.446/0.304/0.250 | 0.366/0.281/0.353 | 0.102 | draw | model |
| GER-Bundesliga | 2026-10-24 | Köln | Schalke 04 | False | 0.535/0.258/0.207 | 0.435/0.262/0.303 | 0.100 | draw | market |
| ENG-Premier League | 2026-08-28 | Crystal Palace | Manchester City | True | 0.234/0.283/0.482 | 0.190/0.228/0.582 | 0.100 | away | market |
| GER-Bundesliga | 2026-10-17 | Werder Bremen | Paderborn 07 | False | 0.462/0.302/0.236 | 0.561/0.225/0.215 | 0.099 | draw | model |
| ESP-La Liga | 2026-09-19 | Osasuna | Rayo Vallecano | False | 0.455/0.285/0.260 | 0.357/0.295/0.348 | 0.098 | draw | market |
| ENG-Premier League | 2026-10-31 | Aston Villa | Fulham | False | 0.385/0.303/0.312 | 0.483/0.256/0.261 | 0.098 | draw | model |
| ITA-Serie A | 2026-11-02 | Sassuolo | Fiorentina | False | 0.363/0.311/0.326 | 0.316/0.261/0.423 | 0.097 | away | market |
| GER-Bundesliga | 2026-10-24 | Augsburg | Union Berlin | False | 0.457/0.269/0.274 | 0.554/0.227/0.219 | 0.097 | draw | model |
| ESP-La Liga | 2026-09-20 | Dep. A Coruña | Real Betis | False | 0.299/0.310/0.392 | 0.253/0.258/0.488 | 0.097 | draw | model |
| ESP-La Liga | 2026-09-20 | Valencia | Real Sociedad | False | 0.420/0.289/0.291 | 0.329/0.283/0.388 | 0.096 | away | market |
| FRA-Ligue 1 | 2026-11-01 | Marseille | Toulouse | False | 0.405/0.308/0.287 | 0.500/0.242/0.257 | 0.096 | home | market |
| ITA-Serie A | 2026-11-08 | Fiorentina | Juventus | False | 0.202/0.273/0.526 | 0.293/0.277/0.430 | 0.095 | draw | market |
| ITA-Serie A | 2026-09-05 | Fiorentina | Torino | True | 0.369/0.330/0.302 | 0.463/0.283/0.253 | 0.094 | away | model |
| GER-Bundesliga | 2026-09-19 | Hamburger SV | Köln | False | 0.260/0.310/0.430 | 0.354/0.261/0.385 | 0.094 | home | market |
| FRA-Ligue 1 | 2026-10-23 | Brest | Nice | False | 0.494/0.272/0.234 | 0.401/0.274/0.326 | 0.094 | away | market |
| ENG-Premier League | 2026-08-22 | Everton | Crystal Palace | True | 0.314/0.348/0.338 | 0.408/0.282/0.310 | 0.094 | home | market |
| ITA-Serie A | 2026-10-17 | Roma | Genoa | False | 0.686/0.186/0.128 | 0.593/0.244/0.164 | 0.093 | home | model |
| ESP-La Liga | 2026-11-06 | Sevilla | Alavés | False | 0.391/0.303/0.305 | 0.483/0.289/0.228 | 0.092 | draw | model |
| ESP-La Liga | 2026-10-31 | Real Betis | Málaga | False | 0.631/0.241/0.129 | 0.722/0.172/0.106 | 0.092 | home | market |
| ENG-Premier League | 2026-11-07 | Leeds United | Tottenham | False | 0.402/0.314/0.284 | 0.342/0.282/0.376 | 0.092 | home | model |
| ESP-La Liga | 2026-10-11 | Real Sociedad | Dep. A Coruña | False | 0.449/0.308/0.243 | 0.540/0.247/0.213 | 0.092 | home | market |
| ITA-Serie A | 2026-11-01 | Lecce | Genoa | False | 0.381/0.312/0.308 | 0.290/0.318/0.392 | 0.091 | away | market |
| FRA-Ligue 1 | 2026-08-29 | Lyon | Le Havre | True | 0.578/0.258/0.164 | 0.669/0.201/0.131 | 0.091 | draw | model |
| ITA-Serie A | 2026-09-13 | Napoli | Bologna | False | 0.435/0.297/0.268 | 0.525/0.263/0.211 | 0.091 | home | market |
| ENG-Premier League | 2026-08-30 | Sunderland | Fulham | True | 0.335/0.344/0.321 | 0.425/0.287/0.288 | 0.090 | home | market |
| FRA-Ligue 1 | 2026-11-07 | PSG | Troyes | False | 0.756/0.160/0.084 | 0.846/0.102/0.053 | 0.089 | home | market |
| ENG-Premier League | 2026-09-12 | Tottenham | Everton | False | 0.388/0.305/0.307 | 0.477/0.260/0.263 | 0.089 | draw | model |
| ENG-Premier League | 2026-10-11 | Hull City | Everton | False | 0.324/0.280/0.396 | 0.235/0.281/0.484 | 0.089 | draw | market |
| GER-Bundesliga | 2026-08-30 | Augsburg | Schalke 04 | True | 0.327/0.268/0.405 | 0.414/0.269/0.317 | 0.089 | home | market |
| ITA-Serie A | 2026-11-02 | Atalanta | Parma | False | 0.595/0.246/0.159 | 0.684/0.188/0.129 | 0.089 | away | model |
| GER-Bundesliga | 2026-10-17 | Union Berlin | Dortmund | False | 0.215/0.240/0.545 | 0.161/0.207/0.632 | 0.087 | draw | model |
| FRA-Ligue 1 | 2026-11-06 | Toulouse | Strasbourg | False | 0.519/0.256/0.225 | 0.433/0.262/0.305 | 0.087 | home | model |
| ENG-Premier League | 2026-10-11 | Crystal Palace | Nottingham | False | 0.375/0.332/0.294 | 0.339/0.281/0.380 | 0.086 | home | model |
| GER-Bundesliga | 2026-10-31 | Bayern Munich | Dortmund | False | 0.621/0.183/0.196 | 0.707/0.162/0.131 | 0.086 | draw | model |
| GER-Bundesliga | 2026-10-25 | Freiburg | Bayern Munich | False | 0.190/0.227/0.583 | 0.156/0.175/0.668 | 0.086 | away | market |
| FRA-Ligue 1 | 2026-10-25 | Toulouse | Troyes | False | 0.685/0.185/0.129 | 0.600/0.223/0.178 | 0.085 | draw | market |
| GER-Bundesliga | 2026-11-07 | Paderborn 07 | Frankfurt | False | 0.289/0.337/0.374 | 0.315/0.252/0.433 | 0.085 | draw | model |
| ENG-Premier League | 2026-10-31 | Coventry City | Sunderland | False | 0.358/0.325/0.317 | 0.319/0.280/0.401 | 0.084 | home | model |
| ENG-Premier League | 2026-10-24 | Coventry City | Fulham | False | 0.297/0.337/0.366 | 0.287/0.263/0.450 | 0.084 | away | market |
| ESP-La Liga | 2026-08-29 | Levante | Real Betis | True | 0.324/0.345/0.331 | 0.304/0.282/0.415 | 0.083 | home | model |
| ESP-La Liga | 2026-11-08 | Real Sociedad | Rayo Vallecano | False | 0.429/0.279/0.292 | 0.512/0.244/0.244 | 0.083 | home | market |
| ENG-Premier League | 2026-09-05 | Brighton | Leeds United | True | 0.404/0.312/0.284 | 0.487/0.260/0.253 | 0.083 | draw | model |
| GER-Bundesliga | 2026-08-29 | Union Berlin | Frankfurt | True | 0.331/0.342/0.328 | 0.361/0.258/0.380 | 0.083 | draw | model |
| GER-Bundesliga | 2026-08-30 | Freiburg | Werder Bremen | True | 0.449/0.304/0.247 | 0.532/0.248/0.220 | 0.083 | home | market |
| FRA-Ligue 1 | 2026-09-20 | Auxerre | Brest | False | 0.346/0.330/0.325 | 0.325/0.268/0.407 | 0.083 | home | model |
| FRA-Ligue 1 | 2026-10-11 | Troyes | Marseille | False | 0.224/0.231/0.546 | 0.271/0.266/0.463 | 0.083 | away | model |
| ENG-Premier League | 2026-10-31 | Brentford | Nottingham | False | 0.367/0.312/0.321 | 0.449/0.261/0.289 | 0.082 | home | market |
| GER-Bundesliga | 2026-09-20 | Paderborn 07 | Hoffenheim | False | 0.163/0.248/0.589 | 0.246/0.222/0.533 | 0.082 | home | market |
| ITA-Serie A | 2026-10-28 | Monza | Napoli | False | 0.237/0.240/0.523 | 0.176/0.219/0.605 | 0.082 | away | market |
| FRA-Ligue 1 | 2026-09-19 | Lyon | Rennes | False | 0.532/0.243/0.225 | 0.451/0.251/0.298 | 0.081 | home | model |
| GER-Bundesliga | 2026-09-05 | Werder Bremen | RB Leipzig | True | 0.170/0.250/0.579 | 0.251/0.231/0.518 | 0.081 | home | market |
| ITA-Serie A | 2026-09-12 | Genoa | Frosinone | False | 0.336/0.288/0.376 | 0.417/0.283/0.301 | 0.080 | draw | model |
| ENG-Premier League | 2026-09-12 | Sunderland | Arsenal | False | 0.121/0.214/0.665 | 0.161/0.255/0.585 | 0.080 | away | model |
| ITA-Serie A | 2026-10-18 | Fiorentina | Como | False | 0.237/0.259/0.504 | 0.310/0.266/0.424 | 0.080 | away | model |

### Model minus market, histogram

| bin from | home | draw | away |
|---|---|---|---|
| -0.30 | 5 | 0 | 2 |
| -0.25 | 9 | 0 | 5 |
| -0.20 | 17 | 0 | 26 |
| -0.15 | 61 | 0 | 40 |
| -0.10 | 79 | 3 | 81 |
| -0.05 | 114 | 85 | 102 |
| +0.00 | 96 | 266 | 139 |
| +0.05 | 77 | 132 | 78 |
| +0.10 | 32 | 13 | 17 |
| +0.15 | 7 | 0 | 8 |
| +0.20 | 2 | 0 | 1 |
| +0.25 | 0 | 0 | 0 |

## Historical benchmark (walk-forward, frozen seasons)

Leagues: ENG-Premier League, ESP-La Liga, GER-Bundesliga, ITA-Serie A. Rows 11,311, joined 11,309 (99.98%).

Unjoined:

| season | league | date | home | away |
|---|---|---|---|---|
| 1819 | GER-Bundesliga | 2019-05-04 | Bayern Munich | Hannover 96 |
| 2324 | ITA-Serie A | 2024-04-14 | Udinese | Roma |

| season | n | blend LL | layer LL | market LL | blend gap | layer gap |
|---|---|---|---|---|---|---|
| 1819 | 1412 | 0.9748 | 0.9763 | 0.9502 | 0.0245 | 0.0260 |
| 1920 | 1411 | 0.9888 | 0.9902 | 0.9688 | 0.0199 | 0.0214 |
| 2021 | 1415 | 0.9907 | 0.9920 | 0.9727 | 0.0179 | 0.0192 |
| 2122 | 1415 | 0.9868 | 0.9872 | 0.9715 | 0.0153 | 0.0157 |
| 2223 | 1413 | 0.9881 | 0.9880 | 0.9769 | 0.0111 | 0.0111 |
| 2324 | 1412 | 0.9701 | 0.9703 | 0.9423 | 0.0277 | 0.0280 |
| 2425 | 1415 | 0.9810 | 0.9812 | 0.9635 | 0.0175 | 0.0177 |
| 2526 | 1416 | 0.9953 | 0.9952 | 0.9781 | 0.0172 | 0.0171 |
| pooled | 11309 | 0.9844 | 0.9851 | 0.9655 | 0.0189 | 0.0195 |

## Information test

The model does not add information beyond the market: its weight is 0.09 with a 95% CI of -0.05 to 0.21, which includes zero.

Arm blend, n=11,309, weight_model 0.0909 (95% CI -0.0456 to 0.2128, 500 resamples), weight_market 1.0193.

| season | n | market-only LL | stacked LL | gain |
|---|---|---|---|---|
| 1819 | 1412 | 0.9504 | 0.9504 | 0.0000 |
| 1920 | 1411 | 0.9697 | 0.9696 | 0.0001 |
| 2021 | 1415 | 0.9724 | 0.9721 | 0.0003 |
| 2122 | 1415 | 0.9715 | 0.9712 | 0.0003 |
| 2223 | 1413 | 0.9793 | 0.9794 | -0.0001 |
| 2324 | 1412 | 0.9401 | 0.9405 | -0.0004 |
| 2425 | 1415 | 0.9624 | 0.9621 | 0.0003 |
| 2526 | 1416 | 0.9773 | 0.9773 | 0.0000 |
| pooled | 11309 | 0.9654 | 0.9653 | 0.0001 |


Probabilities and fair prices only — never betting advice.
