# 立绘一致性报警报告 v3（批1-T1.10：组内相对口径）

口径 v3：表情为整张生成，全局 diff（实测 13-50%）是固有属性，绝对阈值无裁决意义——该数据本身坐实了方向 3「需要 inpaint 分区管线」的判断。
改用组内相对口径：blink 应为组内最小 diff（只动眼睛）；任意表情 >组内中位 1.6 倍 = 离群；构图质心偏移 >2% 绝对报警。

扫描 192 张表情差分，报警 120 张。

## 报警清单（按曝光度排序，人工裁决）

| 曝光 | 文件 | 级别 | 说明 |
|---|---|---|---|
| ★ | natsu-blink | WARN | blink diff=51.9% 高于组内中位 50.7%（blink 只该动眼睛，应为最小）；构图质心偏移 4.2% |
| ★ | natsu-happy | WARN | 构图质心偏移 4.3% |
| ★ | natsu-think | WARN | 构图质心偏移 2.4% |
| ★ | natsu-club-blink | WARN | blink diff=51.9% 高于组内中位 50.7%（blink 只该动眼睛，应为最小）；构图质心偏移 4.2% |
| ★ | natsu-club-happy | WARN | 构图质心偏移 4.3% |
| ★ | natsu-club-think | WARN | 构图质心偏移 2.4% |
| ★ | natsu-glam-blink | WARN | blink diff=34.6% 高于组内中位 32.6%（blink 只该动眼睛，应为最小）；构图质心偏移 3.5% |
| ★ | natsu-glam-happy | WARN | 构图质心偏移 6.1% |
| ★ | natsu-glam-sad | WARN | 构图质心偏移 9.7% |
| ★ | natsu-glam-think | WARN | 构图质心偏移 4.1% |
| ★ | natsu-p0-think | WARN | diff=10.0% 是组内中位（1.0%）的离群值；构图质心偏移 2.5% |
| ★ | natsu-p1-think | WARN | 构图质心偏移 4.5% |
| ★ | natsu-p2-blink | WARN | blink diff=34.0% 高于组内中位 31.2%（blink 只该动眼睛，应为最小）；构图质心偏移 4.3% |
| ★ | natsu-p3-blink | WARN | 构图质心偏移 2.6% |
| ★ | natsu-p4-think | WARN | diff=42.7% 是组内中位（6.6%）的离群值；构图质心偏移 3.6% |
| ★ | rin-blink | WARN | 构图质心偏移 12.0% |
| ★ | rin-think | WARN | 构图质心偏移 12.5% |
| ★ | rin-club-blink | WARN | 构图质心偏移 12.0% |
| ★ | rin-club-think | WARN | 构图质心偏移 12.5% |
| ★ | rin-glam-blink | WARN | 构图质心偏移 3.9% |
| ★ | rin-glam-happy | WARN | 构图质心偏移 2.7% |
| ★ | rin-glam-sad | WARN | 构图质心偏移 3.0% |
| ★ | rin-glam-think | WARN | 构图质心偏移 2.7% |
| ★ | rin-p0-blink | WARN | blink diff=30.0% 高于组内中位 29.5%（blink 只该动眼睛，应为最小）；构图质心偏移 3.4% |
| ★ | rin-p0-happy | WARN | 构图质心偏移 3.8% |
| ★ | rin-p0-sad | WARN | 构图质心偏移 2.4% |
| ★ | rin-p1-blink | WARN | 构图质心偏移 4.1% |
| ★ | rin-p1-happy | WARN | 构图质心偏移 2.5% |
| ★ | rin-p1-think | WARN | 构图质心偏移 3.5% |
| ★ | rin-p2-think | WARN | 构图质心偏移 2.6% |
| ★ | rin-p3-happy | WARN | 构图质心偏移 2.4% |
| ★ | rin-p3-sad | WARN | 构图质心偏移 2.1% |
| ★ | rin-p4-blink | WARN | 构图质心偏移 2.0% |
| ★ | rin-p4-happy | WARN | 构图质心偏移 4.2% |
| ★ | rin-p4-sad | WARN | 构图质心偏移 3.0% |
| ★ | rin-p4-think | WARN | 构图质心偏移 2.7% |
| ★ | shiori-blink | WARN | 构图质心偏移 3.1% |
| ★ | shiori-happy | WARN | 构图质心偏移 5.6% |
| ★ | shiori-think | WARN | 构图质心偏移 4.8% |
| ★ | shiori-club-blink | WARN | 构图质心偏移 3.1% |
| ★ | shiori-club-happy | WARN | 构图质心偏移 5.6% |
| ★ | shiori-club-think | WARN | 构图质心偏移 4.8% |
| ★ | shiori-glam-blink | WARN | 构图质心偏移 5.1% |
| ★ | shiori-p0-blink | WARN | 构图质心偏移 2.5% |
| ★ | shiori-p0-think | WARN | 构图质心偏移 2.5% |
| ★ | shiori-p1-blink | WARN | 构图质心偏移 9.2% |
| ★ | shiori-p1-happy | WARN | 构图质心偏移 10.5% |
| ★ | shiori-p1-sad | WARN | 构图质心偏移 10.2% |
| ★ | shiori-p1-think | WARN | 构图质心偏移 11.0% |
| ★ | shiori-p2-sad | WARN | 构图质心偏移 3.9% |
| ★ | shiori-p2-think | WARN | 构图质心偏移 3.9% |
| ★ | shiori-p4-blink | WARN | 构图质心偏移 2.7% |
| ★ | shiori-p4-sad | WARN | 构图质心偏移 2.5% |
| ★ | shiori-p4-think | WARN | 构图质心偏移 3.1% |
| ★ | suzu-blink | WARN | blink diff=48.9% 高于组内中位 41.5%（blink 只该动眼睛，应为最小）；构图质心偏移 8.4% |
| ★ | suzu-happy | WARN | 构图质心偏移 6.9% |
| ★ | suzu-sad | WARN | 构图质心偏移 7.2% |
| ★ | suzu-club-blink | WARN | blink diff=48.9% 高于组内中位 41.5%（blink 只该动眼睛，应为最小）；构图质心偏移 8.4% |
| ★ | suzu-club-happy | WARN | 构图质心偏移 6.9% |
| ★ | suzu-club-sad | WARN | 构图质心偏移 7.2% |
| ★ | suzu-glam-blink | WARN | 构图质心偏移 4.5% |
| ★ | suzu-glam-think | WARN | 构图质心偏移 2.9% |
| ★ | suzu-p0-blink | WARN | blink diff=46.8% 高于组内中位 46.7%（blink 只该动眼睛，应为最小）；构图质心偏移 16.7% |
| ★ | suzu-p0-sad | WARN | 构图质心偏移 16.0% |
| ★ | suzu-p0-think | WARN | 构图质心偏移 16.4% |
| ★ | suzu-p1-blink | WARN | 构图质心偏移 6.6% |
| ★ | suzu-p1-happy | WARN | 构图质心偏移 6.7% |
| ★ | suzu-p1-sad | WARN | 构图质心偏移 6.7% |
| ★ | suzu-p1-think | WARN | 构图质心偏移 5.0% |
| ★ | suzu-p2-blink | WARN | 构图质心偏移 2.3% |
| ★ | suzu-p2-happy | WARN | 构图质心偏移 2.5% |
| ★ | suzu-p2-sad | WARN | 构图质心偏移 2.2% |
| ★ | suzu-p4-blink | WARN | 构图质心偏移 3.0% |
| ★ | suzu-p4-happy | WARN | 构图质心偏移 2.8% |
| ★ | ume-blink | WARN | 构图质心偏移 7.0% |
| ★ | ume-happy | WARN | 构图质心偏移 6.2% |
| ★ | ume-sad | WARN | 构图质心偏移 4.2% |
| ★ | ume-think | WARN | 构图质心偏移 2.7% |
| ★ | ume-club-blink | WARN | 构图质心偏移 7.0% |
| ★ | ume-club-happy | WARN | 构图质心偏移 6.2% |
| ★ | ume-club-sad | WARN | 构图质心偏移 4.2% |
| ★ | ume-club-think | WARN | 构图质心偏移 2.7% |
| ★ | ume-glam-blink | WARN | 构图质心偏移 3.8% |
| ★ | ume-glam-happy | WARN | 构图质心偏移 5.3% |
| ★ | ume-glam-sad | WARN | 构图质心偏移 10.1% |
| ★ | ume-p0-blink | WARN | 构图质心偏移 3.0% |
| ★ | ume-p0-happy | WARN | 构图质心偏移 5.9% |
| ★ | ume-p0-think | WARN | 构图质心偏移 3.9% |
| ★ | ume-p1-blink | WARN | 构图质心偏移 3.4% |
| ★ | ume-p1-happy | WARN | 构图质心偏移 2.6% |
| ★ | ume-p2-happy | WARN | 构图质心偏移 3.9% |
| ★ | ume-p2-sad | WARN | 构图质心偏移 2.8% |
| ★ | ume-p3-happy | WARN | 构图质心偏移 2.8% |
| ★ | ume-p3-sad | WARN | 构图质心偏移 3.3% |
| ★ | ume-p4-blink | WARN | blink diff=30.8% 高于组内中位 30.5%（blink 只该动眼睛，应为最小）；构图质心偏移 3.3% |
| ★ | yuki-blink | WARN | 构图质心偏移 6.4% |
| ★ | yuki-happy | WARN | 构图质心偏移 6.6% |
| ★ | yuki-sad | WARN | 构图质心偏移 3.2% |
| ★ | yuki-think | WARN | 构图质心偏移 10.5% |
| ★ | yuki-club-blink | WARN | 构图质心偏移 6.4% |
| ★ | yuki-club-happy | WARN | 构图质心偏移 6.6% |
| ★ | yuki-club-sad | WARN | 构图质心偏移 3.2% |
| ★ | yuki-club-think | WARN | 构图质心偏移 10.5% |
| ★ | yuki-glam-blink | WARN | 构图质心偏移 9.5% |
| ★ | yuki-glam-happy | WARN | 构图质心偏移 2.8% |
| ★ | yuki-glam-sad | WARN | 构图质心偏移 5.7% |
| ★ | yuki-glam-think | WARN | 构图质心偏移 5.2% |
| ★ | yuki-p0-blink | WARN | blink diff=22.0% 高于组内中位 21.1%（blink 只该动眼睛，应为最小）；构图质心偏移 2.0% |
| ★ | yuki-p0-think | WARN | 构图质心偏移 3.2% |
| ★ | yuki-p1-blink | WARN | 构图质心偏移 5.2% |
| ★ | yuki-p1-happy | WARN | 构图质心偏移 6.9% |
| ★ | yuki-p1-sad | WARN | 构图质心偏移 9.7% |
| ★ | yuki-p1-think | WARN | 构图质心偏移 9.1% |
| ★ | yuki-p2-happy | WARN | 构图质心偏移 3.4% |
| ★ | yuki-p2-sad | WARN | 构图质心偏移 3.9% |
| ★ | yuki-p2-think | WARN | 构图质心偏移 3.3% |
| ★ | yuki-p4-blink | WARN | blink diff=21.6% 高于组内中位 21.6%（blink 只该动眼睛，应为最小）；构图质心偏移 2.5% |
| ★ | yuki-p4-happy | WARN | 构图质心偏移 3.9% |
| ★ | yuki-p4-sad | WARN | 构图质心偏移 2.9% |
| ★ | yuki-p4-think | WARN | 构图质心偏移 3.2% |

