# Native R contract runner for the NSAID state-transition models.
#
# The Python formula engines export versioned transition and reward contracts.
# This file performs trace propagation, reward accumulation, PSA aggregation,
# regression validation and Figure 2 plotting using base R only.

`%||%` <- function(x, y) if (is.null(x)) y else x

read_contracts <- function(data_dir = file.path("r", "data")) {
  list(
    transitions = read.csv(file.path(data_dir, "transition_contract.csv"), stringsAsFactors = FALSE, check.names = FALSE),
    initial = read.csv(file.path(data_dir, "initial_state_contract.csv"), stringsAsFactors = FALSE, check.names = FALSE),
    rewards = read.csv(file.path(data_dir, "reward_contract.csv"), stringsAsFactors = FALSE, check.names = FALSE),
    summary_reference = read.csv(file.path(data_dir, "summary_reference.csv"), stringsAsFactors = FALSE, check.names = FALSE),
    trace_reference = read.csv(file.path(data_dir, "trace_reference.csv"), stringsAsFactors = FALSE, check.names = FALSE),
    psa_model = read.csv(file.path(data_dir, "psa_model_level_england.csv"), stringsAsFactors = FALSE, check.names = FALSE),
    psa_total_reference = read.csv(file.path(data_dir, "psa_total_reference.csv"), stringsAsFactors = FALSE, check.names = FALSE)
  )
}

model_states <- function(contracts, model_id) {
  rows <- contracts$initial[contracts$initial$model_id == model_id, c("state_index", "state")]
  rows <- rows[order(rows$state_index), ]
  unique(rows$state)
}

initial_vector <- function(contracts, model_id, arm) {
  rows <- contracts$initial[contracts$initial$model_id == model_id & contracts$initial$arm == arm, ]
  rows <- rows[order(rows$state_index), ]
  as.numeric(rows$probability)
}

transition_matrix_for_cycle <- function(contracts, model_id, arm, cycle, n_states) {
  rows <- contracts$transitions[
    contracts$transitions$model_id == model_id &
      contracts$transitions$arm == arm &
      contracts$transitions$cycle == cycle,
    , drop = FALSE
  ]
  mat <- matrix(0, nrow = n_states, ncol = n_states)
  for (i in seq_len(nrow(rows))) {
    mat[rows$from_index[i], rows$to_index[i]] <- rows$probability[i]
  }
  mat
}

run_trace <- function(contracts, model_id, arm) {
  states <- model_states(contracts, model_id)
  n_states <- length(states)
  reward_rows <- contracts$rewards[contracts$rewards$model_id == model_id, ]
  n_cycles <- max(reward_rows$cycle) + 1
  trace <- matrix(0, nrow = n_cycles + 1, ncol = n_states)
  trace[1, ] <- initial_vector(contracts, model_id, arm)
  for (cycle in seq_len(n_cycles)) {
    mat <- transition_matrix_for_cycle(contracts, model_id, arm, cycle, n_states)
    trace[cycle + 1, ] <- as.numeric(trace[cycle, , drop = FALSE] %*% mat)
  }
  colnames(trace) <- states
  data.frame(
    cycle = 0:n_cycles,
    trace,
    check.names = FALSE
  )
}

summarise_trace <- function(contracts, model_id, trace) {
  rewards <- contracts$rewards[contracts$rewards$model_id == model_id, ]
  rewards <- rewards[order(rewards$cycle, rewards$state_index), ]
  n_cycles <- max(rewards$cycle) + 1
  n_states <- max(rewards$state_index)
  totals <- c(
    total_ly = 0,
    discounted_ly = 0,
    total_qaly = 0,
    discounted_qaly = 0,
    total_cost = 0,
    discounted_cost = 0
  )
  state_cols <- colnames(trace)[-(1)]
  trace_matrix <- as.matrix(trace[, state_cols, drop = FALSE])

  for (cycle0 in 0:(n_cycles - 1)) {
    rows <- rewards[rewards$cycle == cycle0, ]
    rows <- rows[order(rows$state_index), ]
    start <- as.numeric(trace_matrix[cycle0 + 1, ])
    end <- as.numeric(trace_matrix[cycle0 + 2, ])
    occupancy <- 0.5 * (start + end)
    ly <- sum(start * rows$ly_weight)
    qaly <- sum(occupancy * rows$qaly_weight)
    cost <- sum(occupancy * rows$cost_weight)
    totals["total_ly"] <- totals["total_ly"] + ly
    totals["discounted_ly"] <- totals["discounted_ly"] + ly / rows$ly_discount_factor[1]
    totals["total_qaly"] <- totals["total_qaly"] + qaly
    totals["discounted_qaly"] <- totals["discounted_qaly"] + qaly / rows$qaly_discount_factor[1]
    totals["total_cost"] <- totals["total_cost"] + cost
    totals["discounted_cost"] <- totals["discounted_cost"] + cost / rows$cost_discount_factor[1]
  }
  totals
}

