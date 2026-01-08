#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(httr)
  library(jsonlite)
})

# Normalize CIK to standard 10-digit string expected by the SEC endpoints.
to_10_digits <- function(n) {
  s <- trimws(as.character(n))
  if (!grepl("^[0-9]+$", s)) stop(sprintf("Expected only digits, got %s", s))
  if (nchar(s) > 10) stop(sprintf("Number longer than 10 digits: %s", s))
  sprintf("%010d", as.integer(s))
}

# User-Agent is required by SEC; compression keeps payloads small.
headers <- c(
  "User-Agent" = "jo boulement jo@gmx.at",
  "Accept-Encoding" = "gzip, deflate"
)

tickers_url <- "https://www.sec.gov/files/company_tickers.json"

nz_chr <- function(x) {
  if (is.null(x)) "" else as.character(x)
}

# Insert quarter value into the nested years/quarter structure used for outputs.
add_q <- function(obj, year, quarter, value) {
  year_key <- as.character(year)
  if (is.null(obj$years)) obj$years <- list()
  if (is.null(obj$years[[year_key]])) obj$years[[year_key]] <- list()
  obj$years[[year_key]][[quarter]] <- value
  obj
}

# Derive quarterly EPS from cumulative frames, mirroring facts.py logic.
eps_for_year <- function(start_year, eps_json, eps_diluted) {
  frame_check <- paste0("cy", start_year)
  q1_eps <- q2_eps <- q3_eps <- q4_eps <- NULL

  for (entry in eps_diluted) {
    form <- entry$form
    if (is.null(form)) next
    if (is.na(form)) next
    if (!(form %in% c("10-q", "10-k"))) next

    frame <- entry$frame
    fp <- entry$fp
    val <- entry$val
    start <- nz_chr(entry$start)
    end <- nz_chr(entry$end)

    # Prefer explicit frame tags (cyYYYYqX) when present.
    if (!is.null(frame) && !is.na(frame) && frame == paste0(frame_check, "q1")) {
      q1_eps <- val
      eps_json <- add_q(eps_json, start_year, "q1", q1_eps)
    # Fall back to fiscal period (fp) plus date range when frame is missing.
    } else if (is.null(q1_eps) && identical(fp, "q1") &&
               grepl(paste0(start_year, "-01"), start, fixed = TRUE) &&
               grepl(paste0(start_year, "-03"), end, fixed = TRUE)) {
      q1_eps <- val
      eps_json <- add_q(eps_json, start_year, "q1", q1_eps)
    }

    # Q2: pull direct frame first; otherwise infer and subtract Q1 from YTD.
    if (!is.null(frame) && !is.na(frame) && frame == paste0(frame_check, "q2")) {
      q2_eps <- val
      eps_json <- add_q(eps_json, start_year, "q2", q2_eps)
    } else if (is.null(q2_eps) && identical(fp, "q2") &&
               grepl(paste0(start_year, "-01"), start, fixed = TRUE) &&
               grepl(paste0(start_year, "-06"), end, fixed = TRUE) &&
               !is.null(q1_eps)) {
      q2_eps <- round(val - q1_eps, 4)
      eps_json <- add_q(eps_json, start_year, "q2", q2_eps)
    } else if (is.null(q2_eps) && identical(fp, "q2") &&
               grepl(paste0(start_year, "-03"), start, fixed = TRUE) &&
               grepl(paste0(start_year, "-06"), end, fixed = TRUE)) {
      q2_eps <- val
      eps_json <- add_q(eps_json, start_year, "q2", q2_eps)
    } else if (is.null(q2_eps) && identical(fp, "q2") &&
               grepl(paste0(start_year, "-04"), start, fixed = TRUE) &&
               grepl(paste0(start_year, "-06"), end, fixed = TRUE)) {
      q2_eps <- val
      eps_json <- add_q(eps_json, start_year, "q2", q2_eps)
    }

    # Q3: direct frame; otherwise infer and subtract Q1+Q2 from YTD.
    if (!is.null(frame) && !is.na(frame) && frame == paste0(frame_check, "q3")) {
      q3_eps <- val
      eps_json <- add_q(eps_json, start_year, "q3", q3_eps)
    } else if (is.null(q3_eps) && identical(fp, "q3") &&
               grepl(paste0(start_year, "-01"), start, fixed = TRUE) &&
               grepl(paste0(start_year, "-09"), end, fixed = TRUE) &&
               !is.null(q1_eps) && !is.null(q2_eps)) {
      q3_eps <- round(val - (q1_eps + q2_eps), 4)
      eps_json <- add_q(eps_json, start_year, "q3", q3_eps)
    } else if (is.null(q3_eps) && identical(fp, "q3") &&
               grepl(paste0(start_year, "-06"), start, fixed = TRUE) &&
               grepl(paste0(start_year, "-09"), end, fixed = TRUE)) {
      q3_eps <- val
      eps_json <- add_q(eps_json, start_year, "q3", q3_eps)
    } else if (is.null(q3_eps) && identical(fp, "q3") &&
               grepl(paste0(start_year, "-07"), start, fixed = TRUE) &&
               grepl(paste0(start_year, "-09"), end, fixed = TRUE)) {
      q3_eps <- val
      eps_json <- add_q(eps_json, start_year, "q3", q3_eps)
    }

    # Q4: subtract prior quarters from annual total; otherwise accept FY value.
    if (!is.null(frame) && !is.na(frame) && frame == frame_check &&
        !is.null(q1_eps) && !is.null(q2_eps) && !is.null(q3_eps)) {
      q4_eps <- round(val - (q1_eps + q2_eps + q3_eps), 4)
      eps_json <- add_q(eps_json, start_year, "q4", q4_eps)
    } else if (is.null(q4_eps) && identical(fp, "FY") &&
               grepl(paste0(start_year, "-01"), start, fixed = TRUE) &&
               grepl(paste0(start_year, "-12"), end, fixed = TRUE) &&
               !is.null(q1_eps) && !is.null(q2_eps) && !is.null(q3_eps)) {
      q4_eps <- val - (q1_eps + q2_eps + q3_eps)
      eps_json <- add_q(eps_json, start_year, "q4", q4_eps)
    } else if (is.null(q4_eps) && identical(fp, "FY") &&
               grepl(paste0(start_year, "-09"), start, fixed = TRUE) &&
               grepl(paste0(start_year, "-12"), end, fixed = TRUE)) {
      q4_eps <- val
      eps_json <- add_q(eps_json, start_year, "q4", q4_eps)
    } else if (is.null(q4_eps) && identical(fp, "FY") &&
               grepl(paste0(start_year, "-10"), start, fixed = TRUE) &&
               grepl(paste0(start_year, "-12"), end, fixed = TRUE)) {
      q4_eps <- val
      eps_json <- add_q(eps_json, start_year, "q4", q4_eps)
    }
  }

  eps_json
}

