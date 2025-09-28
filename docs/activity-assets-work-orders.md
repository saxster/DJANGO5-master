# Activity, Assets & Work Orders

_Preamble: Activity is the backbone for jobs, assets, and locations. You’ll touch it for schedules, attendance context, reports, and WOs/PPM._

## Models & Relationships
- Activity models live in `apps/activity/models/` (e.g., `asset_model.py`, `job_model.py`).
- Jobs link People and Assets; Jobneeds define job templates and constraints.

## Interactions
- Scheduler uses these models to create and preview tours/tasks.
- Attendance and Reports query across these relations heavily; keep queries optimized.

## Extending
- Add selective `select_related`/`prefetch_related` in high‑traffic lists.
- For GraphQL, provide dataloaders for common joins; see `apps/api/graphql/dataloaders.py`.
- Index new filtering paths to maintain performance.

## ER Overview
```mermaid
classDiagram
  class People {+id +peoplename}
  class Asset {+id +name +location}
  class Jobneed {+id +name +rules}
  class Job {+id +title +status}
  People <o-- Job : assigned
  Asset <o-- Job : operates_on
  Jobneed <o-- Job : instantiates
```

## Example: Assignment Service
```python
def list_jobs_for_people(people_ids: list[int]):
    return (Job.objects
        .filter(people_id__in=people_ids)
        .select_related('asset','people','jobneed')
        .only('id','title','status','asset__name','people__peoplename'))
```

## Indexing Guidance
- Typical filters: `status`, `asset_id`, `people_id`, `created_at`.
- Add composite indexes when sorting/filtering on multiple fields is common.
- Periodically analyze query plans; adjust indexes to current access patterns.

