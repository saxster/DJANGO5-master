# GraphQL/Graphene-Django Implementation

## Overview
GraphQL serves as the primary API interface for YOUTILITY5, providing a flexible query language for mobile and web clients. The implementation uses Graphene-Django for schema definition and graphql-jwt for authentication.

## Installation
```bash
pip install graphene-django==3.2.3
pip install graphene-gis==0.0.8
pip install django-graphql-jwt==0.4.0
pip install graphql-core==3.2.6
```

## Architecture

### Core Schema Structure
**Location**: `/apps/service/schema.py`

```python
import graphene
import graphql_jwt

class Query(
    TicketQueries,
    QuestionQueries,
    JobQueries,
    TypeAssistQueries,
    WorkPermitQueries,
    PeopleQueries,
    AssetQueries,
    BtQueries,
    graphene.ObjectType,
):
    # Query fields

class Mutation(graphene.ObjectType):
    token_auth = LoginUser.Field()
    logout_user = LogoutUser.Field()
    insert_record = InsertRecord.Field()
    update_task_tour = TaskTourUpdate.Field()
    upload_report = ReportMutation.Field()
    # Other mutations

schema = graphene.Schema(query=RootQuery, mutation=RootMutation)
```

### Configuration in Settings
**Location**: `/intelliwiz_config/settings.py`

```python
GRAPHENE = {
    "ATOMIC_MUTATIONS": True,
    "SCHEMA": "apps.service.schema.schema",
    "MIDDLEWARE": [
        "graphql_jwt.middleware.JSONWebTokenMiddleware",
    ],
}

GRAPHQL_JWT = {
    "JWT_VERIFY_EXPIRATION": True,
    "JWT_EXPIRATION_DELTA": timedelta(minutes=5),
    "JWT_REFRESH_EXPIRATION_DELTA": timedelta(days=7),
    "JWT_ALGORITHM": "HS256",
    "JWT_AUTH_HEADER_PREFIX": "JWT",
}
```

## Query Organization

### Modular Query Structure
Each domain has its own query class in `/apps/service/queries/`:

| Query Class | Domain | File |
|------------|--------|------|
| `TicketQueries` | Helpdesk tickets | `ticket_queries.py` |
| `JobQueries` | Job management | `job_queries.py` |
| `PeopleQueries` | Employee data | `people_queries.py` |
| `AssetQueries` | Asset management | `asset_queries.py` |
| `QuestionQueries` | Survey/Questions | `question_queries.py` |
| `BtQueries` | Business transactions | `bt_queries.py` |
| `TypeAssistQueries` | Type assistance | `typeassist_queries.py` |
| `WorkPermitQueries` | Work permits | `workpermit_queries.py` |

### Query Pattern with Pydantic Validation
```python
from pydantic import ValidationError
from apps.service.pydantic_schemas.people_schema import PeopleModifiedAfterSchema
from graphql import GraphQLError

class PeopleQueries(graphene.ObjectType):
    get_peoplemodifiedafter = graphene.Field(
        SelectOutputType,
        mdtz=graphene.String(required=True),
        ctzoffset=graphene.Int(required=True),
        buid=graphene.Int(required=True),
    )

    @staticmethod
    def resolve_get_peoplemodifiedafter(self, info, mdtz, ctzoffset, buid):
        try:
            # Validate with Pydantic
            filter_data = {
                'mdtz': mdtz,
                'ctzoffset': ctzoffset,
                'buid': buid
            }
            validated = PeopleModifiedAfterSchema(**filter_data)

            # Query database
            data = People.objects.get_people_modified_after(
                mdtz=validated.mdtz,
                siteid=validated.buid
            )

            # Return standardized response
            records, count, msg = utils.get_select_output(data)
            return SelectOutputType(nrows=count, records=records, msg=msg)

        except ValidationError as ve:
            raise GraphQLError(f"Validation failed: {str(ve)}")
```

## Mutation Organization

### Available Mutations
**Location**: `/apps/service/mutations.py`

