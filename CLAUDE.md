# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Vana PII Anonymization Compute Job** that processes query results through a comprehensive privacy-preserving pipeline. It's designed to run in Trusted Execution Environments (TEEs) as part of Vana's privacy-first data processing architecture, automatically detecting and anonymizing personally identifiable information (PII) before outputting results.

**Key Capabilities:**
- **Advanced PII Detection**: Uses Microsoft Presidio with custom recognizers for 71% anonymization rate
- **Memory-Efficient Processing**: Handles large datasets (10GB+) through streaming architecture  
- **Comprehensive Entity Coverage**: Detects 8 PII entity types including person names, emails, credit cards, addresses, SSNs
- **Privacy-Preserving**: Ensures sensitive data never leaves the TEE in raw form
- **Production Ready**: Successfully anonymizes 20/20 credit cards, 78 locations, and preserves user ID integrity

## Development Commands

### Building and Running
```bash
# Build Docker image
./scripts/image-build.sh

# Run in development mode (uses local SQLite)
./scripts/image-run.sh

# Export Docker image for submission
./scripts/image-export.sh
```

### Test Data Setup
```bash
# Generate dummy data for local testing
sqlite3 ./input/query_results.db < dummy_data.sql
```

## Architecture

The codebase follows a streaming ETL pattern with PII anonymization capabilities:

- **src/worker.py**: Main entry point that orchestrates the workflow
- **src/container_params.py**: Handles configuration and parameter parsing
- **src/query_engine_client.py**: API client for interacting with Vana Query Engine
- **src/presidio_config.py**: Configuration system for PII detection and anonymization
- **src/sqlite_stream_processor.py**: Memory-efficient streaming SQLite processor
- **src/pii_anonymization_pipeline.py**: PII anonymization pipeline using Microsoft Presidio

### Data Flow
1. **Query Execution**: 
   - Production: Executes signed queries against Vana Query Engine
   - Development: Reads from local SQLite database at `/mnt/input/query_results.db`
2. **PII Anonymization Pipeline** (Core Processing):
   - **Streaming Analysis**: Processes database tables in memory-efficient 1000-row batches
   - **Entity Detection**: Uses Microsoft Presidio + custom recognizers to identify PII entities
     - Person names (confidence: 0.7) → Custom masking: `John Smith` → `Jo** Sm***`
     - Emails (confidence: 0.8) → Custom masking: `user@example.com` → `us***@e***.com`  
     - Credit cards (confidence: 0.7) → Mask: `4532-1234-5678-9012` → `4532-12************`
     - Addresses (confidence: 0.6) → Custom masking: `123 Main St` → `1** M*** St`
     - SSNs (confidence: 0.9) → Complete redaction
   - **Smart Preservation**: Excludes user IDs (u001, u002, etc.) from person name detection
   - **Custom Recognizers**: Enhanced regex patterns for dash-format credit cards and full addresses
3. **Privacy-Preserving Output**: 
   - Writes anonymized database to `/mnt/output/query_results.db`
   - Generates detailed anonymization report with statistics and performance metrics

### Key Environment Variables
- `DEV_MODE`: Set to "1" for local development (uses local SQLite)
- `QUERY`: Base64-encoded query payload (production mode)
- `INPUT_DIR`: Input directory path (default: /mnt/input)
- `OUTPUT_DIR`: Output directory path (default: /mnt/output)
- `PRESIDIO_CONFIG_PATH`: Path to Presidio configuration file (default: /app/config/presidio_config.json)

## PII Anonymization System

### Overview
The compute job now includes a comprehensive PII (Personally Identifiable Information) anonymization system using Microsoft Presidio. This system:

- **Streams large datasets** (10GB+) without loading everything into memory
- **Configurable PII detection** for various entity types (names, emails, phone numbers, etc.)
- **Multiple anonymization strategies** (replace, mask, redact, hash, encrypt)
- **Preserves database schema** while anonymizing sensitive data
- **Generates detailed reports** on anonymization operations

### Supported PII Entity Types
The system can detect and anonymize the following PII entities:

- **PERSON**: Names and personal identifiers
- **EMAIL_ADDRESS**: Email addresses
- **PHONE_NUMBER**: Phone numbers (various formats)
- **US_SSN**: Social Security Numbers
- **CREDIT_CARD**: Credit card numbers
- **LOCATION**: Addresses and geographic locations
- **DATE_TIME**: Dates and timestamps
- **IP_ADDRESS**: IP addresses
- **URL**: Web URLs and links
- **ORG**: Organization names
- **MONEY**: Monetary amounts
- **IBAN_CODE**: Bank account information

### Anonymization Strategies
Each PII entity type can be configured with different anonymization strategies:

1. **Replace**: Replace with placeholder text (e.g., `<PERSON>`)
2. **Mask**: Replace characters with asterisks (e.g., `***-**-1234`)
3. **Redact**: Remove the PII completely
4. **Hash**: Replace with SHA256/SHA512 hash
5. **Encrypt**: Encrypt using AES encryption (reversible)

### Configuration

#### Presidio Configuration File
The system uses a JSON configuration file located at `config/presidio_config.json`:

```json
{
  "enabled": true,
  "entities": {
    "person": {
      "entity_type": "PERSON",
      "enabled": true,
      "confidence_threshold": 0.6,
      "anonymization_strategy": "replace",
      "anonymization_params": {"new_value": "<PERSON>"}
    },
    "email": {
      "entity_type": "EMAIL_ADDRESS",
      "enabled": true,
      "confidence_threshold": 0.8,
      "anonymization_strategy": "replace",
      "anonymization_params": {"new_value": "<EMAIL>"}
    }
  },
  "batch_processing": {
    "batch_size": 1000,
    "max_memory_mb": 512,
    "enable_parallel_processing": true
  }
}
```

#### Customizing PII Detection
To customize PII detection and anonymization:

1. **Enable/Disable entity types**: Set `"enabled": false` for unwanted entities
2. **Adjust confidence thresholds**: Higher values = more strict detection
3. **Change anonymization strategies**: Choose from replace, mask, redact, hash, encrypt
4. **Configure anonymization parameters**: Customize replacement text, masking patterns, etc.
5. **Add custom deny lists**: Specify exact terms to detect as PII
6. **Configure batch processing**: Adjust batch size and memory limits for performance

### Performance Optimization

#### Memory-Efficient Streaming
- Processes databases in configurable batches (default: 1000 rows)
- Memory usage bounded regardless of database size
- Supports parallel processing for improved performance

#### Batch Processing Configuration
```json
{
  "batch_processing": {
    "batch_size": 1000,           // Rows per batch
    "max_memory_mb": 512,         // Memory limit
    "enable_parallel_processing": true,  // Enable parallel table processing
    "num_workers": 4              // Number of worker threads
  }
}
```

### Output and Reporting

#### Anonymized Database
- **Location**: `/mnt/output/query_results.db`
- **Format**: Same schema as input database
- **Content**: All detected PII anonymized according to configuration

#### Anonymization Report
- **Location**: `/mnt/output/anonymization_report.json`
- **Content**: Detailed statistics on anonymization process
- **Includes**: Entity counts, processing time, performance metrics

**Recent Production Performance** (20 rows, 200 values processed):
```json
{
  "processing_stats": {
    "total_rows": 20,
    "processed_rows": 20,
    "anonymized_rows": 20,
    "processing_time": 2.01,
    "rows_per_second": 9.97,
    "anonymization_rate": 71.0
  },
  "anonymization_stats": {
    "total_values_anonymized": 142,
    "entities_found": {
      "EMAIL_ADDRESS": 40,
      "URL": 70,
      "PERSON": 52,
      "PHONE_NUMBER": 42,
      "LOCATION": 78,
      "US_SSN": 22,
      "CREDIT_CARD": 20,
      "IP_ADDRESS": 2
    }
  }
}
```

## Important Constraints

1. **Docker Required**: All development must be done using Docker containers
2. **AMD64 Architecture**: Must build for AMD64 (use `--platform linux/amd64` if on ARM)
3. **Directory Structure**: Input/output directories are mounted at specific paths
4. **Memory Considerations**: PII anonymization can be memory-intensive for large datasets
5. **NLP Model Requirements**: Requires spaCy models for PII detection (automatically downloaded)

## Common Development Tasks

