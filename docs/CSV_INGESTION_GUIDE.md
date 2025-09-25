# CSV Data Ingestion Guide

This guide shows you how to ingest your CSV data from `/home/jarvis/DJANGO5/Data` into the AI system for semantic search.

## 📂 Data Files Detected

I found these CSV files in your data directory:
- **ticket_data.csv** - Contains tickets with descriptions, priorities, status, etc.
- **asset.csv** - Contains assets with codes, names, running status, etc.

## 🚀 How to Ingest Your CSV Data

### Step 1: Activate Your Environment
First, make sure Django environment is activated:
```bash
# Activate your virtual environment if using one
source venv/bin/activate

# Or if using conda
conda activate your_env_name
```

### Step 2: Test with Small Sample
Start with a small sample to test:
```bash
python manage.py ingest_csv_data --source=all --limit=10
```

### Step 3: Ingest All Data
Once tested, ingest your full dataset:
```bash
# Ingest everything
python manage.py ingest_csv_data --source=all

# Or ingest specific types with limits
python manage.py ingest_csv_data --source=tickets --limit=1000
python manage.py ingest_csv_data --source=assets --limit=500
```

### Step 4: Clear and Reindex (if needed)
```bash
# Clear existing CSV data and reindex
python manage.py ingest_csv_data --source=all --clear --limit=1000
```

## 📊 What Gets Ingested

### From ticket_data.csv:
- **Ticket Numbers**: MUM0011432#22, MUM0011432#23, etc.
- **Descriptions**: "Site Crisis Alert", "Security Breach", etc.
- **Priorities**: HIGH, MEDIUM, LOW
- **Status**: NEW, OPEN, RESOLVED, etc.
- **Metadata**: All IDs, timestamps, assignment info

### From asset.csv:
- **Asset Codes**: KAVBLCP1, TTMTRLGCP2, GBDNRCHCP4, etc.
- **Asset Names**: "0418 - Shutter", "DG Set", "Fascia Light", etc.
- **Identifiers**: CHECKPOINT, ASSET
- **Running Status**: WORKING, MAINTENANCE, STANDBY
- **Metadata**: All technical specifications, locations, relationships

## 🔍 Expected Results

After ingestion, you'll be able to search for:

### Ticket Searches:
- "Security Breach" → Will find tickets about security incidents
- "Site Crisis Alert" → Will find emergency tickets
- "HIGH priority" → Will find urgent tickets
- "MUM0011432" → Will find tickets with that number pattern

### Asset Searches:
- "DG Set" → Will find diesel generator assets
- "Fascia Light" → Will find lighting equipment
- "Shutter" → Will find shutter-related assets
- "WORKING status" → Will find operational equipment
- "CHECKPOINT" → Will find checkpoint assets

## 🎯 Data Structure Created

The system creates two separate semantic indexes:

```
csv_tickets (SemanticIndex)
├── IndexedDocument #1: "Ticket MUM0011432#22: Site Crisis Alert..."
├── IndexedDocument #2: "Ticket MUM0011432#23: Site Crisis Alert..."
└── ...

csv_assets (SemanticIndex)  
├── IndexedDocument #1: "Asset KAVBLCP1: 0418 - Shutter"
├── IndexedDocument #2: "Asset TTMTRLGCP2: 1937 - Shutter"
└── ...
```

Each `IndexedDocument` contains:
- **title**: Human-readable title
- **content**: Searchable text content
- **metadata**: All original CSV fields for filtering
- **embedding_vector**: AI-generated similarity vectors
- **data_source**: "csv_import" (to distinguish from other data)

## 🔄 Data Flow

```
CSV Files → Parse & Extract → Create IndexedDocuments → Generate Embeddings → Enable Search
    ↓           ↓                    ↓                      ↓               ↓
ticket_data.csv  Extract text     Store in DB         txtai vectors    Smart Results
asset.csv       + metadata       + relationships     + similarity     + Context
```

## 📈 Command Options

### --source Options:
- `all`: Ingest both tickets and assets
- `tickets`: Ingest only ticket_data.csv
- `assets`: Ingest only asset.csv