# Derive quarterly operating cash flow from cumulative cashflow frames.
cashflow_for_year <- function(start_year, cashflow_json, operating_cashflow) {
  frame_check <- paste0("cy", start_year)
  q1_csh <- q2_csh <- q3_csh <- q4_csh <- NULL

  for (entry in operating_cashflow) {
    frame <- entry$frame
    fp <- entry$fp
    val <- entry$val
    start <- nz_chr(entry$start)
    end <- nz_chr(entry$end)

    # Cashflow frames are cumulative; subtract prior quarters to get discrete values.
    if (!is.null(frame) && !is.na(frame)) {
      if (frame == paste0(frame_check, "q1")) q1_csh <- val
      if (frame == paste0(frame_check, "q2") && !is.null(q1_csh)) q2_csh <- round(val - q1_csh, 4)
      if (frame == paste0(frame_check, "q3") && !is.null(q1_csh) && !is.null(q2_csh)) q3_csh <- round(val - (q1_csh + q2_csh), 4)
      if (frame == frame_check && !is.null(q1_csh) && !is.null(q2_csh) && !is.null(q3_csh)) {
        q4_csh <- round(val - (q1_csh + q2_csh + q3_csh), 4)
      }
    }

    # If frame is missing, infer quarter using fiscal period tags plus dates.
    if (!is.null(fp)) {
      if (identical(fp, "q1") &&
          grepl(paste0(start_year, "-01"), start, fixed = TRUE) &&
          grepl(paste0(start_year, "-03"), end, fixed = TRUE)) {
        q1_csh <- val
      } else if (identical(fp, "q2") &&
                 grepl(paste0(start_year, "-01"), start, fixed = TRUE) &&
                 grepl(paste0(start_year, "-06"), end, fixed = TRUE) &&
                 !is.null(q1_csh)) {
        q2_csh <- round(val - q1_csh, 4)
      } else if (identical(fp, "q3") &&
                 grepl(paste0(start_year, "-01"), start, fixed = TRUE) &&
                 grepl(paste0(start_year, "-09"), end, fixed = TRUE) &&
                 !is.null(q1_csh) && !is.null(q2_csh)) {
        q3_csh <- round(val - (q1_csh + q2_csh), 4)
      } else if (identical(fp, "q4") &&
                 grepl(paste0(start_year, "-01"), start, fixed = TRUE) &&
                 grepl(paste0(start_year, "-12"), end, fixed = TRUE) &&
                 !is.null(q1_csh) && !is.null(q2_csh) && !is.null(q3_csh)) {
        q4_csh <- round(val - (q1_csh + q2_csh + q3_csh), 4)
      }
    }
  }

  if (is.null(q1_csh) || is.null(q2_csh) || is.null(q3_csh) || is.null(q4_csh)) {
    stop("Incomplete cashflow data for year")
  }

  cashflow_json <- add_q(cashflow_json, start_year, "q1", q1_csh)
  cashflow_json <- add_q(cashflow_json, start_year, "q2", q2_csh)
  cashflow_json <- add_q(cashflow_json, start_year, "q3", q3_csh)
  cashflow_json <- add_q(cashflow_json, start_year, "q4", q4_csh)
  cashflow_json
}

