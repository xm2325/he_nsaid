# Shared scenario layer for the dynamic R Shiny application.
#
# The versioned dashboard contract is exported from validated Python formula
# engines. This R layer performs the same transparent proportional avoided-
# burden scenario calculation used by the Python Streamlit application.

EVENT_COLUMNS <- c(
  deaths = "excess_event_deaths_per_person",
  symptomatic_ulcers = "excess_event_symptomatic_ulcers_per_person",
  serious_gastrointestinal_events = "excess_event_serious_gastrointestinal_events_per_person",
  strokes = "excess_event_strokes_per_person",
  acute_exacerbations_of_heart_failure = "excess_event_acute_exacerbations_of_heart_failure_per_person",
  acute_kidney_injuries = "excess_event_acute_kidney_injuries_per_person"
)

EVENT_LABELS <- c(
  deaths = "Deaths",
  symptomatic_ulcers = "Symptomatic ulcers",
  serious_gastrointestinal_events = "Serious gastrointestinal events",
  strokes = "Strokes",
  acute_exacerbations_of_heart_failure = "Acute exacerbations of heart failure",
  acute_kidney_injuries = "Acute kidney injuries"
)

read_dashboard_contract <- function(path = file.path("data", "dashboard_scenario_contract.csv")) {
  read.csv(path, stringsAsFactors = FALSE, check.names = FALSE)
}

select_duration_rows <- function(contract, duration_years, selected_models) {
  available <- sort(unique(contract$duration_years))
  nearest <- available[which.min(abs(available - duration_years))]
  if (abs(nearest - duration_years) > 1e-8) {
    stop(sprintf("Duration %.3f is not available in dashboard contract", duration_years))
  }
  rows <- contract[abs(contract$duration_years - nearest) < 1e-8 & contract$model_id %in% selected_models, , drop = FALSE]
  if (nrow(rows) == 0) stop("At least one model must be selected")
  rows
}

calculate_dashboard_scenario <- function(
  contract,
  duration_years,
  selected_models,
  model_counts = NULL,
  uptake = 0.60,
  effectiveness = 0.25,
  implementation_cost_per_approached_hpe_gbp = 0.0
) {
  if (uptake < 0 || uptake > 1) stop("uptake must be in [0, 1]")
  if (effectiveness < 0 || effectiveness > 1) stop("effectiveness must be in [0, 1]")
  rows <- select_duration_rows(contract, duration_years, selected_models)
  if (is.null(model_counts)) {
    model_counts <- setNames(rows$default_england_hpe_count, rows$model_id)
  }
  rows$scenario_hpe_count <- as.numeric(model_counts[rows$model_id])
  if (any(is.na(rows$scenario_hpe_count))) stop("Missing model count for one or more selected models")
  rows$reducible_fraction <- uptake * effectiveness
  rows$baseline_incremental_cost_gbp <- rows$scenario_hpe_count * rows$incremental_discounted_cost_per_person_gbp
  rows$baseline_incremental_qaly <- rows$scenario_hpe_count * rows$incremental_discounted_qaly_per_person
  rows$gross_cost_avoided_gbp <- rows$baseline_incremental_cost_gbp * rows$reducible_fraction
  rows$qaly_gained <- -rows$baseline_incremental_qaly * rows$reducible_fraction

  event_rows <- lapply(names(EVENT_COLUMNS), function(slug) {
    column <- EVENT_COLUMNS[[slug]]
    baseline <- sum(rows$scenario_hpe_count * rows[[column]])
    data.frame(
      event = EVENT_LABELS[[slug]],
      baseline_excess_events = baseline,
      events_avoided = baseline * uptake * effectiveness,
      stringsAsFactors = FALSE
    )
  })
  events <- do.call(rbind, event_rows)
  approached_hpe <- sum(rows$scenario_hpe_count) * uptake
  implementation_cost <- approached_hpe * implementation_cost_per_approached_hpe_gbp
  gross_saving <- sum(rows$gross_cost_avoided_gbp)
  metrics <- data.frame(
    duration_years = duration_years,
    selected_model_count = nrow(rows),
    total_hpe_count = sum(rows$scenario_hpe_count),
    uptake = uptake,
    effectiveness = effectiveness,
    reducible_fraction = uptake * effectiveness,
    baseline_incremental_cost_gbp = sum(rows$baseline_incremental_cost_gbp),
    baseline_incremental_qaly = sum(rows$baseline_incremental_qaly),
    gross_cost_avoided_gbp = gross_saving,
    qaly_gained = sum(rows$qaly_gained),
    implementation_cost_gbp = implementation_cost,
    net_budget_impact_gbp = gross_saving - implementation_cost,
    stringsAsFactors = FALSE
  )
  list(metrics = metrics, per_model = rows, events = events)
}

scenario_curve_r <- function(
  contract,
  selected_models,
  model_counts,
  uptake,
  effectiveness,
  implementation_cost_per_approached_hpe_gbp
) {
  rows <- lapply(sort(unique(contract$duration_years)), function(duration) {
    calculate_dashboard_scenario(
      contract,
      duration_years = duration,
      selected_models = selected_models,
      model_counts = model_counts,
      uptake = uptake,
      effectiveness = effectiveness,
      implementation_cost_per_approached_hpe_gbp = implementation_cost_per_approached_hpe_gbp
    )$metrics
  })
  do.call(rbind, rows)
}
