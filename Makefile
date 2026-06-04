.PHONY: python-workflow export-r-contracts export-dashboard-contract validate-r-contracts validate-dashboard-contract python-dashboard-scenarios python-tests r-workflow r-tests r-dashboard-tests r-dashboard-scenarios compare-dashboard-outputs ci-python ci-r ci-dashboards run-streamlit

python-workflow:
	python scripts/run_all.py

export-r-contracts:
	python scripts/export_r_contracts.py

export-dashboard-contract:
	python scripts/export_dashboard_contract.py

validate-r-contracts:
	python scripts/validate_r_contracts.py

validate-dashboard-contract:
	python scripts/validate_dashboard_contract.py

python-dashboard-scenarios:
	python scripts/run_dashboard_scenarios.py

python-tests:
	python -m pytest -q

r-workflow:
	Rscript r/scripts/run_all.R

r-tests:
	Rscript r/tests/test_contract_runner.R

r-dashboard-tests:
	Rscript r/tests/test_dashboard_scenario.R

r-dashboard-scenarios:
	Rscript r/scripts/run_dashboard_scenarios.R

compare-dashboard-outputs:
	python scripts/compare_dashboard_outputs.py

run-streamlit:
	streamlit run dashboard/streamlit_app.py

ci-python: python-workflow export-r-contracts export-dashboard-contract validate-r-contracts validate-dashboard-contract python-dashboard-scenarios python-tests

ci-r: export-r-contracts export-dashboard-contract r-workflow r-tests r-dashboard-tests

ci-dashboards: export-dashboard-contract validate-dashboard-contract python-dashboard-scenarios r-dashboard-scenarios compare-dashboard-outputs
