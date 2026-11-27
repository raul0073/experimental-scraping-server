# Which strategy makes sense for this model

11309 fixtures, 292 weeks, 1819..2526, walk-forward. Bankroll 1000, 34-week seasons bootstrapped 4000 times from all weeks. Ranked by expected log growth (positive expectation rewarded, variance and ruin punished).

Winner-like regime is an ASSUMPTION from eight prices seen on 2026-11-27: {'draw_mult': 1.03, 'fav_mult': 0.87, 'dog_mult': 0.92, 'fav_from': 0.5}.

## winner-like prices, 60/week

| strategy | ROI | weeks bet | week in profit | median end | 10th pct | 90th pct | season up | bust |
|---|---|---|---|---|---|---|---|---|
| draws top4 >=0.30 · system 2/4 | +33.0% | 171 | 25% | 1341 | 687 | 2183 | 74% | 0.0% |
| draws top5 >=0.30 · system 2/5 | +28.6% | 136 | 23% | 1242 | 789 | 1798 | 74% | 0.0% |
| draws top3 >=0.30 · system 2/3 | +36.3% | 203 | 18% | 1455 | 545 | 2538 | 73% | 1.7% |
| draws top3 >=0.30 · singles | +15.3% | 203 | 47% | 1211 | 872 | 1572 | 78% | 0.0% |
| draws top4 >=0.30 · singles | +13.3% | 171 | 26% | 1153 | 882 | 1452 | 77% | 0.0% |
| draws top3 >=0.31 · system 2/3 | +34.7% | 121 | 10% | 1212 | 544 | 2162 | 64% | 0.1% |
| draws top5 >=0.30 · singles | +12.2% | 136 | 26% | 1120 | 896 | 1340 | 75% | 0.0% |
| draws top3 >=0.31 · singles | +14.7% | 121 | 28% | 1109 | 854 | 1394 | 71% | 0.0% |
| draws top3 · singles | +6.6% | 292 | 65% | 1134 | 737 | 1541 | 67% | 0.0% |
| draws top6 >=0.30 · system 2/6 | +13.3% | 106 | 12% | 1072 | 746 | 1474 | 60% | 0.0% |
| draws top5 >=0.30 · system 3/5 | +32.4% | 136 | 11% | 1124 | 430 | 2338 | 57% | 0.4% |
| draws top6 >=0.30 · singles | +4.7% | 106 | 22% | 1031 | 855 | 1211 | 59% | 0.0% |

worst five by the same measure:

- draws top6 · system 4/6: ROI -49.9%, median end 0, bust 66.3%
- strong top5 >=0.55 · 5-fold: ROI -53.0%, median end 0, bust 60.9%
- draws top5 · 5-fold: ROI -100.0%, median end 0, bust 100.0%
- draws top6 · system 5/6: ROI -100.0%, median end 0, bust 100.0%
- draws top6 · 6-fold: ROI -100.0%, median end 0, bust 100.0%

## winner-like prices, 10/line

| strategy | ROI | weeks bet | week in profit | median end | 10th pct | 90th pct | season up | bust |
|---|---|---|---|---|---|---|---|---|
| draws top4 >=0.30 · system 2/4 | +33.0% | 171 | 25% | 1354 | 698 | 2179 | 74% | 0.1% |
| draws top5 >=0.30 · system 2/5 | +28.6% | 136 | 23% | 1403 | 653 | 2357 | 74% | 0.6% |
| draws top3 >=0.30 · system 2/3 | +36.3% | 203 | 18% | 1216 | 763 | 1782 | 72% | 0.0% |
| draws top3 >=0.30 · 3-fold | +84.3% | 203 | 3% | 1139 | 750 | 1776 | 69% | 0.0% |
| draws top3 >=0.31 · 3-fold | +116.1% | 121 | 2% | 1195 | 840 | 1630 | 57% | 0.0% |
| draws top3 >=0.31 · system 2/3 | +34.7% | 121 | 10% | 1112 | 780 | 1584 | 65% | 0.0% |
| draws top4 >=0.30 · system 3/4 | +58.6% | 171 | 7% | 1160 | 400 | 2822 | 58% | 0.1% |
| draws top4 >=0.30 · 4-fold | +124.0% | 171 | 1% | 820 | 770 | 2111 | 30% | 0.0% |
| draws top3 >=0.30 · singles | +15.3% | 203 | 47% | 1103 | 932 | 1283 | 77% | 0.0% |
| draws top4 >=0.30 · singles | +13.3% | 171 | 26% | 1098 | 913 | 1292 | 74% | 0.0% |
| draws top5 >=0.30 · singles | +12.2% | 136 | 26% | 1091 | 904 | 1281 | 73% | 0.0% |
| draws top3 · 3-fold | +43.6% | 292 | 4% | 1056 | 660 | 1757 | 65% | 0.0% |

worst five by the same measure:

- draws top6 · system 3/6: ROI -11.8%, median end 0, bust 75.5%
- strong top5 >=0.60 · system 3/5: ROI -37.6%, median end 0, bust 66.7%
- strong top5 >=0.55 · system 3/5: ROI -35.8%, median end 0, bust 73.4%
- draws top6 · system 4/6: ROI -49.9%, median end 0, bust 92.1%
- draws top6 · system 5/6: ROI -100.0%, median end 0, bust 100.0%

