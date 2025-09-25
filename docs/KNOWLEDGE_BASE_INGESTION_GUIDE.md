# Knowledge Base Document Ingestion Guide

This guide shows you how to ingest PDF documents and other files from your KnowledgeBase directory into the AI system for intelligent search and RAG (Retrieval Augmented Generation).

## 📂 Your KnowledgeBase Structure Detected

```
/home/jarvis/DJANGO5/Data/KnowledgeBase/
├── Facility Management/
│   ├── ADA385500.pdf
│   └── Facilities Management Handbook.pdf
└── Fire/
    ├── Fire-fighting Guidance Notes_e-Feb15.pdf
    └── MRT-06 COVERPAGE-merged.pdf
```

## 🛠 Prerequisites

First, install the required PDF processing library:

```bash
# Activate your environment
source django5-env/bin/activate

# Install PDF processing library
pip install PyPDF2

# Optional: For Word documents (.doc, .docx)
pip install python-docx
```

## 🚀 Document Ingestion Commands

### Step 1: Test with Small Sample
```bash
# Test with first 2 documents
python3 manage.py ingest_documents --limit=2

# Test specific category only
python3 manage.py ingest_documents --category="Fire" --limit=2
```

### Step 2: Ingest All Documents
```bash
# Ingest all documents from KnowledgeBase
python3 manage.py ingest_documents

# Ingest with custom chunk size for large PDFs
python3 manage.py ingest_documents --chunk-size=1500 --overlap=150
```

### Step 3: Category-Specific Ingestion
```bash
# Ingest only Facility Management documents
python3 manage.py ingest_documents --category="Facility Management"

# Ingest only Fire documents
python3 manage.py ingest_documents --category="Fire"
```

## 📊 What Gets Processed

### Supported File Types:
- **PDF**: `.pdf` files (using PyPDF2)
- **Text**: `.txt` files  
- **Word**: `.doc`, `.docx` files (with python-docx)
- **Markdown**: `.md` files

### Document Processing:
- **Text Extraction**: Extracts all text content from each document
- **Chunking**: Large documents split into 1000-character chunks with 100-character overlap
- **Page Tracking**: PDF pages are labeled (e.g., "[Page 1]", "[Page 2]")
- **Category Organization**: Documents organized by folder structure

## 🏗 Data Architecture Created

```
KnowledgeBase Directory → Semantic Indexes → Smart Search
         ↓                    ↓                ↓
Facility Management/    → kb_facility_management → FM procedures search
Fire/                  → kb_fire                → Fire safety search  
```

### Semantic Indexes Created:
- **kb_facility_management**: For all Facility Management documents
- **kb_fire**: For all Fire-related documents
- Additional indexes for any other categories you add

### IndexedDocument Structure:
```python
{
    'title': 'Facilities Management Handbook.pdf (Facility Management)',
    'content': '[Page 1]\nFacility Management Overview...',
    'metadata': {
        'file_path': '/home/jarvis/DJANGO5/Data/KnowledgeBase/Facility Management/Facilities Management Handbook.pdf',
        'category': 'Facility Management',
        'file_size': 2048576,
        'chunk_index': 0,
        'total_chunks': 5,
        'data_source': 'document_import'
    }
}
```

## 🔍 Expected Search Results

After ingestion, you can search for:

### Facility Management Queries:
- `"facility maintenance procedures"`
- `"building management guidelines"`
- `"ADA compliance requirements"`
- `"space management"`

### Fire Safety Queries:
- `"fire fighting procedures"`
- `"emergency evacuation"`
- `"fire safety equipment"`
- `"fire prevention guidelines"`

### Cross-Category Queries:
- `"emergency procedures"` → Finds relevant content in both categories
- `"maintenance requirements"` → Finds related content across documents
- `"safety protocols"` → Searches all safety-related content

## 📋 Command Options

### Basic Options:
```bash
--path            # Custom KnowledgeBase path (default: /home/jarvis/DJANGO5/Data/KnowledgeBase)
--category        # Process only specific category (e.g., "Fire")
--file-types      # File extensions to process (default: pdf,txt,doc,docx,md)
--limit          # Limit number of documents to process
--clear          # Clear existing documents before ingesting
```

### Advanced Options:
```bash
--chunk-size     # Text chunk size for large documents (default: 1000)
--overlap       # Overlap between chunks (default: 100)
```

### Example Commands:
```bash
# Custom path with specific file types
python3 manage.py ingest_documents --path=/custom/path --file-types=pdf,txt

# Large document processing
python3 manage.py ingest_documents --chunk-size=2000 --overlap=200

# Clear and reindex
python3 manage.py ingest_documents --clear --category="Fire"
```

## ✅ Success Indicators

You'll know it worked when you see:
```
🚀 Starting Document Ingestion...
KnowledgeBase Path: /home/jarvis/DJANGO5/Data/KnowledgeBase
Processing file types: pdf, txt, doc, docx, md
✓ Found documents in categories: {'Facility Management', 'Fire'}
✓ Created index: kb_facility_management (Facility Management)
✓ Created index: kb_fire (Fire)
Found 4 documents to process

Processing: ADA385500.pdf (Facility Management)
Processing: Facilities Management Handbook.pdf (Facility Management)
Processing: Fire-fighting Guidance Notes_e-Feb15.pdf (Fire)
Processing: MRT-06 COVERPAGE-merged.pdf (Fire)
✓ Processed 4 documents

✅ Document Ingestion Complete!

📊 DOCUMENT INGESTION SUMMARY:
  Total Documents Indexed: 12  # (4 files split into chunks)
  Facility Management: 8 documents
  Fire: 4 documents

🎯 READY TO SEARCH KNOWLEDGE BASE:
  1. Smart Search: http://127.0.0.1:8003/ai/search/search/
  2. Knowledge Base: http://127.0.0.1:8003/ai/search/knowledge/
  3. Analytics: http://127.0.0.1:8003/ai/search/analytics/

💡 TRY THESE SEARCHES:
  - 'Facility Management procedures' or 'Facility Management guidelines'
  - 'Fire procedures' or 'Fire guidelines'
  - 'fire safety' or 'facility management'
  - 'emergency procedures' or 'maintenance guidelines'
```

## 🔧 Troubleshooting

### Common Issues:

1. **PyPDF2 Not Installed**:
   ```bash
   pip install PyPDF2
   ```

2. **Permission Denied**: Ensure Django has read access to KnowledgeBase files

3. **Large PDF Processing**: Use smaller chunk sizes:
   ```bash
   python3 manage.py ingest_documents --chunk-size=500
   ```

4. **Memory Issues**: Process categories separately:
   ```bash
   python3 manage.py ingest_documents --category="Fire" --limit=5
   ```

## 🚀 Advanced Features

### RAG (Retrieval Augmented Generation):
Once documents are indexed, you can:
- Ask questions about facility management procedures
- Get intelligent answers from fire safety documents
- Cross-reference information across all knowledge base documents

### Knowledge Base Integration:
Your documents will be available in:
- **Smart Search**: Find specific procedures or guidelines
- **Knowledge Base RAG**: Ask natural language questions
- **Analytics**: Monitor which knowledge is most accessed

## 📈 Performance Tips

1. **Start Small**: Test with `--limit=2` first
2. **Category by Category**: Process one category at a time for large collections
3. **Optimal Chunk Size**: Use 1000-1500 characters for most documents
4. **Monitor Processing**: Watch for any PDF extraction errors

Your knowledge base documents are now ready to be ingested into the AI system for intelligent search and question-answering! 🎯