## 全量明细

| 曝光 | 文件 | 级别 | 说明 |
|---|---|---|---|
| ★ | natsu-blink | WARN | diff=51.9%（组中位 50.7%） blink diff=51.9% 高于组内中位 50.7%（blink 只该动眼睛，应为最小）；构图质心偏移 4.2% |
| ★ | natsu-happy | WARN | diff=50.7%（组中位 50.7%） 构图质心偏移 4.3% |
| ★ | natsu-sad | OK | diff=50.1%（组中位 50.7%） 一致 |
| ★ | natsu-think | WARN | diff=15.6%（组中位 50.7%） 构图质心偏移 2.4% |
| ★ | natsu-club-blink | WARN | diff=51.9%（组中位 50.7%） blink diff=51.9% 高于组内中位 50.7%（blink 只该动眼睛，应为最小）；构图质心偏移 4.2% |
| ★ | natsu-club-happy | WARN | diff=50.7%（组中位 50.7%） 构图质心偏移 4.3% |
| ★ | natsu-club-sad | OK | diff=50.1%（组中位 50.7%） 一致 |
| ★ | natsu-club-think | WARN | diff=15.6%（组中位 50.7%） 构图质心偏移 2.4% |
| ★ | natsu-glam-blink | WARN | diff=34.6%（组中位 32.6%） blink diff=34.6% 高于组内中位 32.6%（blink 只该动眼睛，应为最小）；构图质心偏移 3.5% |
| ★ | natsu-glam-happy | WARN | diff=31.1%（组中位 32.6%） 构图质心偏移 6.1% |
| ★ | natsu-glam-sad | WARN | diff=32.6%（组中位 32.6%） 构图质心偏移 9.7% |
| ★ | natsu-glam-think | WARN | diff=26.8%（组中位 32.6%） 构图质心偏移 4.1% |
| ★ | natsu-p0-blink | OK | diff=0.9%（组中位 1.0%） 一致 |
| ★ | natsu-p0-happy | OK | diff=1.0%（组中位 1.0%） 一致 |
| ★ | natsu-p0-sad | OK | diff=0.9%（组中位 1.0%） 一致 |
| ★ | natsu-p0-think | WARN | diff=10.0%（组中位 1.0%） diff=10.0% 是组内中位（1.0%）的离群值；构图质心偏移 2.5% |
| ★ | natsu-p1-blink | OK | diff=11.9%（组中位 29.2%） 一致 |
| ★ | natsu-p1-happy | OK | diff=29.2%（组中位 29.2%） 一致 |
| ★ | natsu-p1-sad | OK | diff=9.6%（组中位 29.2%） 一致 |
| ★ | natsu-p1-think | WARN | diff=39.2%（组中位 29.2%） 构图质心偏移 4.5% |
| ★ | natsu-p2-blink | WARN | diff=34.0%（组中位 31.2%） blink diff=34.0% 高于组内中位 31.2%（blink 只该动眼睛，应为最小）；构图质心偏移 4.3% |
| ★ | natsu-p2-happy | OK | diff=9.7%（组中位 31.2%） 一致 |
| ★ | natsu-p2-sad | OK | diff=1.9%（组中位 31.2%） 一致 |
| ★ | natsu-p2-think | OK | diff=31.2%（组中位 31.2%） 一致 |
| ★ | natsu-p3-blink | WARN | diff=30.9%（组中位 30.9%） 构图质心偏移 2.6% |
| ★ | natsu-p3-happy | OK | diff=23.9%（组中位 30.9%） 一致 |
| ★ | natsu-p3-sad | OK | diff=23.8%（组中位 30.9%） 一致 |
| ★ | natsu-p3-think | OK | diff=31.4%（组中位 30.9%） 一致 |
| ★ | natsu-p4-blink | OK | diff=6.5%（组中位 6.6%） 一致 |
| ★ | natsu-p4-happy | OK | diff=6.5%（组中位 6.6%） 一致 |
| ★ | natsu-p4-sad | OK | diff=6.6%（组中位 6.6%） 一致 |
| ★ | natsu-p4-think | WARN | diff=42.7%（组中位 6.6%） diff=42.7% 是组内中位（6.6%）的离群值；构图质心偏移 3.6% |
| ★ | rin-blink | WARN | diff=34.4%（组中位 34.4%） 构图质心偏移 12.0% |
| ★ | rin-happy | OK | diff=32.8%（组中位 34.4%） 一致 |
| ★ | rin-sad | OK | diff=36.3%（组中位 34.4%） 一致 |
| ★ | rin-think | WARN | diff=32.5%（组中位 34.4%） 构图质心偏移 12.5% |
| ★ | rin-club-blink | WARN | diff=34.4%（组中位 34.4%） 构图质心偏移 12.0% |
| ★ | rin-club-happy | OK | diff=32.8%（组中位 34.4%） 一致 |
| ★ | rin-club-sad | OK | diff=36.3%（组中位 34.4%） 一致 |
| ★ | rin-club-think | WARN | diff=32.5%（组中位 34.4%） 构图质心偏移 12.5% |
| ★ | rin-glam-blink | WARN | diff=18.5%（组中位 18.5%） 构图质心偏移 3.9% |
| ★ | rin-glam-happy | WARN | diff=17.4%（组中位 18.5%） 构图质心偏移 2.7% |
| ★ | rin-glam-sad | WARN | diff=22.7%（组中位 18.5%） 构图质心偏移 3.0% |
| ★ | rin-glam-think | WARN | diff=16.7%（组中位 18.5%） 构图质心偏移 2.7% |
| ★ | rin-p0-blink | WARN | diff=30.0%（组中位 29.5%） blink diff=30.0% 高于组内中位 29.5%（blink 只该动眼睛，应为最小）；构图质心偏移 3.4% |
| ★ | rin-p0-happy | WARN | diff=28.2%（组中位 29.5%） 构图质心偏移 3.8% |
| ★ | rin-p0-sad | WARN | diff=29.5%（组中位 29.5%） 构图质心偏移 2.4% |
| ★ | rin-p0-think | OK | diff=29.0%（组中位 29.5%） 一致 |
| ★ | rin-p1-blink | WARN | diff=29.8%（组中位 29.8%） 构图质心偏移 4.1% |
| ★ | rin-p1-happy | WARN | diff=26.8%（组中位 29.8%） 构图质心偏移 2.5% |
| ★ | rin-p1-sad | OK | diff=28.0%（组中位 29.8%） 一致 |
| ★ | rin-p1-think | WARN | diff=32.1%（组中位 29.8%） 构图质心偏移 3.5% |
| ★ | rin-p2-blink | OK | diff=32.0%（组中位 32.0%） 一致 |
| ★ | rin-p2-happy | OK | diff=32.3%（组中位 32.0%） 一致 |
| ★ | rin-p2-sad | OK | diff=30.6%（组中位 32.0%） 一致 |
| ★ | rin-p2-think | WARN | diff=29.9%（组中位 32.0%） 构图质心偏移 2.6% |
| ★ | rin-p3-blink | OK | diff=26.6%（组中位 27.3%） 一致 |
| ★ | rin-p3-happy | WARN | diff=29.4%（组中位 27.3%） 构图质心偏移 2.4% |
| ★ | rin-p3-sad | WARN | diff=26.5%（组中位 27.3%） 构图质心偏移 2.1% |
| ★ | rin-p3-think | OK | diff=27.3%（组中位 27.3%） 一致 |
| ★ | rin-p4-blink | WARN | diff=29.7%（组中位 32.3%） 构图质心偏移 2.0% |
| ★ | rin-p4-happy | WARN | diff=32.3%（组中位 32.3%） 构图质心偏移 4.2% |
| ★ | rin-p4-sad | WARN | diff=33.5%（组中位 32.3%） 构图质心偏移 3.0% |
| ★ | rin-p4-think | WARN | diff=30.9%（组中位 32.3%） 构图质心偏移 2.7% |
| ★ | shiori-blink | WARN | diff=40.1%（组中位 41.6%） 构图质心偏移 3.1% |
| ★ | shiori-happy | WARN | diff=41.6%（组中位 41.6%） 构图质心偏移 5.6% |
| ★ | shiori-sad | OK | diff=39.5%（组中位 41.6%） 一致 |
| ★ | shiori-think | WARN | diff=42.5%（组中位 41.6%） 构图质心偏移 4.8% |
| ★ | shiori-club-blink | WARN | diff=40.1%（组中位 41.6%） 构图质心偏移 3.1% |
| ★ | shiori-club-happy | WARN | diff=41.6%（组中位 41.6%） 构图质心偏移 5.6% |
| ★ | shiori-club-sad | OK | diff=39.5%（组中位 41.6%） 一致 |
| ★ | shiori-club-think | WARN | diff=42.5%（组中位 41.6%） 构图质心偏移 4.8% |
| ★ | shiori-glam-blink | WARN | diff=24.8%（组中位 24.8%） 构图质心偏移 5.1% |
| ★ | shiori-glam-happy | OK | diff=18.7%（组中位 24.8%） 一致 |
| ★ | shiori-glam-sad | OK | diff=27.2%（组中位 24.8%） 一致 |
| ★ | shiori-glam-think | OK | diff=17.5%（组中位 24.8%） 一致 |
| ★ | shiori-p0-blink | WARN | diff=26.4%（组中位 26.4%） 构图质心偏移 2.5% |
| ★ | shiori-p0-happy | OK | diff=25.4%（组中位 26.4%） 一致 |
| ★ | shiori-p0-sad | OK | diff=25.8%（组中位 26.4%） 一致 |
| ★ | shiori-p0-think | WARN | diff=26.5%（组中位 26.4%） 构图质心偏移 2.5% |
| ★ | shiori-p1-blink | WARN | diff=39.5%（组中位 40.4%） 构图质心偏移 9.2% |
| ★ | shiori-p1-happy | WARN | diff=40.2%（组中位 40.4%） 构图质心偏移 10.5% |
| ★ | shiori-p1-sad | WARN | diff=40.4%（组中位 40.4%） 构图质心偏移 10.2% |
| ★ | shiori-p1-think | WARN | diff=40.5%（组中位 40.4%） 构图质心偏移 11.0% |
| ★ | shiori-p2-blink | OK | diff=27.3%（组中位 27.3%） 一致 |
| ★ | shiori-p2-happy | OK | diff=26.7%（组中位 27.3%） 一致 |
| ★ | shiori-p2-sad | WARN | diff=25.7%（组中位 27.3%） 构图质心偏移 3.9% |
| ★ | shiori-p2-think | WARN | diff=27.8%（组中位 27.3%） 构图质心偏移 3.9% |
| ★ | shiori-p3-blink | OK | diff=24.3%（组中位 25.7%） 一致 |
| ★ | shiori-p3-happy | OK | diff=25.7%（组中位 25.7%） 一致 |
| ★ | shiori-p3-sad | OK | diff=24.3%（组中位 25.7%） 一致 |
| ★ | shiori-p3-think | OK | diff=26.0%（组中位 25.7%） 一致 |
| ★ | shiori-p4-blink | WARN | diff=23.4%（组中位 25.5%） 构图质心偏移 2.7% |
| ★ | shiori-p4-happy | OK | diff=26.7%（组中位 25.5%） 一致 |
| ★ | shiori-p4-sad | WARN | diff=24.9%（组中位 25.5%） 构图质心偏移 2.5% |
| ★ | shiori-p4-think | WARN | diff=25.5%（组中位 25.5%） 构图质心偏移 3.1% |
| ★ | suzu-blink | WARN | diff=48.9%（组中位 41.5%） blink diff=48.9% 高于组内中位 41.5%（blink 只该动眼睛，应为最小）；构图质心偏移 8.4% |
| ★ | suzu-happy | WARN | diff=40.9%（组中位 41.5%） 构图质心偏移 6.9% |
| ★ | suzu-sad | WARN | diff=41.5%（组中位 41.5%） 构图质心偏移 7.2% |
| ★ | suzu-think | OK | diff=21.6%（组中位 41.5%） 一致 |
| ★ | suzu-club-blink | WARN | diff=48.9%（组中位 41.5%） blink diff=48.9% 高于组内中位 41.5%（blink 只该动眼睛，应为最小）；构图质心偏移 8.4% |
| ★ | suzu-club-happy | WARN | diff=40.9%（组中位 41.5%） 构图质心偏移 6.9% |
| ★ | suzu-club-sad | WARN | diff=41.5%（组中位 41.5%） 构图质心偏移 7.2% |
| ★ | suzu-club-think | OK | diff=21.6%（组中位 41.5%） 一致 |
| ★ | suzu-glam-blink | WARN | diff=20.9%（组中位 23.3%） 构图质心偏移 4.5% |
| ★ | suzu-glam-happy | OK | diff=22.9%（组中位 23.3%） 一致 |
| ★ | suzu-glam-sad | OK | diff=24.5%（组中位 23.3%） 一致 |
| ★ | suzu-glam-think | WARN | diff=23.3%（组中位 23.3%） 构图质心偏移 2.9% |
| ★ | suzu-p0-blink | WARN | diff=46.8%（组中位 46.7%） blink diff=46.8% 高于组内中位 46.7%（blink 只该动眼睛，应为最小）；构图质心偏移 16.7% |
| ★ | suzu-p0-happy | OK | diff=0.8%（组中位 46.7%） 一致 |
| ★ | suzu-p0-sad | WARN | diff=46.7%（组中位 46.7%） 构图质心偏移 16.0% |
| ★ | suzu-p0-think | WARN | diff=44.5%（组中位 46.7%） 构图质心偏移 16.4% |
| ★ | suzu-p1-blink | WARN | diff=35.1%（组中位 35.1%） 构图质心偏移 6.6% |
| ★ | suzu-p1-happy | WARN | diff=35.1%（组中位 35.1%） 构图质心偏移 6.7% |
| ★ | suzu-p1-sad | WARN | diff=35.0%（组中位 35.1%） 构图质心偏移 6.7% |
| ★ | suzu-p1-think | WARN | diff=36.1%（组中位 35.1%） 构图质心偏移 5.0% |
| ★ | suzu-p2-blink | WARN | diff=37.0%（组中位 37.0%） 构图质心偏移 2.3% |
| ★ | suzu-p2-happy | WARN | diff=37.9%（组中位 37.0%） 构图质心偏移 2.5% |
| ★ | suzu-p2-sad | WARN | diff=36.7%（组中位 37.0%） 构图质心偏移 2.2% |
| ★ | suzu-p2-think | OK | diff=34.9%（组中位 37.0%） 一致 |
| ★ | suzu-p3-blink | OK | diff=57.3%（组中位 57.3%） 一致 |
| ★ | suzu-p3-happy | OK | diff=57.2%（组中位 57.3%） 一致 |
| ★ | suzu-p3-sad | OK | diff=57.3%（组中位 57.3%） 一致 |
| ★ | suzu-p3-think | OK | diff=57.5%（组中位 57.3%） 一致 |
| ★ | suzu-p4-blink | WARN | diff=26.9%（组中位 27.2%） 构图质心偏移 3.0% |
| ★ | suzu-p4-happy | WARN | diff=28.5%（组中位 27.2%） 构图质心偏移 2.8% |
| ★ | suzu-p4-sad | OK | diff=26.5%（组中位 27.2%） 一致 |
| ★ | suzu-p4-think | OK | diff=27.2%（组中位 27.2%） 一致 |
| ★ | ume-blink | WARN | diff=41.9%（组中位 41.9%） 构图质心偏移 7.0% |
| ★ | ume-happy | WARN | diff=42.9%（组中位 41.9%） 构图质心偏移 6.2% |
| ★ | ume-sad | WARN | diff=37.6%（组中位 41.9%） 构图质心偏移 4.2% |
| ★ | ume-think | WARN | diff=12.8%（组中位 41.9%） 构图质心偏移 2.7% |
| ★ | ume-club-blink | WARN | diff=41.9%（组中位 41.9%） 构图质心偏移 7.0% |
| ★ | ume-club-happy | WARN | diff=42.9%（组中位 41.9%） 构图质心偏移 6.2% |
| ★ | ume-club-sad | WARN | diff=37.6%（组中位 41.9%） 构图质心偏移 4.2% |
| ★ | ume-club-think | WARN | diff=12.8%（组中位 41.9%） 构图质心偏移 2.7% |
| ★ | ume-glam-blink | WARN | diff=34.9%（组中位 34.9%） 构图质心偏移 3.8% |
| ★ | ume-glam-happy | WARN | diff=33.9%（组中位 34.9%） 构图质心偏移 5.3% |
| ★ | ume-glam-sad | WARN | diff=38.8%（组中位 34.9%） 构图质心偏移 10.1% |
| ★ | ume-glam-think | OK | diff=34.6%（组中位 34.9%） 一致 |
| ★ | ume-p0-blink | WARN | diff=30.2%（组中位 31.3%） 构图质心偏移 3.0% |
| ★ | ume-p0-happy | WARN | diff=31.3%（组中位 31.3%） 构图质心偏移 5.9% |
| ★ | ume-p0-sad | OK | diff=31.6%（组中位 31.3%） 一致 |
| ★ | ume-p0-think | WARN | diff=30.3%（组中位 31.3%） 构图质心偏移 3.9% |
| ★ | ume-p1-blink | WARN | diff=30.8%（组中位 32.3%） 构图质心偏移 3.4% |
| ★ | ume-p1-happy | WARN | diff=32.3%（组中位 32.3%） 构图质心偏移 2.6% |
| ★ | ume-p1-sad | OK | diff=32.3%（组中位 32.3%） 一致 |
| ★ | ume-p1-think | OK | diff=29.5%（组中位 32.3%） 一致 |
| ★ | ume-p2-blink | OK | diff=29.5%（组中位 29.7%） 一致 |
| ★ | ume-p2-happy | WARN | diff=29.2%（组中位 29.7%） 构图质心偏移 3.9% |
| ★ | ume-p2-sad | WARN | diff=29.7%（组中位 29.7%） 构图质心偏移 2.8% |
| ★ | ume-p2-think | OK | diff=30.5%（组中位 29.7%） 一致 |
| ★ | ume-p3-blink | OK | diff=28.7%（组中位 29.9%） 一致 |
| ★ | ume-p3-happy | WARN | diff=29.5%（组中位 29.9%） 构图质心偏移 2.8% |
| ★ | ume-p3-sad | WARN | diff=29.9%（组中位 29.9%） 构图质心偏移 3.3% |
| ★ | ume-p3-think | OK | diff=32.5%（组中位 29.9%） 一致 |
| ★ | ume-p4-blink | WARN | diff=30.8%（组中位 30.5%） blink diff=30.8% 高于组内中位 30.5%（blink 只该动眼睛，应为最小）；构图质心偏移 3.3% |
| ★ | ume-p4-happy | OK | diff=29.7%（组中位 30.5%） 一致 |
| ★ | ume-p4-sad | OK | diff=30.5%（组中位 30.5%） 一致 |
| ★ | ume-p4-think | OK | diff=28.7%（组中位 30.5%） 一致 |
| ★ | yuki-blink | WARN | diff=42.1%（组中位 47.5%） 构图质心偏移 6.4% |
| ★ | yuki-happy | WARN | diff=47.5%（组中位 47.5%） 构图质心偏移 6.6% |
| ★ | yuki-sad | WARN | diff=44.4%（组中位 47.5%） 构图质心偏移 3.2% |
| ★ | yuki-think | WARN | diff=53.8%（组中位 47.5%） 构图质心偏移 10.5% |
| ★ | yuki-club-blink | WARN | diff=42.1%（组中位 47.5%） 构图质心偏移 6.4% |
| ★ | yuki-club-happy | WARN | diff=47.5%（组中位 47.5%） 构图质心偏移 6.6% |
| ★ | yuki-club-sad | WARN | diff=44.4%（组中位 47.5%） 构图质心偏移 3.2% |
| ★ | yuki-club-think | WARN | diff=53.8%（组中位 47.5%） 构图质心偏移 10.5% |
| ★ | yuki-glam-blink | WARN | diff=19.3%（组中位 23.6%） 构图质心偏移 9.5% |
| ★ | yuki-glam-happy | WARN | diff=21.7%（组中位 23.6%） 构图质心偏移 2.8% |
| ★ | yuki-glam-sad | WARN | diff=23.6%（组中位 23.6%） 构图质心偏移 5.7% |
| ★ | yuki-glam-think | WARN | diff=26.9%（组中位 23.6%） 构图质心偏移 5.2% |
| ★ | yuki-p0-blink | WARN | diff=22.0%（组中位 21.1%） blink diff=22.0% 高于组内中位 21.1%（blink 只该动眼睛，应为最小）；构图质心偏移 2.0% |
| ★ | yuki-p0-happy | OK | diff=20.4%（组中位 21.1%） 一致 |
| ★ | yuki-p0-sad | OK | diff=20.5%（组中位 21.1%） 一致 |
| ★ | yuki-p0-think | WARN | diff=21.1%（组中位 21.1%） 构图质心偏移 3.2% |
| ★ | yuki-p1-blink | WARN | diff=32.6%（组中位 34.0%） 构图质心偏移 5.2% |
| ★ | yuki-p1-happy | WARN | diff=34.0%（组中位 34.0%） 构图质心偏移 6.9% |
| ★ | yuki-p1-sad | WARN | diff=34.0%（组中位 34.0%） 构图质心偏移 9.7% |
| ★ | yuki-p1-think | WARN | diff=33.3%（组中位 34.0%） 构图质心偏移 9.1% |
| ★ | yuki-p2-blink | OK | diff=20.3%（组中位 21.3%） 一致 |
| ★ | yuki-p2-happy | WARN | diff=24.1%（组中位 21.3%） 构图质心偏移 3.4% |
| ★ | yuki-p2-sad | WARN | diff=21.3%（组中位 21.3%） 构图质心偏移 3.9% |
| ★ | yuki-p2-think | WARN | diff=20.3%（组中位 21.3%） 构图质心偏移 3.3% |
| ★ | yuki-p3-blink | OK | diff=21.7%（组中位 21.7%） 一致 |
| ★ | yuki-p3-happy | OK | diff=22.3%（组中位 21.7%） 一致 |
| ★ | yuki-p3-sad | OK | diff=20.5%（组中位 21.7%） 一致 |
| ★ | yuki-p3-think | OK | diff=20.9%（组中位 21.7%） 一致 |
| ★ | yuki-p4-blink | WARN | diff=21.6%（组中位 21.6%） blink diff=21.6% 高于组内中位 21.6%（blink 只该动眼睛，应为最小）；构图质心偏移 2.5% |
| ★ | yuki-p4-happy | WARN | diff=20.8%（组中位 21.6%） 构图质心偏移 3.9% |
| ★ | yuki-p4-sad | WARN | diff=21.0%（组中位 21.6%） 构图质心偏移 2.9% |
| ★ | yuki-p4-think | WARN | diff=21.6%（组中位 21.6%） 构图质心偏移 3.2% |
