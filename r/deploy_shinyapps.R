# Manual deployment helper for shinyapps.io.
# Set SHINYAPPS_ACCOUNT, SHINYAPPS_TOKEN and SHINYAPPS_SECRET first.
if (!requireNamespace("rsconnect", quietly = TRUE)) install.packages("rsconnect", repos = "https://cloud.r-project.org")
rsconnect::setAccountInfo(
  name = Sys.getenv("SHINYAPPS_ACCOUNT"),
  token = Sys.getenv("SHINYAPPS_TOKEN"),
  secret = Sys.getenv("SHINYAPPS_SECRET")
)
rsconnect::deployApp(appDir = "r/app", forceUpdate = TRUE)
