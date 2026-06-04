source(file.path("r", "app", "scenario_engine.R"))
contract <- read_dashboard_contract(file.path("r", "app", "data", "dashboard_scenario_contract.csv"))
default_rows <- contract[!duplicated(contract$model_id), c("model_id", "default_england_hpe_count")]
counts <- setNames(default_rows$default_england_hpe_count, default_rows$model_id)
scenario <- calculate_dashboard_scenario(
  contract,
  duration_years = 10.0,
  selected_models = c("A", "B", "C", "D", "E"),
  model_counts = counts,
  uptake = 0.60,
  effectiveness = 0.25,
  implementation_cost_per_approached_hpe_gbp = 0.0
)
stopifnot(nrow(scenario$per_model) == 5)
stopifnot(nrow(scenario$events) == 6)
stopifnot(scenario$metrics$gross_cost_avoided_gbp > 0)
stopifnot(scenario$metrics$qaly_gained > 0)
stopifnot(abs(scenario$metrics$net_budget_impact_gbp - scenario$metrics$gross_cost_avoided_gbp) < 1e-8)
cat("R dashboard scenario tests passed\n")