# Collect all revenue frames (any GAAP label containing "revenue").
collect_revenue_frames <- function(facts, default_year) {
  all_frame_rev <- character()
  gaap <- facts[["us-gaap"]]
  if (is.null(gaap)) return(all_frame_rev)

  for (name in names(gaap)) {
    if (!grepl("revenue", name, ignore.case = TRUE)) next
    usd_entries <- gaap[[name]]$units$usd
    if (is.null(usd_entries)) next

    for (y in usd_entries) {
      form <- y$form
      if (is.null(form)) next
      if (is.na(form)) next
      if (!(form %in% c("10-q", "10-k"))) next

      frame <- y$frame
      val <- y$val
      # Capture raw frame if present (kept as "val_frame" strings for later dedupe).
      if (!is.null(frame) && !is.na(frame)) {
        all_frame_rev <- c(all_frame_rev, paste0(val, "_", frame))
        next
      }

      fp <- y$fp
      start <- nz_chr(y$start)
      end <- nz_chr(y$end)
      year <- default_year

      # Build synthetic frame labels from fp + dates when frame is absent.
      if (identical(fp, "q1") &&
          grepl(paste0(year, "-01"), start, fixed = TRUE) &&
          grepl(paste0(year, "-03"), end, fixed = TRUE)) {
        all_frame_rev <- c(all_frame_rev, paste0(val, "_", "cy", year, "q1"))
      }
      if (identical(fp, "q2") &&
          grepl(paste0(year, "-03"), start, fixed = TRUE) &&
          grepl(paste0(year, "-06"), end, fixed = TRUE)) {
        all_frame_rev <- c(all_frame_rev, paste0(val, "_", "cy", year, "q2"))
      } else if (identical(fp, "q2") &&
                 grepl(paste0(year, "-04"), start, fixed = TRUE) &&
                 grepl(paste0(year, "-06"), end, fixed = TRUE)) {
        all_frame_rev <- c(all_frame_rev, paste0(val, "_", "cy", year, "q2"))
      }
      if (identical(fp, "q3") &&
          grepl(paste0(year, "-06"), start, fixed = TRUE) &&
          grepl(paste0(year, "-09"), end, fixed = TRUE)) {
        all_frame_rev <- c(all_frame_rev, paste0(val, "_", "cy", year, "q2"))
      } else if (identical(fp, "q3") &&
                 grepl(paste0(year, "-07"), start, fixed = TRUE) &&
                 grepl(paste0(year, "-09"), end, fixed = TRUE)) {
        all_frame_rev <- c(all_frame_rev, paste0(val, "_", "cy", year, "q2"))
      }
    }
  }

  all_frame_rev
}

