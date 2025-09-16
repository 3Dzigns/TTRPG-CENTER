# Dictionary MongoDB Operations Guide

## Overview

FR-015 MongoDB Dictionary Integration provides a high-performance, resilient dictionary management system with circuit breaker protection and automatic fallback capabilities.

## Quick Reference

### Connection Status Monitoring
- **Admin UI**: Dictionary page shows real-time MongoDB connection status
- **Health Check**: Green badge = healthy, Yellow = degraded, Red = unavailable
- **Circuit Breaker**: Automatically handles failures with 30-second recovery periods

### Performance Metrics
- **Search Target**: ≤1.5s for 10k+ records
- **Typical Performance**: 50-800ms depending on query complexity
- **Index Coverage**: 15+ specialized indexes for optimal query performance

## Operational Procedures

### Daily Monitoring
1. Check dictionary page for MongoDB connection status
2. Review search performance in admin logs
3. Verify circuit breaker is in "Closed" (healthy) state

### Troubleshooting MongoDB Issues

#### Connection Problems
```bash
# Verify MongoDB is running
docker ps | grep mongo

# Check connection from application
curl http://localhost:8000/admin/dictionary/health
```

**Symptoms**: Red connection badge, "Circuit breaker open" messages
**Resolution**:
- Verify MONGO_URI environment variable
- Check MongoDB container status
- Wait 30s for automatic recovery if temporary

#### Performance Issues
```bash
# Check query performance in MongoDB
use ttrpg_dev
db.dictionary.explain("executionStats").find({"term_normalized": /search/})
```

**Symptoms**: Search takes >1.5s, timeout errors
**Resolution**:
- Verify indexes exist: `db.dictionary.getIndexes()`
- Check MongoDB resource usage
- Consider index optimization for specific query patterns

#### Circuit Breaker Reset
If circuit breaker is stuck open:
1. Go to Admin UI → Dictionary → Settings
2. Click "Reset Circuit Breaker" button
3. Monitor connection status for recovery

### Configuration Management

#### Environment Variables
```bash
# Required for MongoDB connectivity
MONGO_URI=mongodb://localhost:27017/ttrpg_dev
APP_ENV=dev

# Optional performance tuning
MONGO_POOL_SIZE=10
MONGO_TIMEOUT_MS=5000
```

#### Database Schema
- **Database Name**: `ttrpg_{environment}`
- **Collection**: `dictionary`
- **Key Indexes**: term_normalized, category, text search
- **Document Structure**: Enhanced with metadata and performance fields

### Maintenance Tasks

#### Weekly
- Review MongoDB slow query log
- Check index usage statistics
- Monitor circuit breaker metrics

#### Monthly
- Evaluate index performance and optimization opportunities
- Review connection pool settings
- Update performance baselines

### Emergency Procedures

#### MongoDB Completely Unavailable
1. System automatically falls back to file-based storage
2. Limited functionality available (basic search only)
3. Admin UI shows fallback status
4. Operations continue with degraded performance

#### Data Corruption or Loss
1. MongoDB service provides backup/restore mechanisms
2. File-based fallback maintains operational continuity
3. Dictionary exports available via Admin UI
4. Contact system administrator for backup restoration

### Performance Baselines

#### Normal Operating Ranges
- **Exact term lookup**: 10-50ms
- **Prefix search**: 50-200ms
- **Full-text search**: 200-800ms
- **Category filtering**: 25-100ms

#### Alert Thresholds
- **WARNING**: Search >1.0s consistently
- **CRITICAL**: Search >1.5s or connection failures >3 in 30s
- **EMERGENCY**: Circuit breaker open for >5 minutes

## Advanced Operations

### Manual Index Management
```javascript
// Connect to MongoDB
use ttrpg_dev

// Check current indexes
db.dictionary.getIndexes()

// Rebuild indexes if needed
db.dictionary.reIndex()

// Check index usage statistics
db.dictionary.aggregate([{$indexStats: {}}])
```

### Performance Analysis
```javascript
// Find slow queries
db.dictionary.find().explain("executionStats")

// Check collection statistics
db.dictionary.stats()

// Monitor real-time operations
db.currentOp()
```

### Data Export/Import for Maintenance
```bash
# Export dictionary data
curl -X GET "http://localhost:8000/admin/dictionary/export?format=json" > backup.json

# Import after maintenance
curl -X POST "http://localhost:8000/admin/dictionary/import" -H "Content-Type: application/json" -d @backup.json
```

## Contact Information

- **System Issues**: Check application logs in `env/{env}/logs/`
- **MongoDB Issues**: Review MongoDB container logs
- **Performance Problems**: Enable debug logging in admin settings
- **Emergency**: File-based fallback provides basic functionality

## Related Documentation

- [FR-015 Complete Implementation Details](../features/FR-015.md)
- [MongoDB Service Architecture](../design/mongodb-architecture.md)
- [Circuit Breaker Pattern Documentation](../patterns/circuit-breaker.md)