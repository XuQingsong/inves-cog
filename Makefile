.PHONY: phase1-test phase1-replay phase1-cases

phase1-test:
	python3 scripts/phase1.py phase1_blocking

phase1-replay:
	python3 scripts/phase1.py phase1_replay

phase1-cases:
	python3 scripts/phase1.py phase1_cases