### --limit Options:
- `--limit=100`: Process only first 100 records per file
- No limit: Process all records

### --clear Option:
- `--clear`: Remove existing CSV-imported data before ingesting

### --data-path Option:
- `--data-path=/custom/path`: Use different directory (default: /home/jarvis/DJANGO5/Data)

## ✅ Verification Steps

After ingestion, check the results:

### 1. Check Django Admin
Visit: http://127.0.0.1:8003/admin/txtai_engine/indexeddocument/
- Filter by semantic_index: "csv_tickets" or "csv_assets"
- Verify records are created

### 2. Test Search Interface
Visit: http://127.0.0.1:8003/ai/search/search/
- Try searching for "Security Breach"
- Try searching for "DG Set"
- Try searching for "Shutter"

### 3. Check Analytics
Visit: http://127.0.0.1:8003/ai/search/analytics/
- Verify document counts
- Check search statistics

### 4. Django Shell Verification
```python
python manage.py shell

# Check ingested counts
from apps.txtai_engine.models import IndexedDocument, SemanticIndex

ticket_index = SemanticIndex.objects.get(name='csv_tickets')
asset_index = SemanticIndex.objects.get(name='csv_assets')

print(f"Tickets indexed: {IndexedDocument.objects.filter(semantic_index=ticket_index).count()}")
print(f"Assets indexed: {IndexedDocument.objects.filter(semantic_index=asset_index).count()}")

# View sample content
sample_ticket = IndexedDocument.objects.filter(semantic_index=ticket_index).first()
if sample_ticket:
    print(f"Sample ticket: {sample_ticket.title}")
    print(f"Content preview: {sample_ticket.content[:200]}...")
    print(f"Metadata keys: {list(sample_ticket.metadata.keys())}")
```

## 🚨 Troubleshooting

### Common Issues:

1. **File Not Found**: Check that CSV files exist in `/home/jarvis/DJANGO5/Data`
2. **Permission Denied**: Ensure Django has read access to CSV files
3. **Memory Issues**: Use `--limit` for large files
4. **Encoding Issues**: CSV files should be UTF-8 encoded

### Performance Tips:

1. **Start Small**: Always test with `--limit=10` first
2. **Monitor Progress**: The command shows real-time progress
3. **Check Logs**: Django logs will show detailed error messages
4. **Batch Processing**: Process files separately if having memory issues

## 🎉 Success Indicators

You'll know it worked when you see:
```
🚀 Starting CSV Data Ingestion...
Data Path: /home/jarvis/DJANGO5/Data
Ensuring semantic indexes for CSV data...
✓ Created CSV ticket index
✓ Created CSV asset index

Ingesting tickets from: /home/jarvis/DJANGO5/Data/ticket_data.csv
Found 306 tickets in CSV
✓ Processed 50 tickets
✓ Processed 100 tickets
...
✓ Successfully ingested 298 tickets, skipped 8

Ingesting assets from: /home/jarvis/DJANGO5/Data/asset.csv  
Found 851 assets in CSV
✓ Processed 50 assets
✓ Processed 100 assets
...
✓ Successfully ingested 851 assets, skipped 0

✅ CSV Data Ingestion Complete!

📊 CSV INGESTION SUMMARY:
  CSV Tickets Indexed: 298
  CSV Assets Indexed: 851
  Total CSV Documents: 1149

🎯 READY TO SEARCH CSV DATA:
  1. Smart Search: http://127.0.0.1:8003/ai/search/search/
  2. Knowledge Base: http://127.0.0.1:8003/ai/search/knowledge/
  3. Analytics: http://127.0.0.1:8003/ai/search/analytics/

💡 TRY THESE SEARCHES:
  - 'Security Breach' (from ticket descriptions)
  - 'DG Set' (from asset names)  
  - 'Fascia Light' (from asset descriptions)
  - 'HIGH priority' (from ticket priorities)
  - 'Shutter' (common in both tickets and assets)
```

Your CSV data is now fully integrated into the AI search system! 🎯