validate_trace <- function(contracts, model_id, arm, trace) {
  ref <- contracts$trace_reference[
    contracts$trace_reference$model_id == model_id & contracts$trace_reference$arm == arm,
    , drop = FALSE
  ]
  ref <- ref[order(ref$cycle, ref$state_index), ]
  state_cols <- colnames(trace)[-1]
  calc <- as.numeric(t(as.matrix(trace[, state_cols, drop = FALSE])))
  # t(matrix) gives state-major order; the reference uses cycle-major order.
  calc <- as.numeric(as.vector(t(as.matrix(trace[, state_cols, drop = FALSE]))))
  ref_cycle_major <- as.numeric(ref$occupancy)
  max(abs(calc - ref_cycle_major))
}

validate_summary <- function(contracts, model_id, arm, summary_values) {
  ref <- contracts$summary_reference[
    contracts$summary_reference$model_id == model_id & contracts$summary_reference$arm == arm,
    , drop = FALSE
  ]
  rows <- lapply(seq_len(nrow(ref)), function(i) {
    metric <- ref$metric[i]
    calc <- unname(summary_values[metric])
    data.frame(
      model_id = model_id,
      arm = arm,
      metric = metric,
      r_value = calc,
      python_reference = ref$reference_value[i],
      absolute_error = calc - ref$reference_value[i],
      stringsAsFactors = FALSE
    )
  })
  do.call(rbind, rows)
}

run_all_deterministic <- function(contracts, output_dir = file.path("outputs_r", "deterministic")) {
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
  models <- c("A", "B", "C", "D", "E")
  arms <- c("HPE", "No HPE")
  summary_rows <- list()
  trace_rows <- list()
  k <- 1
  j <- 1
  for (model_id in models) {
    for (arm in arms) {
      trace <- run_trace(contracts, model_id, arm)
      safe_arm <- gsub(" ", "_", tolower(arm))
      write.csv(trace, file.path(output_dir, sprintf("model_%s_trace_%s.csv", model_id, safe_arm)), row.names = FALSE)
      summary_values <- summarise_trace(contracts, model_id, trace)
      summary_rows[[k]] <- validate_summary(contracts, model_id, arm, summary_values)
      k <- k + 1
      trace_rows[[j]] <- data.frame(
        model_id = model_id,
        arm = arm,
        max_absolute_trace_error = validate_trace(contracts, model_id, arm, trace),
        stringsAsFactors = FALSE
      )
      j <- j + 1
    }
  }
  summary_validation <- do.call(rbind, summary_rows)
  trace_validation <- do.call(rbind, trace_rows)
  write.csv(summary_validation, file.path(output_dir, "r_vs_python_summary_validation.csv"), row.names = FALSE)
  write.csv(trace_validation, file.path(output_dir, "r_vs_python_trace_validation.csv"), row.names = FALSE)
  list(summary_validation = summary_validation, trace_validation = trace_validation)
}

aggregate_psa <- function(contracts) {
  aggregate(
    cbind(england_incremental_cost_gbp, england_incremental_qaly) ~ iteration,
    data = contracts$psa_model,
    FUN = sum
  )
}

plot_psa_figure2 <- function(total, output_file) {
  png(output_file, width = 1600, height = 1250, res = 220)
  old <- par(mar = c(5, 6, 2, 1), las = 1)
  on.exit({par(old); dev.off()}, add = TRUE)
  x <- total$england_incremental_qaly / 1000
  y <- total$england_incremental_cost_gbp / 1e6
  plot(
    x, y,
    pch = 16, cex = 0.38,
    col = rgb(31 / 255, 119 / 255, 180 / 255, alpha = 0.28),
    xlim = c(-12, 2), ylim = c(-40, 120),
    xlab = "QALY impact of hazardous prescribing (000s)",
    ylab = "Cost impact of hazardous prescribing (£ millions)",
    axes = FALSE
  )
  axis(1, at = seq(-12, 2, by = 2))
  axis(2, at = c(-40, 0, 40, 80, 120))
  abline(h = c(-40, 0, 40, 80, 120), col = "grey75", lwd = 1)
  abline(h = 0, v = 0, col = "black", lwd = 1)
  points(mean(x), mean(y), pch = 23, bg = "#f6b21a", col = "#203040", cex = 1.2)
  box(bty = "l")
}

run_psa_reaggregation <- function(contracts, output_dir = file.path("outputs_r", "psa")) {
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
  total <- aggregate_psa(contracts)
  ref <- contracts$psa_total_reference
  merged <- merge(total, ref, by = "iteration", suffixes = c("_r", "_python"))
  merged$cost_abs_error <- merged$england_incremental_cost_gbp - merged$incremental_cost_gbp
  merged$qaly_abs_error <- merged$england_incremental_qaly - merged$incremental_qaly
  write.csv(total, file.path(output_dir, "figure2_r_psa_total.csv"), row.names = FALSE)
  write.csv(merged, file.path(output_dir, "figure2_r_vs_python_validation.csv"), row.names = FALSE)
  plot_psa_figure2(total, file.path(output_dir, "figure2_r_psa_reaggregated.png"))
  data.frame(
    n_iterations = nrow(total),
    mean_incremental_cost_gbp = mean(total$england_incremental_cost_gbp),
    mean_incremental_qaly = mean(total$england_incremental_qaly),
    probability_additional_cost = mean(total$england_incremental_cost_gbp > 0),
    probability_negative_qaly = mean(total$england_incremental_qaly < 0),
    max_abs_cost_difference_vs_python = max(abs(merged$cost_abs_error)),
    max_abs_qaly_difference_vs_python = max(abs(merged$qaly_abs_error))
  )
}