## closing prices, 60/week

| strategy | ROI | weeks bet | week in profit | median end | 10th pct | 90th pct | season up | bust |
|---|---|---|---|---|---|---|---|---|
| draws top4 >=0.30 · system 2/4 | +25.4% | 171 | 25% | 1251 | 636 | 2064 | 69% | 0.0% |
| draws top5 >=0.30 · system 2/5 | +21.2% | 136 | 21% | 1173 | 744 | 1721 | 68% | 0.0% |
| draws top3 >=0.30 · singles | +12.0% | 203 | 45% | 1164 | 838 | 1498 | 73% | 0.0% |
| draws top4 >=0.30 · singles | +10.0% | 171 | 25% | 1118 | 847 | 1400 | 71% | 0.0% |
| draws top3 >=0.30 · system 2/3 | +28.4% | 203 | 18% | 1352 | 468 | 2411 | 68% | 2.0% |
| draws top3 >=0.31 · singles | +11.3% | 121 | 27% | 1093 | 842 | 1363 | 67% | 0.0% |
| draws top5 >=0.30 · singles | +8.9% | 136 | 26% | 1081 | 867 | 1307 | 68% | 0.0% |
| draws top3 >=0.31 · system 2/3 | +27.0% | 121 | 10% | 1143 | 517 | 2052 | 59% | 0.2% |
| strong top2 >=0.65 · 2-fold | +3.1% | 276 | 64% | 1062 | 730 | 1384 | 59% | 0.0% |
| draws top6 >=0.30 · system 2/6 | +6.8% | 106 | 12% | 1035 | 727 | 1408 | 55% | 0.0% |
| strong top4 >=0.55 · system 2/4 | +2.0% | 283 | 38% | 1037 | 790 | 1292 | 58% | 0.0% |
| strong top4 >=0.55 · singles | +1.3% | 283 | 47% | 1024 | 908 | 1143 | 60% | 0.0% |

worst five by the same measure:

- draws top5 · system 4/5: ROI -47.6%, median end 0, bust 70.3%
- draws top6 · system 4/6: ROI -55.5%, median end 0, bust 72.1%
- draws top5 · 5-fold: ROI -100.0%, median end 0, bust 100.0%
- draws top6 · system 5/6: ROI -100.0%, median end 0, bust 100.0%
- draws top6 · 6-fold: ROI -100.0%, median end 0, bust 100.0%

## closing prices, 10/line

| strategy | ROI | weeks bet | week in profit | median end | 10th pct | 90th pct | season up | bust |
|---|---|---|---|---|---|---|---|---|
| draws top4 >=0.30 · system 2/4 | +25.4% | 171 | 25% | 1271 | 664 | 2058 | 70% | 0.1% |
| draws top3 >=0.30 · system 2/3 | +28.4% | 203 | 18% | 1163 | 742 | 1692 | 67% | 0.0% |
| draws top5 >=0.30 · system 2/5 | +21.2% | 136 | 21% | 1289 | 574 | 2201 | 68% | 0.9% |
| draws top3 >=0.30 · 3-fold | +68.7% | 203 | 3% | 1107 | 750 | 1671 | 69% | 0.0% |
| draws top3 >=0.31 · 3-fold | +97.7% | 121 | 2% | 1158 | 840 | 1560 | 56% | 0.0% |
| draws top3 >=0.30 · singles | +12.0% | 203 | 45% | 1080 | 918 | 1253 | 73% | 0.0% |
| draws top4 >=0.30 · singles | +10.0% | 171 | 25% | 1074 | 898 | 1264 | 71% | 0.0% |
| draws top3 >=0.31 · system 2/3 | +27.0% | 121 | 10% | 1073 | 749 | 1507 | 60% | 0.0% |
| draws top5 >=0.30 · singles | +8.9% | 136 | 26% | 1066 | 891 | 1257 | 68% | 0.0% |
| draws top4 >=0.30 · system 3/4 | +45.1% | 171 | 7% | 1113 | 400 | 2581 | 55% | 0.2% |
| draws top4 >=0.30 · 4-fold | +99.0% | 171 | 1% | 820 | 770 | 1958 | 28% | 0.0% |
| draws top3 >=0.31 · singles | +11.3% | 121 | 27% | 1047 | 923 | 1184 | 68% | 0.0% |

worst five by the same measure:

- draws top6 >=0.30 · system 4/6: ROI -42.9%, median end 0, bust 64.3%
- draws top5 · system 4/5: ROI -47.6%, median end 0, bust 66.1%
- draws top6 · system 3/6: ROI -19.3%, median end 0, bust 79.2%
- draws top6 · system 4/6: ROI -55.5%, median end 0, bust 94.3%
- draws top6 · system 5/6: ROI -100.0%, median end 0, bust 100.0%

## The current mandate, for reference (draws top4 · system 2/4)

| regime | stake | ROI | median end | 10th | 90th | season up |
|---|---|---|---|---|---|---|
| closing | 60/week | +5.9% | 1052 | 279 | 1985 | 53% |
| closing | 10/line | +5.9% | 1057 | 290 | 2024 | 53% |
| winner-like | 60/week | +12.4% | 1195 | 401 | 2225 | 61% |
| winner-like | 10/line | +12.4% | 1198 | 376 | 2202 | 61% |
