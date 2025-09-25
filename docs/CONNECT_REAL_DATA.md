# Connect AI System to Real YOUTILITY5 Data

This guide shows you how to connect the AI system to your actual tickets, assets, and reports data instead of using test data.

## What's Been Created

### 1. Real Data Indexing Command
- **File**: `apps/txtai_engine/management/commands/index_real_data.py`
- **Purpose**: Indexes your actual YOUTILITY5 data into the AI system
- **Models Supported**: 
  - Tickets (`y_helpdesk.Ticket`)
  - Assets (`activity.Asset`) 
  - Reports (`reports.ReportHistory`)

### 2. Updated Content Extraction
- **File**: `apps/txtai_engine/views.py` (lines 793-803)
- **Purpose**: Properly extracts content from real YOUTILITY5 model fields
- **Features**: Extracts meaningful titles and searchable content

## How to Use

### Step 1: Index Your Real Data

Choose one of these options:

#### Index All Data Types (Recommended)
```bash
python manage.py index_real_data --model=all --limit=1000
```

#### Index Specific Data Types
```bash
# Index only tickets
python manage.py index_real_data --model=tickets --limit=500

# Index only assets  
python manage.py index_real_data --model=assets --limit=300

# Index only reports
python manage.py index_real_data --model=reports --limit=200
```

#### Filter by Client (Optional)
```bash
# Index data for specific client only
python manage.py index_real_data --model=all --client-id=1 --limit=1000
```

#### Clear and Reindex
```bash
# Clear existing indexed data and reindex
python manage.py index_real_data --model=all --clear --limit=1000
```

### Step 2: Test the Integration

After indexing, visit these URLs to test with real data:

1. **Smart Search**: http://127.0.0.1:8003/ai/search/search/
   - Search for ticket numbers, asset codes, report names
   - Try queries like "maintenance pump", "high priority ticket", "monthly report"

2. **Analytics Dashboard**: http://127.0.0.1:8003/ai/search/analytics/
   - View search statistics for real data
   - Monitor popular queries from your actual content

3. **Bulk Indexing Interface**: http://127.0.0.1:8003/ai/search/indexing/
   - Index additional data through the web interface
   - Now shows real YOUTILITY5 models instead of test models

## What Gets Indexed

### Tickets (`y_helpdesk.Ticket`)
- **Content**: Ticket number, description, priority, status, category, assigned person, location, asset, comments, events
- **Metadata**: All ticket fields for filtering and display
- **Search Examples**: "pump malfunction", "high priority maintenance", "electrical issue"

### Assets (`activity.Asset`)  
- **Content**: Asset code, name, running status, type, category, brand, location, capacity, specifications
- **Metadata**: All asset fields including JSON data from asset_json field
- **Search Examples**: "critical pump", "electrical equipment", "maintenance required"

### Reports (`reports.ReportHistory`)
- **Content**: Report name, export type, user details, email information, parameters
- **Metadata**: All report fields including JSON parameters
- **Search Examples**: "monthly report", "task summary", "attendance report"

## Data Flow Architecture

```
Real YOUTILITY5 Data → AI Indexing → Vector Storage → Semantic Search
     ↓                    ↓              ↓              ↓
   Tickets           Extract Text     Embeddings    Smart Results
   Assets           + Metadata        + Similarity   + Context  
   Reports          + Relationships   + Caching     + Analytics
```

## Advanced Usage

### Monitor Indexing Progress
The command provides real-time progress updates:
```
🚀 Starting Real Data Indexing...
Creating semantic indexes for real data...
✓ Created ticket index

Indexing tickets...
Found 1,247 tickets to index
✓ Indexed 50 tickets
✓ Indexed 100 tickets
...
✓ Successfully indexed 1,247 tickets
```

### Check What's Indexed
```python
# In Django shell
from apps.txtai_engine.models import IndexedDocument, SemanticIndex
from django.contrib.contenttypes.models import ContentType

# Check indexed counts
from apps.y_helpdesk.models import Ticket
ticket_ct = ContentType.objects.get_for_model(Ticket)
print(f"Tickets indexed: {IndexedDocument.objects.filter(content_type=ticket_ct).count()}")

# View sample indexed content
doc = IndexedDocument.objects.filter(content_type=ticket_ct).first()
print(f"Title: {doc.title}")
print(f"Content: {doc.content[:200]}...")
```

### Customize Content Extraction
Edit the extraction functions in `index_real_data.py`:
- `_extract_ticket_content()` - Customize ticket content extraction
- `_extract_asset_content()` - Customize asset content extraction  
- `_extract_report_content()` - Customize report content extraction

## Troubleshooting

### Common Issues

1. **Import Errors**: If models can't be imported, check your Django app structure
2. **Permission Issues**: Ensure the database user has read access to all tables
3. **Memory Issues**: Use smaller `--limit` values for large datasets
4. **Slow Indexing**: Increase `chunk_size` in the iterator for better performance

### Performance Tips

1. **Start Small**: Begin with `--limit=100` to test the process
2. **Index by Client**: Use `--client-id` to process one client at a time
3. **Monitor Memory**: Watch memory usage during large indexing operations
4. **Use Off-Peak Hours**: Run indexing during low-traffic periods

## Next Steps

Once your real data is indexed, you can:

1. **Set up Automated Indexing**: Create scheduled tasks to keep the index updated
2. **Configure Real-Time Updates**: Modify model save methods to update the index automatically
3. **Build Custom Knowledge Bases**: Create specialized RAG systems for different content types
4. **Implement Smart Routing**: Use semantic analysis for ticket assignment
5. **Add Predictive Analytics**: Build maintenance prediction using asset data

## Migration from Test Data

If you want to completely replace test data:

```bash
# Clear all AI data and reindex with real data only
python manage.py index_real_data --clear --model=all --limit=5000

# Then run this to remove any remaining test entries
python manage.py shell -c "
from apps.txtai_engine.models import IndexedDocument
IndexedDocument.objects.filter(metadata__is_test_data=True).delete()
"
```

Your AI system is now connected to real YOUTILITY5 data! 🎉