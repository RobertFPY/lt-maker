# P1-T03 PC-reference trace evidence

Reference revision: `9314f54b49f4552b5a3d023b4da0012ce7dfbc89`.

Each JSONL capture was produced by `app/tests/recovery_trace_runner.py` using
the Trace V1 overlay. Reference captures are retained in the executor temp
directory as `p1-t03-*.jsonl`; recovery captures were compared directly and
passed. The hashes below identify the reference fixture bytes used for review.

| Scenario | Reference fixture | SHA-256 | Terminal checkpoint(s) |
| --- | --- | --- | --- |
| S1 | `p1-t03-s1-reference-v2.jsonl` | `17FB4C8F9417D463879FE19607E5B869CC75452F5659F187AC20555EEB662E75` | `player.control.ready` |
| S2 | `p1-t03-s2-reference.jsonl` | `43B5680F6E7FCEAED5F423831D073522317E3EA49E55B27E31FE9C375865B539` | `save.restore.complete` |
| S3 | N/A -- reference unsupported | -- | -- |
| S4 | `p1-t03-s4-reference.jsonl` | `636547840913373410FB6612A528494B11DBDA0CEB22A2A7E9F835272F040428` | `restart.complete` |
| S5 | `p1-t03-s5-reference.jsonl` | `F545EA0ECA7588EEBC5DF018F1FE7F185B285E73252CDA9F4C17244CF5FFEADE` | `combat.cleanup.complete` |
| S6 | `p1-t03-s6-reference.jsonl` | `EBE882CB9247BF46A448AAC7E158004F789D87B1370304DB76955E7AB095EB19` | `combat.cleanup.complete` |
| S7 | `p1-t03-s7-reference.jsonl` | `8EAFDE83F8A9BF636965BFEB3606B609CB0BAEFB8ADF96A42033DB854CD7AC22` | `combat.cleanup.complete` |
| S8 | `p1-t03-s8-reference.jsonl` | `F2039EA3AEB4FDAD566F9A13AC612A6C465DB9B81DA20C8B22690D965B5EE13D` | `combat.cleanup.complete` |
| S9 | `p1-t03-s9-reference.jsonl` | `20C12378399E44A326AE26ED3F087515860AB52AA38F08E5534FACC541DB4B69` | `combat.cleanup.complete` |
| S10 | `p1-t03-s10-reference.jsonl` | `CF6CAF5FC6D1EC365BEE8982925F3EAB583840889BA768303C27B0A8B07EC3D1` | `item.broken.cleanup.complete` |
| S11 | `p1-t03-s11-reference.jsonl` | `D6D02B66537E97A422C6BB86F5E97234E181532102D941446F3847572D3BA0B2` | `promotion.complete` |
| S12 | `p1-t03-s12-reference.jsonl` | `6A8EC39E493B984EC87D1A1EC03FC53C06A6A92D8DA8650E33AD0513229E3C43` | `aura.propagated`, `aura.load.complete`, `aura.teardown.complete` |
| S13 | `p1-t03-s13-reference-resolved.jsonl` | `B75E3414B552E0BE4941C41B01A20D96C68C0CCCFB21945E482CF7E03828749E` | `fog.move.preview`, `fog.move.cancel.complete`, `fog.wait.complete` |
| S14 | `p1-t03-s14-reference.jsonl` | `10E3A5EA0EA734FE9F5A3E3721221A6D36F1C72053C11AC7BD40A676EA4AC5D0` | `tilemap.change.commit` |
| S15 | `p1-t03-s15-reference.jsonl` | `BA02193DAEEF908E32E7B55665573E927F96EAAB47673C8ED10419670154B593` | `phase.transition.complete` |
| S16 | `p1-t03-s16-reference.jsonl` | `8B12BF2F43ADDC6777802451C20F34172A07C1BFDAE838ACEB0AE5C2B9E3EAEC` | `fast_forward.comparison.end` |
| S17 | `p1-t03-s17-reference.jsonl` | `20A582F6EEE02DC5A00DDEC4DF3D87ED80594DEE27ED444C8C7FF7A1926100F0` | `observer.disabled.baseline`, `observer.idle.complete` |
| S18 | `p1-t03-s18-reference.jsonl` | `284CA80D724F7C8BEC927124F55CBB1E5B6415D5D972374F460F561F31889F10` | `game_over.transition.commit`, `game_over.title_start.commit`, `restart.complete` |

S17 is hybrid by contract: the PC capture is disabled-only; recovery
debugger-idle and profiler-idle traces both compare equal to recovery disabled.
S16 is hybrid by contract: PC OFF equals recovery OFF; recovery ON equals
recovery OFF in logical Trace V1 fields under INV-06.
