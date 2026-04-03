# job_status Lambda

Handles all job status queries for the VSWIR Plants API. Three routes are served by a single Lambda function.

---

## Routes

### `GET /isofit_jobs`

Lists recent isofit parent jobs, newest first.

**Auth:** `superadmins` Cognito group required.

**Query params:**
| Param | Default | Max | Description |
|---|---|---|---|
| `limit` | `5` | `50` | Number of jobs to return |

**Response:**
```json
{
  "jobs": [
    {
      "job_id": "uuid",
      "status": "complete",
      "submitted_by": "username",
      "created_at": "2026-04-02T12:00:00+00:00"
    }
  ]
}
```

**Status values** written by the pixel selection Lambda and kept up to date by the summary route:

| Status | Meaning |
|---|---|
| `submitted` | Parent job created, child Batch jobs submitted |
| `running` | At least one child job is running (container started) |
| `inverting` | At least one child job is actively running isofit inversion |
| `complete` | All child jobs finished successfully |
| `failed` | All child jobs failed |
| `partial` | Mix of complete and failed child jobs |
| `unknown` | Cannot be determined from child statuses |

---

### `GET /job_status/{job_id}?mode=summary`

Aggregates the status of all child Batch jobs belonging to an isofit parent job. Also reconciles any in-flight jobs against the AWS Batch API to catch silent failures (OOM kills, spot interruptions, host termination), writes corrections back to DynamoDB, and updates the parent job status.

**Auth:** `superadmins` Cognito group required.

**Path params:**
| Param | Description |
|---|---|
| `job_id` | The parent job ID returned by `POST /run_isofit` |

**Response:**
```json
{
  "parent_job_id": "uuid",
  "parent_status": "running",
  "total_batches": 42,
  "statuses": {
    "complete": 38,
    "running": 3,
    "failed": 1
  },
  "total_pixels_processed": 760,
  "total_pixels_remaining": 60,
  "restart_required": false,
  "restarted_jobs": [],
  "failed_jobs_pixel_ids": [101, 102, 103]
}
```

**Reconciliation flow:**

```
DynamoDB child records
        │
        ▼
Aggregate statuses, pixel counts, restarted jobs
        │
        ▼
Collect job IDs with status = running or inverting
        │
        ▼
batch.describe_jobs() in chunks of 100
        │
        ├── FAILED   → write status=failed  to DynamoDB child record
        ├── SUCCEEDED → write status=complete to DynamoDB child record
        └── other    → no change (job genuinely still running)
        │
        ▼
Fix up aggregation counters with corrections
        │
        ▼
Derive parent status from child status counts
        │
        ▼
Write parent status back to DynamoDB parent record
        │
        ▼
Return aggregated response
```

**Parent status derivation logic:**

| Child statuses present | Derived parent status |
|---|---|
| only `complete` | `complete` |
| only `failed` | `failed` |
| `complete` + `failed` only | `partial` |
| any `running` or `inverting` | `running` |
| any `submitted` | `submitted` |
| anything else | `unknown` |

---

### `GET /job_status/{job_id}`

Single job lookup. Used by the spectra extraction flow (not isofit).

**Auth:** Cognito JWT required (any authenticated user).

**Path params:**
| Param | Description |
|---|---|
| `job_id` | The job ID for a single extraction job |

**Response:**
```json
{
  "job_id": "uuid",
  "status": "complete",
  "rows_processed": 500,
  "presigned_url": "https://..."
}
```

Returns `404` if the job is not found.

---

## Code structure

```
job_status/app/
  main.py              # thin router — maps routes to handlers
  auth.py              # JWT claim extraction, admin group check, respond/handle_error helpers
  routes/
    isofit.py          # list_jobs(), job_summary() — isofit-specific routes
    single.py          # job_status() — spectra extraction route
  services/
    dynamo.py          # all DynamoDB reads and writes
    batch.py           # AWS Batch reconciliation via describe_jobs()
```

---

## IAM permissions required

| Permission | Reason |
|---|---|
| `dynamodb:GetItem` | Single job lookup |
| `dynamodb:Query` | List parent jobs and child job aggregation (GSI queries) |
| `dynamodb:UpdateItem` | Write Batch corrections and parent status back to DynamoDB |
| `batch:DescribeJobs` | Reconcile in-flight jobs against real Batch status |
| `logs:*` | CloudWatch logging |
