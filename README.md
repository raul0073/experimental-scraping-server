
```
soccer-stats-ai
├─ core
│  └─ db.py
├─ Dockerfile
├─ main.py
├─ models
│  ├─ labels
│  │  └─ labels.py
│  ├─ players.py
│  ├─ plotting
│  │  └─ plot.py
│  ├─ stats_aware
│  │  └─ stats_aware.py
│  ├─ stats_type.py
│  ├─ team.py
│  ├─ users
│  │  └─ user.py
│  └─ zones
│     └─ zones_config.py
├─ requirements.txt
├─ routes
│  ├─ admin.py
│  ├─ AI.py
│  ├─ fbref_route.py
│  ├─ ping.py
│  ├─ plot.py
│  ├─ predictions.py
│  ├─ team.py
│  └─ user.py
├─ services
│  ├─ ai
│  │  └─ ai_service.py
│  ├─ db
│  │  ├─ db_service.py
│  │  └─ user_config_service.py
│  ├─ fbref
│  │  ├─ fbref_data_service.py
│  │  └─ fixtures.py
│  ├─ plotting
│  │  └─ plot_service.py
│  ├─ predictions
│  │  └─ predictions_service.py
│  ├─ rating
│  │  ├─ analysis_service.py
│  │  ├─ benchmarks_service.py
│  │  ├─ bestXI_service.py
│  │  ├─ optimizer.py
│  │  └─ zones_service.py
│  ├─ team_init_service.py
│  └─ utils.py
└─ utils
   ├─ df_utils.py
   ├─ errors.py
   ├─ fonts
   │  └─ RobotoSlab[wght].ttf
   ├─ player_utils.py
   ├─ ranking_utils.py
   ├─ rating_utils.py
   ├─ serialization_utils.py
   └─ stats_utils.py

```