| Mutation | Purpose | Authentication Required |
|----------|---------|------------------------|
| `LoginUser` | JWT token generation | No |
| `LogoutUser` | Session termination | Yes |
| `InsertRecord` | Generic record creation | Yes |
| `UpdateTaskTour` | Update task/tour data | Yes |
| `ReportMutation` | Upload reports | Yes |
| `UploadAttMutaion` | File attachments | Yes |
| `SyncMutation` | Batch sync operations | Yes |
| `AdhocMutation` | Ad-hoc operations | Yes |
| `InsertJsonMutation` | JSON data insertion | Yes |
| `refresh_token` | JWT token refresh | Yes |

### Mutation Pattern
```python
class InsertRecord(graphene.Mutation):
    class Arguments:
        table_name = graphene.String(required=True)
        data = graphene.JSONString(required=True)

    success = graphene.Boolean()
    message = graphene.String()
    record_id = graphene.Int()

    @login_required
    def mutate(self, info, table_name, data):
        try:
            # Business logic here
            model_class = get_model_by_name(table_name)
            instance = model_class.objects.create(**data)

            return InsertRecord(
                success=True,
                message="Record created successfully",
                record_id=instance.id
            )
        except Exception as e:
            return InsertRecord(
                success=False,
                message=str(e),
                record_id=None
            )
```

## Authentication

### JWT Implementation
```python
# Login mutation
class LoginUser(graphene.Mutation):
    token = graphene.String()
    payload = graphene.Field(GenericScalar)
    refresh_token = graphene.String()

    class Arguments:
        username = graphene.String(required=True)
        password = graphene.String(required=True)

    @staticmethod
    def mutate(root, info, username, password):
        user = authenticate(username=username, password=password)
        if user:
            # Generate tokens
            token = get_token(user)
            refresh_token = create_refresh_token(user)

            return LoginUser(
                token=token,
                payload=get_payload(token),
                refresh_token=refresh_token
            )
        raise GraphQLError("Invalid credentials")
```

### Protected Queries/Mutations
```python
from graphql_jwt.decorators import login_required

class Query(graphene.ObjectType):
    @login_required
    def resolve_viewer(self, info, **kwargs):
        return info.context.user.username
```

## Type Definitions

### Custom Types
**Location**: `/apps/service/types.py`

```python
class SelectOutputType(graphene.ObjectType):
    """Standard response format for queries"""
    nrows = graphene.Int()
    records = graphene.JSONString()
    msg = graphene.String()

class PELogType(DjangoObjectType):
    class Meta:
        model = PeopleEventlog
        fields = "__all__"

class TrackingType(DjangoObjectType):
    class Meta:
        model = Tracking
        fields = "__all__"
```

## Error Handling

### Standardized Error Responses
```python
try:
    # Operation
    pass
except ValidationError as ve:
    log.error("Validation failed", exc_info=True)
    raise GraphQLError(f"Validation Error: {str(ve)}")
except PermissionError as pe:
    log.error("Permission denied", exc_info=True)
    raise GraphQLError(f"Permission Denied: {str(pe)}")
except Exception as e:
    log.error("Unexpected error", exc_info=True)
    raise GraphQLError(f"Internal Error: {str(e)}")
```

## Performance Optimization

### DataLoader Pattern
**Location**: `/apps/api/graphql/dataloaders.py`

```python
from promise import Promise
from promise.dataloader import DataLoader

class UserLoader(DataLoader):
    def batch_load_fn(self, user_ids):
        users = {u.id: u for u in User.objects.filter(id__in=user_ids)}
        return Promise.resolve([users.get(uid) for uid in user_ids])

# Usage in resolver
def resolve_user(self, info):
    return info.context.user_loader.load(self.user_id)
```

### Query Optimization with select_related
```python
def resolve_jobs_with_details(self, info):
    return Job.objects.select_related(
        'assigned_to',
        'created_by',
        'site'
    ).prefetch_related(
        'attachments',
        'comments'
    )
```

