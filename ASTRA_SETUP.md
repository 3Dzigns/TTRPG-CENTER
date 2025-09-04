# AstraDB Setup Guide

To enable real database loading instead of simulation mode, follow these steps:

## 1. Install AstraDB Python Client

```bash
pip install astrapy
```

## 2. Configure Database Credentials

Edit `env/dev/config/.env` and fill in your AstraDB credentials:

```env
# Database Configuration
ASTRA_DB_API_ENDPOINT=https://your-database-id-region.apps.astra.datastax.com
ASTRA_DB_APPLICATION_TOKEN=AstraCS:your-application-token-here
ASTRA_DB_ID=your-database-id
ASTRA_DB_KEYSPACE=default_keyspace
ASTRA_DB_REGION=us-east-2
```

## 3. Get Your AstraDB Credentials

### From AstraDB Console:
1. Go to [astra.datastax.com](https://astra.datastax.com)
2. Select your database
3. Go to **Connect** tab
4. Copy the following:
   - **API Endpoint**: The base URL for your database
   - **Application Token**: Generate or copy existing token
   - **Database ID**: Found in the database overview

### Example Values:
```env
ASTRA_DB_API_ENDPOINT=https://12345678-1234-1234-1234-123456789abc-us-east-2.apps.astra.datastax.com
ASTRA_DB_APPLICATION_TOKEN=AstraCS:AbCdEfGhIjKlMnOpQrStUvWxYz:1234567890abcdef
ASTRA_DB_ID=12345678-1234-1234-1234-123456789abc
```

## 4. Enable Real Database Mode

Once configured, uncomment the AstraDB client initialization in `src_common/astra_loader.py`:

```python
# Uncomment these lines:
from astrapy import Database
self.client = Database(
    api_endpoint=self.db_config['ASTRA_DB_API_ENDPOINT'],
    token=self.db_config['ASTRA_DB_APPLICATION_TOKEN']
)
```

## 5. Create Collection

The `ttrpg_chunks_dev` collection will be created automatically when you first load data, or you can pre-create it:

```python
python -c "
from src_common.astra_loader import AstraLoader
loader = AstraLoader('dev')
stats = loader.get_collection_stats()
print(f'Collection status: {stats}')
"
```

## 6. Load Data

Once configured, re-run the loading command:

```bash
python src_common/astra_loader.py "path/to/chunks.json" --env dev --empty-first
```

## Troubleshooting

### "Simulation Mode" Message
This means credentials are not configured. Check:
- `.env` file exists with correct values
- No extra spaces or quotes around values
- Database ID and token are valid

### Connection Errors
- Verify API endpoint URL is correct
- Check that application token has proper permissions
- Ensure database is active (not hibernated)

### Collection Not Found
- Collections are created automatically on first insert
- Or create manually via AstraDB console

## Security Notes

- Never commit `.env` files to git
- Use environment-specific tokens (dev/test/prod)
- Rotate tokens regularly
- Limit token permissions to minimum required

## Current Status

The Phase 1 pipeline is complete and functional. The chunks have been processed through:
- ✅ Pass A: PDF parsing with FR1 enhancements (562 chunks)
- ✅ Pass B: Content enrichment (1,053 enriched chunks)
- ✅ Pass C: Graph compilation ready
- ⚠️ **Database Loading: In simulation mode** (needs credentials)

Once AstraDB is configured, all 1,053 enriched chunks will be loaded to the `ttrpg_chunks_dev` collection.