# Run the standard dashboard cross-language scenarios in R.
source(file.path("r", "app", "scenario_engine.R"))

contract <- read_dashboard_contract(file.path("r", "app", "data", "dashboard_scenario_contract.csv"))
cases <- read.csv(file.path("dashboard", "data", "dashboard_cross_language_cases.csv"), stringsAsFactors = FALSE)
default_rows <- contract[!duplicated(contract$model_id), c("model_id", "default_england_hpe_count")]
defaults <- setNames(default_rows$default_england_hpe_count, default_rows$model_id)

result_rows <- lapply(seq_len(nrow(cases)), function(i) {
  case <- cases[i, ]
  selected_models <- strsplit(case$selected_models, "\\|", fixed = FALSE)[[1]]
  counts <- defaults * case$scale
  result <- calculate_dashboard_scenario(
    contract,
    duration_years = case$duration_years,
    selected_models = selected_models,
    model_counts = counts,
    uptake = case$uptake,
    effectiveness = case$effectiveness,
    implementation_cost_per_approached_hpe_gbp = case$implementation_cost_per_approached_hpe_gbp
  )
  row <- result$metrics
  row$scenario_id <- case$scenario_id
  for (j in seq_len(nrow(result$events))) {
    slug <- names(EVENT_LABELS)[EVENT_LABELS == result$events$event[j]]
    row[[paste0("events_avoided_", slug)]] <- result$events$events_avoided[j]
  }
  row[, c("scenario_id", setdiff(names(row), "scenario_id")), drop = FALSE]
})

result <- do.call(rbind, result_rows)
out <- file.path("outputs_r", "dashboard_crosscheck")
dir.create(out, recursive = TRUE, showWarnings = FALSE)
write.csv(result, file.path(out, "r_dashboard_scenarios.csv"), row.names = FALSE)
print(result)