## Testing GraphQL

### Query Testing
```python
import json
from graphene_django.utils.testing import GraphQLTestCase

class TestPeopleQueries(GraphQLTestCase):
    GRAPHQL_SCHEMA = "apps.service.schema.schema"

    def test_people_modified_after_query(self):
        query = """
        query {
            getPeoplemodifiedafter(
                mdtz: "2024-01-01T00:00:00",
                ctzoffset: 0,
                buid: 1
            ) {
                nrows
                records
                msg
            }
        }
        """

        response = self.query(query)
        content = json.loads(response.content)

        self.assertResponseNoErrors(response)
        self.assertIn('getPeoplemodifiedafter', content['data'])
```

### Mutation Testing
```python
def test_login_mutation(self):
    mutation = """
    mutation {
        tokenAuth(username: "testuser", password: "testpass") {
            token
            payload
            refreshToken
        }
    }
    """

    response = self.query(mutation)
    content = json.loads(response.content)

    self.assertResponseNoErrors(response)
    self.assertIsNotNone(content['data']['tokenAuth']['token'])
```

## Client Usage Examples

### JavaScript/Fetch
```javascript
const query = `
    query GetPeople($mdtz: String!, $buid: Int!) {
        getPeoplemodifiedafter(mdtz: $mdtz, ctzoffset: 0, buid: $buid) {
            nrows
            records
        }
    }
`;

fetch('/graphql/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': 'JWT ' + token
    },
    body: JSON.stringify({
        query: query,
        variables: {
            mdtz: '2024-01-01T00:00:00',
            buid: 1
        }
    })
})
.then(response => response.json())
.then(data => console.log(data));
```

### Python Client
```python
import requests

url = "http://localhost:8000/graphql/"
headers = {"Authorization": f"JWT {token}"}

query = """
mutation {
    insertRecord(tableName: "Job", data: "{\\"title\\": \\"Test Job\\"}") {
        success
        message
        recordId
    }
}
"""

response = requests.post(url, json={'query': query}, headers=headers)
print(response.json())
```

## GraphQL Endpoint

### URL Configuration
```python
# urls.py
from django.urls import path
from graphene_django.views import GraphQLView
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path("graphql/", csrf_exempt(GraphQLView.as_view(graphiql=True))),
]
```

### GraphiQL Interface
- Development: `http://localhost:8000/graphql/`
- Features: Interactive query builder, schema documentation, query history

## Best Practices

1. **Always validate inputs** with Pydantic schemas
2. **Use DataLoaders** for N+1 query prevention
3. **Implement proper error handling** with GraphQLError
4. **Add @login_required** to protected endpoints
5. **Use select_related/prefetch_related** for query optimization
6. **Return standardized responses** (SelectOutputType)
7. **Log all errors** with appropriate detail levels
8. **Test both success and failure cases**
9. **Document complex queries** with descriptions
10. **Version your schema** for backward compatibility

## Common Issues & Solutions

### Issue: Token Expiration
**Solution**: Implement refresh token rotation
```python
# Client should refresh before expiry
if token_expires_soon():
    new_token = refresh_access_token(refresh_token)
```

### Issue: N+1 Queries
**Solution**: Use DataLoaders or prefetch_related
```python
# Bad
for job in jobs:
    print(job.assigned_to.name)  # N queries

# Good
jobs = Job.objects.select_related('assigned_to')
for job in jobs:
    print(job.assigned_to.name)  # 1 query
```

### Issue: Large Response Payloads
**Solution**: Implement pagination
```python
class PaginatedJobsQuery(graphene.ObjectType):
    jobs = graphene.Field(
        JobPaginationType,
        page=graphene.Int(),
        page_size=graphene.Int()
    )
```

## Related Documentation
- [Pydantic Usage](./pydantic_usage.md) - Input validation
- [JWT Authentication](./jwt_authentication.md) - Token management
- [Manager Pattern](./manager_pattern.md) - Query optimization