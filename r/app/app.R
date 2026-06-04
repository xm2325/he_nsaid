library(shiny)
APP_DIR <- if (file.exists("scenario_engine.R")) "." else file.path("r", "app")
source(file.path(APP_DIR, "scenario_engine.R"))

contract <- read_dashboard_contract(file.path(APP_DIR, "data", "dashboard_scenario_contract.csv"))
model_table <- unique(contract[, c("model_id", "model_label", "default_england_hpe_count")])
model_table <- model_table[order(model_table$model_id), ]
MODEL_CHOICES <- setNames(model_table$model_id, paste0(model_table$model_id, ": ", model_table$model_label))

format_gbp <- function(x) paste0("£", format(round(x), big.mark = ",", scientific = FALSE))
format_num <- function(x, digits = 1) format(round(x, digits), big.mark = ",", scientific = FALSE, nsmall = digits)

ui <- fluidPage(
  tags$head(tags$style(HTML("\
    body { font-family: Arial, sans-serif; }\
    .metric-box { background:#f6f8fa; border:1px solid #d0d7de; border-radius:8px; padding:14px; margin-bottom:12px; }\
    .metric-title { color:#57606a; font-size:14px; }\
    .metric-value { font-size:26px; font-weight:700; }\
  "))),
  titlePanel("MedSID NSAID medicines-safety scenario explorer"),
  p("Dynamic R Shiny version: five validated NSAID model contracts plus a transparent intervention scenario layer."),
  sidebarLayout(
    sidebarPanel(
      checkboxGroupInput("models", "Models included", choices = MODEL_CHOICES, selected = model_table$model_id),
      sliderInput("duration", "HPE exposure duration (years)", min = 0.25, max = 10.0, value = 10.0, step = 0.25),
      sliderInput("uptake", "Intervention uptake", min = 0, max = 1, value = 0.60, step = 0.01),
      sliderInput("effectiveness", "Effectiveness among reached HPEs", min = 0, max = 1, value = 0.25, step = 0.01),
      numericInput("unit_cost", "Implementation cost per approached HPE (£)", value = 0, min = 0, step = 1),
      numericInput("scale", "Population scale relative to England", value = 1, min = 0.0001, step = 0.05),
      helpText("Avoided burden = baseline HPE burden × uptake × effectiveness."),
      downloadButton("download_scenario", "Download scenario CSV")
    ),
    mainPanel(
      fluidRow(
        column(3, div(class = "metric-box", div(class = "metric-title", "Gross NHS cost avoided"), div(class = "metric-value", textOutput("gross_cost", inline = TRUE)))),
        column(3, div(class = "metric-box", div(class = "metric-title", "QALYs gained"), div(class = "metric-value", textOutput("qaly_gained", inline = TRUE)))),
        column(3, div(class = "metric-box", div(class = "metric-title", "Implementation cost"), div(class = "metric-value", textOutput("implementation_cost", inline = TRUE)))),
        column(3, div(class = "metric-box", div(class = "metric-title", "Net budget impact"), div(class = "metric-value", textOutput("net_budget", inline = TRUE))))
      ),
      tabsetPanel(
        tabPanel("Scenario summary",
          fluidRow(
            column(6, h3("Estimated safety events avoided"), plotOutput("events_plot"), tableOutput("events_table")),
            column(6, h3("Exposure-duration curve"), plotOutput("duration_plot"))
          )
        ),
        tabPanel("Model results", tableOutput("model_results")),
        tabPanel("Validation and scope",
          h3("What is recalculated dynamically?"),
          tags$ul(
            tags$li("The R Shiny page reads a versioned dashboard contract generated from validated Python formula engines."),
            tags$li("Exposure duration, selected models, local scale, uptake, effectiveness and implementation cost update reactively."),
            tags$li("GitHub Actions runs standard scenarios in Python and R and fails if outputs differ beyond tolerance."),
            tags$li("The intervention layer is a user-supplied proportional scenario assumption, not an inferred causal effect.")
          )
        )
      )
    )
  )
)

server <- function(input, output, session) {
  model_counts <- reactive({
    setNames(model_table$default_england_hpe_count * input$scale, model_table$model_id)
  })

  scenario <- reactive({
    req(length(input$models) > 0)
    calculate_dashboard_scenario(
      contract,
      duration_years = input$duration,
      selected_models = input$models,
      model_counts = model_counts(),
      uptake = input$uptake,
      effectiveness = input$effectiveness,
      implementation_cost_per_approached_hpe_gbp = input$unit_cost
    )
  })

  curve <- reactive({
    req(length(input$models) > 0)
    scenario_curve_r(
      contract,
      selected_models = input$models,
      model_counts = model_counts(),
      uptake = input$uptake,
      effectiveness = input$effectiveness,
      implementation_cost_per_approached_hpe_gbp = input$unit_cost
    )
  })

  output$gross_cost <- renderText(format_gbp(scenario()$metrics$gross_cost_avoided_gbp))
  output$qaly_gained <- renderText(format_num(scenario()$metrics$qaly_gained, 1))
  output$implementation_cost <- renderText(format_gbp(scenario()$metrics$implementation_cost_gbp))
  output$net_budget <- renderText(format_gbp(scenario()$metrics$net_budget_impact_gbp))

  output$events_plot <- renderPlot({
    events <- scenario()$events
    events <- events[abs(events$events_avoided) > 1e-10, ]
    par(mar = c(5, 13, 2, 1))
    barplot(rev(events$events_avoided), names.arg = rev(events$event), horiz = TRUE, las = 1,
            xlab = "Estimated events avoided", col = "#1f77b4", border = NA)
  })

  output$events_table <- renderTable({ scenario()$events }, digits = 2)

  output$duration_plot <- renderPlot({
    data <- curve()
    par(mfrow = c(2, 1), mar = c(4, 5, 2, 1))
    plot(data$duration_years, data$gross_cost_avoided_gbp / 1e6, type = "o", pch = 16,
         xlab = "", ylab = "Gross cost avoided (£m)", col = "#1f77b4")
    grid()
    plot(data$duration_years, data$qaly_gained, type = "o", pch = 16,
         xlab = "Duration of exposure to hazardous prescribing (years)", ylab = "QALYs gained", col = "#1f77b4")
    grid()
  })

  output$model_results <- renderTable({
    rows <- scenario()$per_model
    rows[, c("model_id", "model_label", "scenario_hpe_count", "incremental_discounted_cost_per_person_gbp",
             "incremental_discounted_qaly_per_person", "baseline_incremental_cost_gbp",
             "baseline_incremental_qaly", "gross_cost_avoided_gbp", "qaly_gained")]
  }, digits = 3)

  output$download_scenario <- downloadHandler(
    filename = function() "medsid_r_shiny_scenario.csv",
    content = function(file) write.csv(scenario()$per_model, file, row.names = FALSE)
  )
}

shinyApp(ui, server)
