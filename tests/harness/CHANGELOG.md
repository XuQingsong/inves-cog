# Frozen-input changes

| File | Old hash | New SHA-256 | Reason | Requirement |
|---|---|---|---|---|
| tests/fixtures/phase1/harness/sample.json | absent | 0feb1942305b5d73cc2980f6e37ef881e85c35a13bd9d1c3b886c0437321473b | Initial synthetic NULL input | FR-M0-08 |
| tests/fixtures/phase1/m1/form4_synthetic.xml | absent | dc24e8daac3fca9389fc7f5b41490f7700916a158a44cebae7c2da794b20f573 | M1 v2 handwritten deterministic fixture / synthetic recording, no real-source claim | Q-M1-5–16; FR-M0-08 |
| tests/fixtures/phase1/m1/wide_candidates.json | absent | 35d695449860d9a132565b35e55cd340858288b96063b4f337fa8a7919f0a484 | M1 v2 handwritten deterministic fixture / synthetic recording, no real-source claim | Q-M1-5–16; FR-M0-08 |
| tests/fixtures/phase1/recordings/entity_tagging/0742ee7bd1402c921e8e40cf111b463612d12952d70ff7418c48425a72c26339.json | absent | 561b5cd45c11ae0bfc9d7d6b4049f10fe2f82ab6d31c805441dee6e1f12cacf0 | M1 v2 handwritten deterministic fixture / synthetic recording, no real-source claim | Q-M1-5–16; FR-M0-08 |
| tests/fixtures/phase1/recordings/entity_tagging/186a42f0828f600fddbdae7f3d88ab0839bb9d59505d4b3384729894df273ad8.json | absent | dcf982a74e10f064b7f14058f043b4ed976b5df31df8e491c8329849cad1fe87 | M1 v2 handwritten deterministic fixture / synthetic recording, no real-source claim | Q-M1-5–16; FR-M0-08 |
| tests/fixtures/phase1/recordings/entity_tagging/a6b51d6180f8aafc478c37ceac81baa865671a9e3f2339fbc4ba57f4e3a520c6.json | absent | b9ddb7cb12b74a5fb1ce1cd94569336f142c3f9cb44f3734c1b49da8e0f9600f | M1 v2 handwritten deterministic fixture / synthetic recording, no real-source claim | Q-M1-5–16; FR-M0-08 |
| tests/fixtures/phase1/recordings/info_fields_extraction/0742ee7bd1402c921e8e40cf111b463612d12952d70ff7418c48425a72c26339.json | absent | 5a82d6d93b391fe8330ce1d8c5cc36163f7ca4545086b1a69b80f9eb9c59786b | M1 v2 handwritten deterministic fixture / synthetic recording, no real-source claim | Q-M1-5–16; FR-M0-08 |
| tests/fixtures/phase1/recordings/info_fields_extraction/186a42f0828f600fddbdae7f3d88ab0839bb9d59505d4b3384729894df273ad8.json | absent | e9ae4d2c682840f3279eebf7710449cc7db97748c032316e20cd5ee2ffaadd0c | M1 v2 handwritten deterministic fixture / synthetic recording, no real-source claim | Q-M1-5–16; FR-M0-08 |

2026-10-14 m1/sec_acceptance_conflict.json 9631c3b17cc7fcb48cf7241f677498c68bcf96498be8231814c9666aa1678d30 FR-M1-06/Q-M1-8: freeze three official SEC acceptance-time conflicts; preserve red assertion pending contract answer.

2026-10-14 tests/fixtures/phase1/m1/sec_acceptance_conflict.json 9631c3b17cc7fcb48cf7241f677498c68bcf96498be8231814c9666aa1678d30 FR-M1-06/Q-M1-8: complete repository-relative frozen fixture path for official SEC comparison.

- 2026-10-14 M1: freeze SEC official Form 4 accession 0001140361-26-039158 XML and index Accepted provenance; S transaction, 2399 shares, 332.01 USD, officer=true. Existing synthetic P input unchanged.
- m1/form4_official.xml new sha256 3fd3b9cbe1cc36f6c0fb98a1a6f2f10708dd0974a326e70269db9a8a9e7d4ab7: official SEC input frozen once; no existing input modified.
- m1/form4_official.json new sha256 bd43f415dbff43d7a34bc131af7e3460cf8427b67c1a0b96d2445fe598bef243: official SEC input frozen once; no existing input modified.
2026-10-14 tests/fixtures/phase1/m1/form4_official.xml 3fd3b9cbe1cc36f6c0fb98a1a6f2f10708dd0974a326e70269db9a8a9e7d4ab7 complete required frozen path and new hash.
2026-10-14 tests/fixtures/phase1/m1/form4_official.json bd43f415dbff43d7a34bc131af7e3460cf8427b67c1a0b96d2445fe598bef243 complete required frozen path and new hash.