### Modifying PII Anonymization
1. **Update PII detection rules**: Edit `config/presidio_config.json`
2. **Add new entity types**: Add to the `entities` section in configuration
3. **Customize anonymization strategies**: Modify `anonymization_strategy` and `anonymization_params`
4. **Test configuration changes**: Use `./scripts/image-run.sh` with DEV_MODE=1

### Testing PII Anonymization
1. **Add test data with PII**: Update `dummy_data.sql` with sample PII data
2. **Run locally**: `./scripts/image-run.sh` with DEV_MODE=1
3. **Check anonymization report**: Review `/mnt/output/anonymization_report.json`
4. **Verify anonymized data**: Inspect output database for properly anonymized PII

### Performance Tuning
1. **Adjust batch size**: Modify `batch_processing.batch_size` in configuration
2. **Configure memory limits**: Set `batch_processing.max_memory_mb`
3. **Enable parallel processing**: Set `batch_processing.enable_parallel_processing: true`
4. **Monitor performance**: Check processing rates in anonymization report

### General Development Workflow
1. Update logic in `src/worker.py` for data processing
2. Modify PII anonymization configuration as needed
3. Test locally using `./scripts/image-run.sh` with DEV_MODE=1
4. Build and export image using provided scripts
5. Submit through Vana app for DLP approval

## Query Results Schema

The input SQLite database contains a `results` table with query results. The exact schema depends on the query being executed.

## Vana Ecosystem Context

### Overview
Vana is a decentralized platform that enables user-owned AI and privacy-preserving data access through a sophisticated data infrastructure. Key components include:

- **Data Liquidity Pools (DLPs)**: Decentralized data cooperatives that aggregate, refine, and monetize data while preserving privacy
- **Trusted Execution Environments (TEEs)**: Secure compute environments where data processing occurs without exposing raw data
- **Query Engine**: Manages data access permissions and payments for querying refined data (contract: 0xd25Eb66EA2452cf3238A2eC6C1FD1B7F5B320490)
- **Compute Engine**: Orchestrates compute job execution across TEE pools (contract: 0xb2BFe33FA420c45F1Cf1287542ad81ae935447bd)

### Compute Jobs in Vana

Compute jobs are containerized workloads that run in TEEs and can:
- Query and transform permissioned datasets
- Execute SQL queries against encrypted data via the Query Engine
- Process data while maintaining privacy guarantees
- Produce artifacts (results) without exposing raw data

#### Compute Job Workflow
1. **Registration**: Register compute instruction via `ComputeInstructionRegistry`
2. **Submission**: Submit job to `ComputeEngine` with parameters (timeout, GPU requirements, instruction ID)
3. **Execution**: Job runs in assigned TEE pool (ephemeral, persistent, or dedicated)
4. **Query Processing**: Job submits queries to Query Engine which validates permissions
5. **Results**: Artifacts produced and made available for download

#### TEE Pool Types
- **Ephemeral**: Short-lived jobs (up to 5 minutes), optimized for queries
- **Persistent**: Long-running jobs (up to 2 hours), supports CPU and GPU variants
- **Dedicated**: Custom resource allocation for exclusive use

### Query Engine Integration

The Query Engine is central to data access in Vana:
- **Permission Management**: DataDAO owners grant granular access (dataset/table/column level)
- **Payment Processing**: Handles $VANA payments for data queries
- **Revenue Distribution**: 80% to DataDAO, 20% to Vana network
- **Integration**: Compute jobs interact with Query Engine to execute SQL queries on encrypted datasets

### Security and Privacy
- All data processing occurs within TEEs
- Raw data is never exposed to compute jobs or query executors
- Queries run on encrypted datasets with permission validation
- Results are filtered based on DataDAO-defined permissions

### Relevant for This Project
This **PII anonymization compute job** aligns perfectly with Vana's privacy-first architecture:
- **Privacy-Preserving Processing**: Automatically anonymizes sensitive data within TEEs
- **Query Engine Integration**: Receives query results and processes them for privacy compliance
- **Zero Raw Data Exposure**: Ensures PII never leaves the secure compute environment in unprotected form
- **Regulatory Compliance**: Helps DataDAOs meet GDPR, HIPAA, and other privacy regulations
- **Trust Through Transparency**: Provides detailed anonymization reports for audit and verification
- **TEE-Optimized**: Designed for Vana's trusted execution environment with proper attestation
- **Revenue Protection**: Enables safe data monetization by removing liability from PII exposure