# Deduplicate revenue by quarter and prefer largest value per frame.
rev_graph <- function(start_year, all_frame_rev, revenue_json) {
  i <- 0
  z <- 0
  rev_qy_test <- character()
  rev_num_test <- character()
  unique_list <- character()
  rev_qy_trailed <- character()
  rev_num_trailed <- numeric()

  # Split "val_frame" strings into parallel lists of values and period labels.
  for (x in all_frame_rev) {
    if (!grepl(paste0("cy", start_year), x, ignore.case = TRUE)) next
    parts <- strsplit(x, "_", fixed = TRUE)[[1]]
    for (y in parts) {
      i <- i + 1
      if ((i %% 2) == 0) {
        rev_qy_test <- c(rev_qy_test, y)
      } else {
        rev_num_test <- c(rev_num_test, y)
      }
    }
  }

  for (item in rev_qy_test) {
    if (!(item %in% unique_list)) unique_list <- c(unique_list, item)
  }

  # Sort period labels chronologically (cyYYYYq1..q4 then cyYYYY).
  period_key <- function(labels) {
    m <- regexec("^cy(\\d{4})(?:q([1-4]))?$", tolower(labels))
    matches <- regmatches(labels, m)
    do.call(rbind, lapply(matches, function(x) {
      if (length(x) == 0) return(c(Inf, Inf))
      year <- as.numeric(x[2])
      q <- x[3]
      rank <- ifelse(is.na(q) || q == "", 5, as.numeric(q))
      c(year, rank)
    }))
  }

  if (length(unique_list)) {
    key <- period_key(unique_list)
    ordering <- order(key[, 1], key[, 2], na.last = TRUE)
    unique_list <- unique_list[ordering]
  }

  # For each period, pick the largest revenue (mirrors Python heuristic).
  for (x in unique_list) {
    list_num <- numeric()
    o <- 0
    for (y in rev_qy_test) {
      if (x == y) {
        list_num <- c(list_num, as.numeric(rev_num_test[o + 1]))
      }
      o <- o + 1
    }
    if (!length(list_num)) next
    largest_rev <- max(list_num)
    if (x %in% c(paste0("cy", start_year, "q1"),
                 paste0("cy", start_year, "q2"),
                 paste0("cy", start_year, "q3"),
                 paste0("cy", start_year))) {
      rev_qy_trailed <- c(rev_qy_trailed, x)
      rev_num_trailed <- c(rev_num_trailed, largest_rev)
    }
  }

  # If annual frame exists, derive Q4 by subtracting first three quarters.
  if (length(rev_qy_trailed) >= 4 && rev_qy_trailed[4] == paste0("cy", start_year)) {
    calc <- sum(rev_num_trailed[1:3])
    end_of_year_rev <- rev_num_trailed[4]
    fourth_q_rev <- end_of_year_rev - calc
    rev_num_trailed <- c(rev_num_trailed[1:3], fourth_q_rev)
  }

  # Write quartered revenue into output structure.
  for (idx in seq_along(rev_qy_trailed)) {
    revenue_json <- add_q(revenue_json, start_year, paste0("q", idx), rev_num_trailed[idx])
    z <- z + 1
  }

  revenue_json
}

failed <- character()

resp <- GET(tickers_url, add_headers(.headers = headers))
stop_for_status(resp)

response_tickers <- content(resp, "text", encoding = "UTF-8")
response_tickers <- tolower(response_tickers)
response_tickers <- fromJSON(response_tickers, simplifyVector = FALSE)

# Iterate every ticker with cached facts, mirroring the Python batch flow.
for (entry in response_tickers) {
  tryCatch({
    current_ticker <- entry$ticker
    path_company <- file.path("output", paste0(current_ticker, "-facts-json"))
    full_path <- file.path(path_company, paste0("full_", current_ticker, ".json"))

    # Facts payload must already be cached on disk by a prior fetch step.
    response <- fromJSON(full_path, simplifyVector = FALSE)
    eps_diluted <- response$facts$`us-gaap`$earningspersharediluted$units$`usd/shares`
    operating_cashflow <- response$facts$`us-gaap`$netcashprovidedbyusedinoperatingactivities$units$usd
    if (is.null(eps_diluted) || is.null(operating_cashflow)) stop("Missing required facts data")

    # Seed output objects.
    eps_json <- list(company = current_ticker, metric = "epsd")
    revenue_json <- list(company = current_ticker, metric = "total revenue")
    cashflow_json <- list(company = current_ticker, metric = "operating cashflow")
    all_frame_rev <- collect_revenue_frames(response$facts, default_year = 2020)

    start_year <- 2020
    repeat {
      # Tolerate gaps by catching per-year errors so other metrics continue.
      tryCatch({
        eps_json <- eps_for_year(start_year, eps_json, eps_diluted)
      }, error = function(e) NULL)

      tryCatch({
        cashflow_json <- cashflow_for_year(start_year, cashflow_json, operating_cashflow)
      }, error = function(e) NULL)

      tryCatch({
        revenue_json <- rev_graph(start_year, all_frame_rev, revenue_json)
      }, error = function(e) NULL)

      start_year <- start_year + 1
      if (start_year > 2025) break
    }

    # Persist derived metrics for downstream scripts (e.g., deltas).
    dir.create(path_company, recursive = TRUE, showWarnings = FALSE)
    write_json(eps_json, file.path(path_company, paste0("epsd_", current_ticker, ".json")), pretty = TRUE, auto_unbox = TRUE)
    write_json(cashflow_json, file.path(path_company, paste0("cash_", current_ticker, ".json")), pretty = TRUE, auto_unbox = TRUE)
    write_json(revenue_json, file.path(path_company, paste0("rev_", current_ticker, ".json")), pretty = TRUE, auto_unbox = TRUE)
    cat("pass\n")
  }, error = function(e) {
    failed <<- c(failed, entry$ticker)
    cat("fail\n")
  })
}

if (length(failed)) {
  message("Failed tickers: ", paste(failed, collapse = ", "))
}
