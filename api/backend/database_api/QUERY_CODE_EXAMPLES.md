
## Python Client Example

```python
import io, base64
import requests
import pandas as pd
import geopandas as gpd

API   = "https://your-api-gateway-url"
TOKEN = "your-jwt-token"

response = requests.post(
    f"{API}/query",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json={
        "geojson": {"type": "Polygon", "coordinates": [[[...]]]},
        "trait_filters": {
            "trait": ["LMA"],
            "taxa":  ["Picea engelmannii"],
            "collection_date_start": "2018-06-01",
            "collection_date_end":   "2018-08-31",
        },
        "granule_filters": {
            "sensor_name":            ["NEON AIS 1"],
            "acquisition_date_start": "2018-06-01",
            "acquisition_date_end":   "2018-08-31",
        },
        "format": "geoparquet",
        "limit":  100,
    }
)
data = response.json()

print(f"Showing {data['plot_count']} of {data['total_plot_count']} plots")

# API Gateway returns base64-encoded binary — decode before reading
plots    = gpd.read_parquet(io.BytesIO(base64.b64decode(data["plots_parquet"])))
traits   = pd.read_parquet(io.BytesIO(base64.b64decode(data["traits_parquet"])))
granules = pd.read_parquet(io.BytesIO(base64.b64decode(data["granules_parquet"])))

# Explode pixel_ids — one row per pixel
pixels = granules.explode("pixel_ids").rename(columns={"pixel_ids": "pixel_id"})

# Download spectra via extract spectra (existing flow)
spectra = pd.read_parquet("spectra.parquet")  # pixel_id + band_1 ... band_N

# Join spectra to pixels
spectra_pixels = pixels[["granule_id", "sensor_name", "pixel_id"]].merge(
    spectra, on="pixel_id"
)

# Link traits via plot_id
granule_plots = granules.explode("plot_ids").rename(columns={"plot_ids": "plot_id"})
result = spectra_pixels.merge(
    granule_plots[["granule_id", "plot_id"]], on="granule_id"
).merge(
    traits[["plot_id", "sample_name", "trait", "value", "units", "taxa"]],
    on="plot_id"
)
```

**Result shape:** One row per `(pixel, trait measurement)`. Spectra columns repeat for every trait of the same pixel's plot. If a plot has 5 traits and 20 pixels → 100 rows. Each row is one `(spectrum, trait)` observation — ready for trait prediction models.

| `pixel_id` | `granule_id` | `sensor_name` | `band_1` | `...` | `band_N` | `plot_id` | `sample_name` | `trait` | `value` | `units` | `taxa` |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3817 | NIS01_20180621 | NEON AIS 1 | 0.023 | ... | 0.018 | 21 | 020-ER18_Picea | LMA | 412.9 | g/m2 | Picea engelmannii |
| 3817 | NIS01_20180621 | NEON AIS 1 | 0.023 | ... | 0.018 | 21 | 020-ER18_Picea | Chl | 23.1 | µg/cm² | Picea engelmannii |
| 3818 | NIS01_20180621 | NEON AIS 1 | 0.019 | ... | 0.015 | 21 | 020-ER18_Picea | LMA | 412.9 | g/m2 | Picea engelmannii |
| 3818 | NIS01_20180621 | NEON AIS 1 | 0.019 | ... | 0.015 | 21 | 020-ER18_Picea | Chl | 23.1 | µg/cm² | Picea engelmannii |

---

## R Client Example

```r
library(httr2)
library(arrow)
library(sf)
library(dplyr)
library(tidyr)
library(base64enc)

resp <- request("https://your-api-gateway-url/query") |>
  req_auth_bearer_token("your-jwt-token") |>
  req_body_json(list(
    trait_filters = list(
      trait = list("LMA"),
      taxa  = list("Picea engelmannii"),
      collection_date_start = "2018-06-01",
      collection_date_end   = "2018-08-31"
    ),
    granule_filters = list(
      sensor_name           = list("NEON AIS 1"),
      acquisition_date_start = "2018-06-01",
      acquisition_date_end   = "2018-08-31"
    ),
    format = "geoparquet",
    limit  = 100
  )) |>
  req_perform() |>
  resp_body_json()

cat(sprintf("Showing %d of %d plots\n", resp$plot_count, resp$total_plot_count))

# API Gateway returns base64-encoded binary — decode before reading
plots    <- read_sf(rawConnection(base64decode(resp$plots_parquet)))
traits   <- read_parquet(rawConnection(base64decode(resp$traits_parquet)))
granules <- read_parquet(rawConnection(base64decode(resp$granules_parquet)))
spectra  <- read_parquet("spectra.parquet")

result <- granules |>
  unnest(pixel_ids) |>
  rename(pixel_id = pixel_ids) |>
  inner_join(spectra, by = "pixel_id") |>
  unnest(plot_ids) |>
  rename(plot_id = plot_ids) |>
  inner_join(traits, by = "plot_id")
```

